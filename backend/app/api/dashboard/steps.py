"""Hardest steps ranking by success rate."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import weighted_success_pct, wilson_success_pct
from app.database import get_db
from app.models import Course, Submission, User

router = APIRouter()


def _parse_step_positions(raw) -> dict[int, int]:
    """step_id → позиция в уроке (1-based).

    raw_lesson.steps в реальной PG — jsonb: asyncpg возвращает уже
    разобранный list. В SQLite-фикстуре колонка TEXT: приходит JSON-строка.
    Оба варианта обязаны работать (регрессия: json.loads(list) → TypeError
    и молча пустой результат).
    """
    try:
        arr = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {}
    positions: dict[int, int] = {}
    if isinstance(arr, list):
        for i, sid in enumerate(arr):
            try:
                positions[int(sid)] = i + 1
            except (TypeError, ValueError):
                continue
    return positions


@router.get("/hardest-steps")
async def get_hardest_steps(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    min_submissions: int = Query(10, ge=1),
):
    course_ids_result = await db.execute(select(Course.id).where(Course.user_id == user.id))
    course_ids = [r[0] for r in course_ids_result.all()]

    if not course_ids:
        return {"steps": []}

    course_map_result = await db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids)))
    course_map = {row[0]: row[1] for row in course_map_result.all()}

    result = await db.execute(
        select(
            Submission.stepik_step_id,
            Submission.course_id,
            func.count(Submission.id).label("total"),
            func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author.is_(False),
        )
        .group_by(Submission.stepik_step_id, Submission.course_id)
        .having(func.count(Submission.id) >= min_submissions)
        .order_by(Submission.stepik_step_id)
    )
    rows = result.all()

    # Средний успех по ШАГАМ (не по попыткам): иначе доминирующий по объёму
    # шаг сдвигает global в свою сторону, и малообъёмный мусор притягивается
    # к нему, не отделяясь. Unweighted mean по шагам даёт «типичный» шаг.
    step_rates = [row.correct / row.total for row in rows if row.total > 0]
    global_pct = (sum(step_rates) / len(step_rates) * 100) if step_rates else 0.0

    steps = []
    for row in rows:
        total = row.total
        correct = row.correct
        steps.append(
            {
                "stepik_step_id": row.stepik_step_id,
                "course_id": str(row.course_id),
                "course_title": course_map.get(row.course_id, "Unknown"),
                "total": total,
                "correct": correct,
                "wrong": total - correct,
                "success_pct": round(wilson_success_pct(correct, total), 1),
                "weighted_success_pct": round(weighted_success_pct(correct, total, global_pct), 1),
                "students": row.students,
            }
        )

    steps.sort(key=lambda s: s["weighted_success_pct"])
    steps = steps[:limit]

    step_lesson = {}
    if steps:
        ids = [s["stepik_step_id"] for s in steps]
        params = {f"id{i}": str(sid) for i, sid in enumerate(ids)}
        placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
        res = await db.execute(
            text(f"SELECT DISTINCT step_id, lesson FROM raw_step WHERE step_id IN ({placeholders})"),
            params,
        )
        step_lesson = {
            int(r[0]): int(r[1])
            for r in res
            if r[0] is not None and r[1] is not None
        }

    step_number_map = {}
    lesson_title_map = {}
    lesson_ids = sorted({lid for lid in step_lesson.values() if lid is not None})
    if lesson_ids:
        params_l = {f"lid{i}": str(lid) for i, lid in enumerate(lesson_ids)}
        placeholders_l = ", ".join(f":lid{i}" for i in range(len(lesson_ids)))
        res_l = await db.execute(
            text(f"SELECT lesson_id, steps, title FROM raw_lesson WHERE lesson_id IN ({placeholders_l})"),
            params_l,
        )
        for r in res_l:
            if r[0] is None:
                continue
            if r[1]:
                step_number_map.update(_parse_step_positions(r[1]))
            if r[2]:
                lesson_title_map[int(r[0])] = r[2]

    lesson_section = {}
    unit_position_map = {}
    section_info = {}
    section_ids = []
    lesson_ids = sorted({lid for lid in step_lesson.values() if lid is not None})
    if lesson_ids:
        res_u = await db.execute(
            text(
                "SELECT DISTINCT lesson_id, section_id, position "
                f"FROM raw_unit WHERE lesson_id IN ({placeholders_l})"
            ),
            params_l,
        )
        for r in res_u:
            if r[0] is None or r[1] is None:
                continue
            lesson_section[int(r[0])] = int(r[1])
            if r[2] is not None:
                unit_position_map[int(r[0])] = int(r[2])
        section_ids = sorted({sid for sid in lesson_section.values()})
        params_s = {f"sid{i}": str(sid_) for i, sid_ in enumerate(section_ids)}
        placeholders_s = ", ".join(f":sid{i}" for i in range(len(section_ids)))
        if section_ids:
            res_s = await db.execute(
                text(
                    "SELECT section_id, course, position, title "
                    f"FROM raw_section WHERE section_id IN ({placeholders_s})"
                ),
                params_s,
            )
            for r in res_s:
                if r[0] is None:
                    continue
                section_info[int(r[0])] = (
                    int(r[1]) if r[1] is not None else None,
                    int(r[2]) if r[2] is not None else None,
                    r[3] if r[3] else None,
                )

    # Сквозная нумерация уроков (как в интерфейсе Stepik): глобальный номер
    # урока = сумма уроков всех предыдущих модулей курса + номер урока
    # внутри своего модуля. Нужны ВСЕ секции курса, не только затронутые.
    module_number_map = {}
    lesson_number_map = {}
    if section_ids:
        course_ids = {c for c, _, _ in section_info.values() if c is not None}
        if course_ids:
            params_c = {f"cid{i}": str(cid_) for i, cid_ in enumerate(course_ids)}
            placeholders_c = ", ".join(f":cid{i}" for i in range(len(course_ids)))
            res_c = await db.execute(
                text(f"SELECT section_id, course, position FROM raw_section WHERE course IN ({placeholders_c})"),
                params_c,
            )
            all_sections = {}
            for r in res_c:
                if r[0] is None or r[1] is None:
                    continue
                all_sections.setdefault(int(r[1]), []).append(
                    (int(r[2]) if r[2] is not None else None, int(r[0]))
                )
            params_u = {}
            all_section_ids = sorted({sid_ for secs in all_sections.values() for _, sid_ in secs})
            params_u = {f"sid{i}": str(sid_) for i, sid_ in enumerate(all_section_ids)}
            placeholders_u = ", ".join(f":sid{i}" for i in range(len(all_section_ids)))
            units_by_section = {}
            if all_section_ids:
                res_u2 = await db.execute(
                    text(
                        "SELECT section_id, COUNT(*) FROM raw_unit "
                        f"WHERE section_id IN ({placeholders_u}) GROUP BY section_id"
                    ),
                    params_u,
                )
                units_by_section = {int(r[0]): int(r[1]) for r in res_u2}
            for secs in all_sections.values():
                secs.sort(key=lambda t: t[0] if t[0] is not None else 0)
                offset = 0
                for idx, (_, sid_) in enumerate(secs):
                    module_number_map[sid_] = idx + 1
                    lesson_number_map[sid_] = offset + 1
                    offset += units_by_section.get(sid_, 0)

    for s in steps:
        lid = step_lesson.get(s["stepik_step_id"])
        s["lesson_id"] = lid
        s["step_number"] = step_number_map.get(s["stepik_step_id"])
        sid_ = lesson_section.get(lid) if lid is not None else None
        s["module_number"] = module_number_map.get(sid_) if sid_ is not None else None
        s["lesson_number"] = lesson_number_map.get(sid_) if sid_ is not None else None
        s["lesson_title"] = lesson_title_map.get(lid) if lid is not None else None
        s["module_title"] = section_info.get(sid_, (None, None, None))[2] if sid_ is not None else None
        unit_pos = unit_position_map.get(lid) if lid is not None else None
        if sid_ is not None and s["lesson_number"] is not None and unit_pos is not None:
            s["lesson_number"] = s["lesson_number"] - 1 + unit_pos

    return {"steps": steps}
