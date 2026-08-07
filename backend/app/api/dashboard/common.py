"""Shared helpers for dashboard endpoints."""

import json
import uuid
from math import sqrt

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MONTH_NAMES
from app.models import Course, User


async def get_courses_for_user(
    db: AsyncSession,
    user: User,
    course_ids: list[uuid.UUID] | None = None,
) -> tuple[list[Course], list]:
    """Return (courses, course_ids) for the current user, in title order.

    With course_ids given, restricts to the intersection with the user's
    courses — a caller can never see courses owned by another user.
    An empty list → no courses (explicitly nothing selected).
    """
    courses_result = await db.execute(select(Course).where(Course.user_id == user.id))
    courses = list(courses_result.scalars().all())
    if course_ids is not None:
        selected = set(course_ids)
        courses = [c for c in courses if c.id in selected]
    return courses, [c.id for c in courses]


def format_month_label(month: int, year: int) -> str:
    return f"{MONTH_NAMES.get(month, str(month))} {year}"


def json_field(val, field):
    """Extract a field from a raw `_raw_json` value (dict/list/JSON string)."""
    if isinstance(val, (dict, list)):
        return val.get(field) if isinstance(val, dict) else None
    if isinstance(val, (str, bytes, bytearray)):
        try:
            return json.loads(val).get(field)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def wilson_success_pct(correct: int, total: int, z: float = 1.96) -> float:
    """Lower bound of the 95% Wilson score interval, in percent (0..100).

    «Успех» учитывает объём попыток: чем их меньше, тем сильнее число
    занижается относительно наблюдённого correct/total (данных мало — верить
    нельзя); с ростом попыток значение приближается к наблюдённому.
    """
    if total <= 0:
        return 0.0
    p = correct / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denom) * 100


def weighted_success_pct(correct: int, total: int, global_pct: float, weight: float = 20) -> float:
    """«Взвешенный успех»: наблюдённый процент, притянутый к среднему.

    Мало попыток → цифра близка к среднему по всем шагам (global_pct) и не
    выглядит ни катастрофой, ни триумфом; много попыток → цифра = реальный
    correct/total. Используется для ранжирования «самых сложных», чтобы шаги
    с 1-2 попытками не всплывали наверх.
    """
    if total <= 0:
        return 0.0
    return (correct + weight * global_pct / 100) / (total + weight) * 100


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


async def build_step_path_maps(db: AsyncSession, step_ids: list[int]) -> dict[int, dict]:
    """step_id → «модуль.урок-шаг» карта для единого рендеринга пути шага.

    Возвращает {step_id: {lesson_id, step_number, module_number, lesson_number,
    lesson_title, module_title}}. Единый источник для hardest-steps и списков
    комментариев: модуль из raw_section.position, урок — сквозной номер в курсе
    (сумма уроков предыдущих модулей + позиция unit'а внутри своего модуля из
    raw_unit.position), шаг — позиция в raw_lesson.steps.
    """
    if not step_ids:
        return {}

    params = {f"id{i}": str(sid) for i, sid in enumerate(step_ids)}
    placeholders = ", ".join(f":id{i}" for i in range(len(step_ids)))
    res = await db.execute(
        text(f"SELECT DISTINCT step_id, lesson FROM raw_step WHERE step_id IN ({placeholders})"),
        params,
    )
    step_lesson = {int(r[0]): int(r[1]) for r in res if r[0] is not None and r[1] is not None}

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
    if lesson_ids:
        res_u = await db.execute(
            text(
                f"SELECT DISTINCT lesson_id, section_id, position FROM raw_unit WHERE lesson_id IN ({placeholders_l})"
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
    # урока = сумма уроков всех предыдущих модулей курса + номер урока внутри
    # своего модуля. Нужны ВСЕ секции курса, не только затронутые.
    module_number_map = {}
    lesson_number_map = {}
    if section_ids:
        course_numbers = {c for c, _, _ in section_info.values() if c is not None}
        if course_numbers:
            params_c = {f"cid{i}": str(cid_) for i, cid_ in enumerate(course_numbers)}
            placeholders_c = ", ".join(f":cid{i}" for i in range(len(course_numbers)))
            res_c = await db.execute(
                text(f"SELECT section_id, course, position FROM raw_section WHERE course IN ({placeholders_c})"),
                params_c,
            )
            all_sections = {}
            for r in res_c:
                if r[0] is None or r[1] is None:
                    continue
                all_sections.setdefault(int(r[1]), []).append((int(r[2]) if r[2] is not None else None, int(r[0])))
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

    result = {}
    for sid in step_ids:
        lid = step_lesson.get(sid)
        sid_ = lesson_section.get(lid) if lid is not None else None
        lesson_number = lesson_number_map.get(sid_) if sid_ is not None else None
        unit_pos = unit_position_map.get(lid) if lid is not None else None
        if sid_ is not None and lesson_number is not None and unit_pos is not None:
            lesson_number = lesson_number - 1 + unit_pos
        result[sid] = {
            "lesson_id": lid,
            "step_number": step_number_map.get(sid),
            "module_number": module_number_map.get(sid_) if sid_ is not None else None,
            "lesson_number": lesson_number,
            "lesson_title": lesson_title_map.get(lid) if lid is not None else None,
            "module_title": section_info.get(sid_, (None, None, None))[2] if sid_ is not None else None,
        }
    return result
