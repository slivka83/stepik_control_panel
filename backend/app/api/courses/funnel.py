"""Course completion funnel (by modules or by lessons)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.courses.common import course_payload, load_owned_course
from app.database import get_db
from app.models import StudentEnrollment, Submission, User

router = APIRouter()

FUNNEL_VIEWS = ("modules", "lessons")


async def _module_entries(db: AsyncSession, stepik_course_id: int):
    """(titles, step→entry index) for the module view."""
    modules_result = await db.execute(
        text(
            "SELECT module_number, module_title FROM mart_modules "
            "WHERE stepik_course_id = :cid ORDER BY module_number"
        ),
        {"cid": stepik_course_id},
    )
    entry_titles: list[tuple[int, str]] = []
    module_index: dict[int, int] = {}
    for module_number, module_title in modules_result:
        # list.index(...) в прежней реализации брал ПЕРВОЕ вхождение номера
        if module_number not in module_index:
            module_index[module_number] = len(entry_titles)
        entry_titles.append((module_number, module_title or ""))

    step_to_entry: dict[int, int] = {}
    step_rows = await db.execute(
        text(
            "SELECT step_id, module_number FROM mart_steps "
            "WHERE stepik_course_id = :cid"
        ),
        {"cid": stepik_course_id},
    )
    for step_id, module_number in step_rows:
        if module_number is None:
            continue
        idx = module_index.get(module_number)
        if idx is not None:
            step_to_entry[int(step_id)] = idx
    return entry_titles, step_to_entry


async def _lesson_entries(db: AsyncSession, stepik_course_id: int):
    """(titles, step→entry index) for the lesson view (school-wide numbering)."""
    lessons_result = await db.execute(
        text(
            "SELECT lesson_id, lesson_number, lesson_title FROM mart_lessons "
            "WHERE stepik_course_id = :cid ORDER BY lesson_number"
        ),
        {"cid": stepik_course_id},
    )
    entry_titles: list[tuple[int, str]] = []
    lesson_index: dict[int, int] = {}
    for lesson_id, lesson_number, lesson_title in lessons_result:
        lesson_index[lesson_id] = len(entry_titles)
        entry_titles.append((lesson_number, lesson_title or ""))

    step_to_entry: dict[int, int] = {}
    step_rows = await db.execute(
        text(
            "SELECT step_id, lesson_id FROM mart_steps "
            "WHERE stepik_course_id = :cid"
        ),
        {"cid": stepik_course_id},
    )
    for step_id, lesson_id in step_rows:
        idx = lesson_index.get(lesson_id)
        if idx is not None:
            step_to_entry[int(step_id)] = idx
    return entry_titles, step_to_entry


def _suffix_values(entry_users: list[set]) -> list[int]:
    """Cumulative distinct students: group i or any later group."""
    suffix_values = [0] * len(entry_users)
    suffix: set = set()
    for i in range(len(entry_users) - 1, -1, -1):
        suffix |= entry_users[i]
        suffix_values[i] = len(suffix)
    return suffix_values


@router.get("/{course_id}/funnel")
async def get_course_funnel(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    view: str = Query("modules"),
):
    """Воронка прохождения одного курса.

    Этапы: «Записались» → группа N («Модуль N» при view=modules, «Урок N» при
    view=lessons) → «Получили сертификат». Значение этапа группы —
    distinct-студенты, отправившие хотя бы одно решение в этой группе или позже
    (cumulative suffix: воронка монотонно убывает). Первая группа фактически =
    «начали курс» (сделали хотя бы одно решение). Шаги, не атрибутированные в
    структуру (не синканы), пропускаются. Авторские решения (is_author=True)
    исключены.
    """
    if view not in FUNNEL_VIEWS:
        view = "modules"

    course = await load_owned_course(db, user, course_id)
    course_payload_ = course_payload(course)

    if view == "lessons":
        entry_titles, step_to_entry = await _lesson_entries(db, course.stepik_course_id)
    else:
        entry_titles, step_to_entry = await _module_entries(db, course.stepik_course_id)

    entry_users: list[set] = [set() for _ in entry_titles]
    sub_result = await db.execute(
        select(Submission.stepik_step_id, Submission.user_id)
        .where(
            Submission.course_id == course.id,
            Submission.is_author.is_(False),
            Submission.user_id.is_not(None),
        )
        .distinct()
    )
    for step_id, user_id in sub_result:
        idx = step_to_entry.get(int(step_id))
        if idx is not None:
            entry_users[idx].add(user_id)

    enroll_result = await db.execute(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(StudentEnrollment.course_id == course.id)
    )
    enrolled = enroll_result.scalar_one()

    cert_result = await db.execute(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(
            StudentEnrollment.course_id == course.id,
            StudentEnrollment.certificate_issued.is_(True),
        )
    )
    certificate_count = cert_result.scalar_one()

    suffix_values = _suffix_values(entry_users)

    stages = [{"key": "enrolled", "label": "Записались", "value": enrolled}]
    if view == "lessons":
        for i, (lesson_number, title) in enumerate(entry_titles):
            stages.append(
                {
                    "key": "lesson",
                    "lesson_number": lesson_number,
                    "label": f"Урок {lesson_number}. {title}" if title else f"Урок {lesson_number}",
                    "value": suffix_values[i],
                }
            )
    else:
        for i, (position, title) in enumerate(entry_titles):
            stages.append(
                {
                    "key": "module",
                    "module_number": position,
                    "label": f"Модуль {position}. {title}" if title else f"Модуль {position}",
                    "value": suffix_values[i],
                }
            )
    stages.append({"key": "certificate", "label": "Получили сертификат", "value": certificate_count})

    return {"course": course_payload_, "stages": stages}
