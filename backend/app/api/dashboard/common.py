"""Shared helpers for dashboard endpoints."""

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


def in_clause(values, prefix: str = "id") -> tuple[str, dict]:
    """SQL IN-плейсхолдеры для безопасного bind списка значений.

    Возвращает ("(:id0, :id1, ...)", {":id0": v0, ...}) — единая реализация
    для всех dashboard-эндпоинтов (раньше копипастилась 8 раз).
    """
    vals = sorted(values)
    placeholders = ", ".join(f":{prefix}{i}" for i in range(len(vals)))
    params = {f"{prefix}{i}": v for i, v in enumerate(vals)}
    return placeholders, params


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


async def build_step_path_maps(db: AsyncSession, step_ids: list[int]) -> dict[int, dict]:
    """step_id → «модуль.урок-шаг» карта для единого рендеринга пути шага.

    Возвращает {step_id: {lesson_id, step_number, module_number, lesson_number,
    lesson_title, module_title}}. Читается из витрины mart_steps (атрибуция и
    нумерация пресчитаны трансформом transform_steps). Для отсутствующих шагов
    все ключи присутствуют со значением None — клиент проверяет ключи, а не
    truthy-значения.
    """
    if not step_ids:
        return {}

    placeholders, params = in_clause(step_ids, "id")
    res = await db.execute(
        text(
            "SELECT step_id, lesson_id, step_number, module_number, lesson_number, "
            "module_title, lesson_title FROM mart_steps "
            f"WHERE step_id IN ({placeholders})"
        ),
        params,
    )
    result = {}
    for r in res:
        result[r[0]] = {
            "lesson_id": r[1],
            "step_number": r[2],
            "module_number": r[3],
            "lesson_number": r[4],
            "module_title": r[5],
            "lesson_title": r[6],
        }
    for sid in step_ids:
        result.setdefault(
            sid,
            {
                "lesson_id": None,
                "step_number": None,
                "module_number": None,
                "lesson_number": None,
                "module_title": None,
                "lesson_title": None,
            },
        )
    return result
