"""Структура: raw_section + raw_unit + raw_lesson + raw_step → mart_modules/mart_lessons/mart_steps."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import (
    _insert_rows,
    _parse_raw,
    _parse_step_positions,
    _step_grade,
    _to_float,
    _to_int,
    load_course_map,
)

logger = logging.getLogger(__name__)


async def transform_steps(session: AsyncSession):
    """Build mart_modules/mart_lessons/mart_steps from the raw structure.

    Step→course attribution and module/lesson numbering are the single source
    for structure/funnel/hardest-steps/comment paths. mart_steps keeps steps
    without course attribution (course_id NULL) — they feed the average step
    grade (kpi) and hardest-steps paths.
    """
    logger.info("=== Mart steps ===")

    course_map = await load_course_map(session)

    sections: dict[str, dict] = {}
    r = await session.execute(text("SELECT section_id, course, position, title FROM raw_section"))
    for section_id, course, position, title in r:
        if section_id is None:
            continue
        sections[str(section_id)] = {
            "course": _to_int(course),
            "position": _to_int(position),
            "title": title,
        }

    units_by_section: dict[str, list[tuple[int, int]]] = {}
    r = await session.execute(text("SELECT lesson_id, section_id, position FROM raw_unit"))
    for lesson_id, section_id, position in r:
        if lesson_id is None or section_id is None:
            continue
        units_by_section.setdefault(str(section_id), []).append((_to_int(position) or 0, _to_int(lesson_id)))

    lesson_info: dict[int, dict] = {}
    r = await session.execute(text("SELECT lesson_id, steps, title FROM raw_lesson"))
    for lesson_id, steps, title in r:
        lid = _to_int(lesson_id)
        if lid is None:
            continue
        lesson_info[lid] = {"title": title, "step_positions": _parse_step_positions(steps)}

    step_meta: dict[int, dict] = {}
    raw_step_lesson: dict[int, int] = {}
    r = await session.execute(text("SELECT step_id, lesson, _raw_json FROM raw_step"))
    for step_id, lesson, raw_json in r:
        sid = _to_int(step_id)
        if sid is None:
            continue
        lid = _to_int(lesson)
        if lid is not None:
            raw_step_lesson[sid] = lid
        raw = _parse_raw(raw_json)
        block = raw.get("block") if isinstance(raw.get("block"), dict) else None
        grade, grade_votes = _step_grade(raw)
        step_meta[sid] = {
            "block": block.get("name") if isinstance(block, dict) else None,
            "viewed_by": _to_int(raw.get("viewed_by")),
            "passed_by": _to_int(raw.get("passed_by")),
            "correct_ratio": _to_float(raw.get("correct_ratio")),
            "grade": grade,
            "grade_votes": grade_votes,
        }

    # Сквозная нумерация по курсу: module_number = индекс секции (по position),
    # lesson_number = порядковый номер урока в курсе. Считаем именно порядок,
    # а не offset + raw position: после удаления юнита positions идут с дырами
    # (1, 3, 4), и прежняя формула давала дубли номеров на границе модулей.
    course_sections: dict[int, list[str]] = {}
    for section_id, info in sections.items():
        if info["course"] is not None:
            course_sections.setdefault(info["course"], []).append(section_id)

    module_info: dict[str, dict] = {}
    lesson_attr: dict[int, dict] = {}
    # One row per UNIT (a lesson may be added to two units of one course).
    # lesson_attr keeps only the first path of a lesson — steps have one path.
    unit_entries: list[dict] = []
    # Known courses first: a lesson shared with a course missing from the
    # panel must belong to the displayed course (same rule as the step map).
    for course_int in sorted(course_sections, key=lambda cid: (0 if cid in course_map else 1, cid)):
        sec_ids = sorted(
            course_sections[course_int],
            key=lambda s: (sections[s]["position"] if sections[s]["position"] is not None else 0, s),
        )
        lesson_number = 0
        for module_number, section_id in enumerate(sec_ids, start=1):
            info = sections[section_id]
            module_info[section_id] = {
                "module_number": module_number,
                "module_title": info["title"],
                "course": course_int,
            }
            for _unit_pos, lesson_id in sorted(units_by_section.get(section_id, [])):
                if lesson_id is None:
                    continue
                existing = lesson_attr.get(lesson_id)
                # The same lesson in another course belongs to the first
                # (known-priority) course only.
                if existing is not None and existing["course"] != course_int:
                    continue
                # Секция может ссылаться на урок, которого нет в raw_lesson
                # (частичный синк/удалённый урок). Такой урок сохраняем для
                # атрибуции шагов, но не занимаем номер: иначе в нумерации
                # реальных уроков появлялась дыра (1, 3).
                has_lesson = lesson_id in lesson_info
                if has_lesson:
                    lesson_number += 1
                attr = {
                    "course": course_int,
                    "module_number": module_number,
                    "lesson_number": lesson_number if has_lesson else None,
                    "module_title": info["title"],
                }
                if existing is None:
                    lesson_attr[lesson_id] = attr
                if has_lesson:
                    unit_entries.append({"lesson_id": lesson_id, **attr})

    module_rows = []
    lesson_rows = []
    for course_int in sorted(course_sections):
        course_uuid = course_map.get(course_int)
        if course_uuid is None:
            continue
        for section_id in sorted(course_sections[course_int], key=lambda s: (module_info[s]["module_number"], s)):
            info = module_info[section_id]
            module_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "course_id": course_uuid,
                    "stepik_course_id": course_int,
                    "module_number": info["module_number"],
                    "module_title": info["module_title"],
                }
            )
        course_units = sorted(
            (entry for entry in unit_entries if entry["course"] == course_int),
            key=lambda entry: (entry["module_number"], entry["lesson_number"]),
        )
        for entry in course_units:
            li = lesson_info.get(entry["lesson_id"])
            if li is None:
                continue
            lesson_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "course_id": course_uuid,
                    "stepik_course_id": course_int,
                    "lesson_id": entry["lesson_id"],
                    "lesson_number": entry["lesson_number"],
                    "module_number": entry["module_number"],
                    "module_title": entry["module_title"],
                    "lesson_title": li["title"],
                }
            )

    # mart_steps = объединение шагов из raw_lesson.steps (структура) и всех
    # строк raw_step (метрики/kpi), атрибуция пути через unit→section→course.
    #
    # Один шаг может встречаться в нескольких уроках (и даже курсах). У
    # витрины один путь на шаг, поэтому первый найденный маршрут — источник
    # истины. Обход идёт в том же порядке, что и build_step_course_map
    # (курс → номер урока → lesson id), иначе структура и решения/комментарии
    # приписывали общий шаг разным курсам.
    def _lesson_order(lesson_id: int) -> tuple[int, int, int, int]:
        attr = lesson_attr.get(lesson_id)
        if attr is None:
            return (1, 0, 0, lesson_id)
        course = attr["course"]
        # Сначала курсы, которые есть в витрине курсов; уроки «чужого»
        # курса не должны забирать шаг у отображаемого курса.
        known_course = 0 if course in course_map else 1
        return (known_course, course, attr["lesson_number"] or 0, lesson_id)

    step_rows: dict[int, dict] = {}
    for lesson_id in sorted(lesson_info, key=_lesson_order):
        li = lesson_info[lesson_id]
        attr = lesson_attr.get(lesson_id)
        for step_id, step_number in sorted(li["step_positions"].items()):
            row = step_rows.setdefault(step_id, {"step_id": step_id})
            if "lesson_id" in row:
                continue
            row["lesson_id"] = lesson_id
            row["step_number"] = step_number
            row["lesson_title"] = li["title"]
            if attr is not None:
                row["module_number"] = attr["module_number"]
                row["lesson_number"] = attr["lesson_number"]
                row["module_title"] = attr["module_title"]
                course_uuid = course_map.get(attr["course"])
                if course_uuid is not None:
                    row["course_id"] = course_uuid
                    row["stepik_course_id"] = attr["course"]
    for step_id, lesson_id in sorted(raw_step_lesson.items()):
        if step_id in step_rows:
            # Структура уже задала путь; raw_step.lesson — только fallback.
            continue
        row = step_rows.setdefault(step_id, {"step_id": step_id})
        row["lesson_id"] = lesson_id
        li = lesson_info.get(lesson_id)
        if li is not None:
            row["lesson_title"] = li["title"]
            if step_id in li["step_positions"]:
                row["step_number"] = li["step_positions"][step_id]
        attr = lesson_attr.get(lesson_id)
        if attr is not None:
            row["module_number"] = attr["module_number"]
            row["lesson_number"] = attr["lesson_number"]
            row["module_title"] = attr["module_title"]
            course_uuid = course_map.get(attr["course"])
            if course_uuid is not None:
                row["course_id"] = course_uuid
                row["stepik_course_id"] = attr["course"]

    step_rows_final = []
    for step_id, row in step_rows.items():
        meta = step_meta.get(step_id, {})
        step_rows_final.append(
            {
                "id": str(uuid.uuid4()),
                "course_id": row.get("course_id"),
                "stepik_course_id": row.get("stepik_course_id"),
                "step_id": step_id,
                "lesson_id": row.get("lesson_id"),
                "step_number": row.get("step_number"),
                "module_number": row.get("module_number"),
                "lesson_number": row.get("lesson_number"),
                "module_title": row.get("module_title"),
                "lesson_title": row.get("lesson_title"),
                "block": meta.get("block"),
                "viewed_by": meta.get("viewed_by"),
                "passed_by": meta.get("passed_by"),
                "correct_ratio": meta.get("correct_ratio"),
                "grade": meta.get("grade"),
                "grade_votes": meta.get("grade_votes"),
            }
        )

    await session.execute(text("DELETE FROM mart_steps"))
    await session.execute(text("DELETE FROM mart_lessons"))
    await session.execute(text("DELETE FROM mart_modules"))
    await _insert_rows(session, "mart_modules", module_rows)
    await _insert_rows(session, "mart_lessons", lesson_rows)
    await _insert_rows(session, "mart_steps", step_rows_final)

    logger.info("  modules=%d lessons=%d steps=%d", len(module_rows), len(lesson_rows), len(step_rows_final))
