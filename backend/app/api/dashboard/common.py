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
    """Return (courses, course_ids) for the current user.

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
    Пустой список → NULL (никогда не совпадает): «IN ()» — синтаксическая
    ошибка на всех поддерживаемых БД.
    """
    vals = sorted(values)
    if not vals:
        return "NULL", {}
    placeholders = ", ".join(f":{prefix}{i}" for i in range(len(vals)))
    params = {f"{prefix}{i}": v for i, v in enumerate(vals)}
    return placeholders, params


def votes_weighted_grade(rows) -> float:
    """Средняя оценка шагов, взвешенная по числу голосов (`grade_votes`).

    `rows` — пары (grade, votes). Одна формула для KPI и фильтра по курсам:
    шаги без оценки/голосов пропускаются, деления на ноль нет.
    """
    votes_total = 0.0
    votes_count = 0
    for grade, votes in rows:
        try:
            grade_f = float(grade)
            votes_i = int(votes)
        except (TypeError, ValueError):
            continue
        if votes_i <= 0:
            continue
        votes_total += grade_f * votes_i
        votes_count += votes_i
    return round(votes_total / votes_count, 2) if votes_count else 0.0


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


def course_label(course_by_stepik: dict, stepik_course_id) -> tuple[str, str]:
    """(uuid курса, название) для строки витрины; пусто/«Unknown» без курса."""
    course = course_by_stepik.get(stepik_course_id)
    if course is None:
        return "", "Unknown"
    return str(course.id), course.title


class PeriodAggregator:
    """Копилка «месяц / год / курс» для витрин (комментарии, сертификаты, отзывы).

    Числовые метрики суммируются, студенты считаются distinct в каждой группе:
    один студент в нескольких месяцах не должен задвоиться в годе и итогах.
    Строки без года/месяца пропускаются целиком — как и раньше в каждом
    эндпоинте по отдельности.
    """

    def __init__(self, metrics: dict[str, int | float]):
        """metrics: имя метрики → начальное значение (0 для счётчиков, 0.0 для сумм)."""
        self._metrics = dict(metrics)
        self._months: dict[tuple[int, int], dict] = {}
        self._month_students: dict[tuple[int, int], set] = {}
        self._year_students: dict[int, set] = {}
        self._courses: dict[int, dict] = {}
        self._course_students: dict[int, set] = {}
        self._all_students: set = set()

    def _blank(self) -> dict:
        return {**self._metrics, "total": 0}

    def add(
        self,
        *,
        year,
        month,
        course_id,
        student_id,
        **values,
    ) -> None:
        if year is None or month is None:
            return

        ym = (year, month)
        month_bucket = self._months.setdefault(ym, self._blank())
        course_bucket = self._courses.setdefault(course_id, self._blank())
        for key in self._metrics:
            value = values.get(key) or 0
            month_bucket[key] += value
            course_bucket[key] += value
        month_bucket["total"] += 1
        course_bucket["total"] += 1

        if student_id is not None:
            self._month_students.setdefault(ym, set()).add(student_id)
            self._year_students.setdefault(year, set()).add(student_id)
            self._course_students.setdefault(course_id, set()).add(student_id)
            self._all_students.add(student_id)

    def _metrics_of(self, bucket: dict) -> dict:
        return {key: bucket[key] for key in self._metrics}

    def months(self) -> list[dict]:
        """Месяцы по возрастанию даты: year, month, students, total + метрики."""
        return [
            {
                "year": year,
                "month": month,
                "students": len(self._month_students.get((year, month), ())),
                **self._metrics_of(bucket),
                "total": bucket["total"],
            }
            for (year, month), bucket in sorted(self._months.items())
        ]

    def years(self) -> list[dict]:
        """Годы по возрастанию: year, students, total + метрики."""
        aggs: dict[int, dict] = {}
        for (year, _month), bucket in self._months.items():
            agg = aggs.setdefault(year, self._blank())
            agg["total"] += bucket["total"]
            for key in self._metrics:
                agg[key] += bucket[key]
        return [
            {
                "year": year,
                "students": len(self._year_students.get(year, ())),
                **self._metrics_of(agg),
                "total": agg["total"],
            }
            for year, agg in sorted(aggs.items())
        ]

    def courses(self) -> list[dict]:
        """Курсы по возрастанию stepik id: stepik_course_id, students, total + метрики."""
        return [
            {
                "stepik_course_id": cid,
                "students": len(self._course_students.get(cid, ())),
                **self._metrics_of(bucket),
                "total": bucket["total"],
            }
            for cid, bucket in sorted(self._courses.items())
        ]

    def totals(self) -> dict:
        """Итоги по всем месяцам: students, total + метрики."""
        total = self._blank()
        for bucket in self._months.values():
            total["total"] += bucket["total"]
            for key in self._metrics:
                total[key] += bucket[key]
        return {"students": len(self._all_students), **total}
