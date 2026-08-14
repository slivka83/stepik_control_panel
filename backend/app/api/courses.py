import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.database import get_db
from app.models import Course, FinancialSnapshot, StudentEnrollment, Submission, User

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(select(Course).where(Course.user_id == user.id))
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    enroll_counts = {}
    cert_counts = {}
    if course_ids:
        enroll_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(StudentEnrollment.course_id.in_(course_ids))
            .group_by(StudentEnrollment.course_id)
        )
        enroll_counts = {row[0]: row[1] for row in enroll_result.all()}

        cert_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.certificate_issued.is_(True),
            )
            .group_by(StudentEnrollment.course_id)
        )
        cert_counts = {row[0]: row[1] for row in cert_result.all()}

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    per_course_community = snapshot.data.get("community", {}).get("per_course", {}) if snapshot else {}
    finance_courses = {c["course_id"]: c for c in (snapshot.data.get("courses", []) if snapshot else [])}

    courses_list = []
    for course in courses:
        sid = str(course.stepik_course_id)
        fc = finance_courses.get(course.stepik_course_id, {})
        pc = per_course_community.get(sid, {})
        courses_list.append(
            {
                "id": str(course.id),
                "stepik_course_id": course.stepik_course_id,
                "title": course.title,
                "status": course.status,
                "price": fc.get("price"),
                "income": fc.get("income"),
                "published_at": course.published_at.isoformat() if course.published_at else None,
                "enrollment_count": enroll_counts.get(course.id, 0),
                "certificates_count": cert_counts.get(course.id, 0),
                "comments_count": pc.get("comments", 0),
                "reviews_count": pc.get("reviews_count", 0),
                "average_rating": pc.get("average_rating", 0),
            }
        )
    courses_list.sort(key=lambda c: (c["published_at"] is not None, c["published_at"] or ""), reverse=True)
    return {"courses": courses_list}


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {
        "course": {
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
        }
    }


@router.get("/{course_id}/structure")
async def get_course_structure(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    """Структура одного курса: модули → уроки → шаги со статистикой.

    Читается из витрин mart_modules/mart_lessons/mart_steps (атрибуция,
    сквозная нумерация и метрики шага пресчитаны transform_steps) + таблицы
    submissions. Метрики шага: viewed_by/passed_by/correct_ratio/grade из
    `raw_step._raw_json` (агрегаты Stepik API; grade — средняя оценка шага
    пользователями из num_grades, пять смайликов), total/correct/students из
    submissions (is_author=False).
    """
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course_payload = {
        "id": str(course.id),
        "stepik_course_id": course.stepik_course_id,
        "title": course.title,
    }

    modules_result = await db.execute(
        text(
            "SELECT module_number, module_title FROM mart_modules "
            "WHERE stepik_course_id = :cid ORDER BY module_number"
        ),
        {"cid": course.stepik_course_id},
    )
    module_rows = modules_result.all()

    lessons_result = await db.execute(
        text(
            "SELECT lesson_id, lesson_number, module_number, lesson_title "
            "FROM mart_lessons WHERE stepik_course_id = :cid "
            "ORDER BY module_number, lesson_number"
        ),
        {"cid": course.stepik_course_id},
    )
    lessons_by_module: dict[int, list[tuple[int, int]]] = {}
    lesson_numbers: dict[int, int] = {}
    lesson_titles: dict[int, str] = {}
    for lesson_id, lesson_number, module_number, lesson_title in lessons_result:
        if module_number is None or lesson_number is None:
            continue
        lessons_by_module.setdefault(module_number, []).append((lesson_number, lesson_id))
        lesson_numbers[lesson_id] = lesson_number
        lesson_titles[lesson_id] = lesson_title

    steps_result = await db.execute(
        text(
            "SELECT step_id, lesson_id, step_number, block, viewed_by, passed_by, "
            "correct_ratio, grade, grade_votes FROM mart_steps WHERE stepik_course_id = :cid"
        ),
        {"cid": course.stepik_course_id},
    )
    steps_by_lesson: dict[int, list[dict]] = {}
    for step_id, lesson_id, step_number, block, viewed_by, passed_by, correct_ratio, grade, grade_votes in steps_result:
        if lesson_id is None:
            continue
        steps_by_lesson.setdefault(lesson_id, []).append(
            {
                "step_id": step_id,
                "lesson_id": lesson_id,
                "step_number": step_number,
                "block": block,
                "viewed_by": viewed_by,
                "passed_by": passed_by,
                "correct_ratio": correct_ratio,
                "grade": grade,
                "grade_votes": grade_votes or 0,
            }
        )

    stats: dict[int, dict] = {}
    sub_result = await db.execute(
        select(
            Submission.stepik_step_id,
            func.count(Submission.id).label("total"),
            func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(Submission.course_id == course_uuid, Submission.is_author.is_(False))
        .group_by(Submission.stepik_step_id)
    )
    for r in sub_result:
        if r[0] is None:
            continue
        stats[int(r[0])] = {"total": r[1], "correct": r[2], "students": r[3]}

    modules = []
    for module_number, module_title in module_rows:
        lessons = []
        for _lesson_number, lid in sorted(lessons_by_module.get(module_number, [])):
            steps = []
            for s in sorted(steps_by_lesson.get(lid, []), key=lambda s: s["step_number"] or 0):
                st = stats.get(s["step_id"], {})
                steps.append(
                    {
                        **s,
                        "total": st.get("total", 0),
                        "correct": st.get("correct", 0),
                        "students": st.get("students", 0),
                    }
                )
            lessons.append(
                {
                    "lesson_id": lid,
                    "lesson_number": lesson_numbers.get(lid),
                    "title": lesson_titles.get(lid),
                    "steps": steps,
                }
            )
        modules.append(
            {
                "position": module_number,
                "title": module_title,
                "lessons": lessons,
            }
        )

    if not module_rows:
        return {"course": course_payload, "modules": []}
    return {"course": course_payload, "modules": modules}


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
    if view not in ("modules", "lessons"):
        view = "modules"

    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course_payload = {
        "id": str(course.id),
        "stepik_course_id": course.stepik_course_id,
        "title": course.title,
    }

    entry_titles: list[tuple[int, str]] = []
    step_to_entry: dict[int, int] = {}
    if view == "lessons":
        lessons_result = await db.execute(
            text(
                "SELECT lesson_id, lesson_number, lesson_title FROM mart_lessons "
                "WHERE stepik_course_id = :cid ORDER BY lesson_number"
            ),
            {"cid": course.stepik_course_id},
        )
        lesson_index: dict[int, int] = {}
        for lesson_id, lesson_number, lesson_title in lessons_result:
            idx = len(entry_titles)
            entry_titles.append((lesson_number, lesson_title or ""))
            lesson_index[lesson_id] = idx
        step_rows = await db.execute(
            text(
                "SELECT step_id, lesson_id FROM mart_steps "
                "WHERE stepik_course_id = :cid"
            ),
            {"cid": course.stepik_course_id},
        )
        for step_id, lesson_id in step_rows:
            idx = lesson_index.get(lesson_id)
            if idx is not None:
                step_to_entry[int(step_id)] = idx
    else:
        modules_result = await db.execute(
            text(
                "SELECT module_number, module_title FROM mart_modules "
                "WHERE stepik_course_id = :cid ORDER BY module_number"
            ),
            {"cid": course.stepik_course_id},
        )
        module_numbers: list[int] = []
        for module_number, module_title in modules_result:
            entry_titles.append((module_number, module_title or ""))
            module_numbers.append(module_number)
        step_rows = await db.execute(
            text(
                "SELECT step_id, module_number FROM mart_steps "
                "WHERE stepik_course_id = :cid"
            ),
            {"cid": course.stepik_course_id},
        )
        for step_id, module_number in step_rows:
            if module_number is None:
                continue
            try:
                idx = module_numbers.index(module_number)
            except ValueError:
                continue
            step_to_entry[int(step_id)] = idx

    entry_users: list[set] = [set() for _ in entry_titles]
    sub_result = await db.execute(
        select(Submission.stepik_step_id, Submission.user_id)
        .where(
            Submission.course_id == course_uuid,
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
        .where(StudentEnrollment.course_id == course_uuid)
    )
    enrolled = enroll_result.scalar_one()

    cert_result = await db.execute(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(
            StudentEnrollment.course_id == course_uuid,
            StudentEnrollment.certificate_issued.is_(True),
        )
    )
    certificate_count = cert_result.scalar_one()

    suffix_values = [0] * len(entry_users)
    suffix: set = set()
    for i in range(len(entry_users) - 1, -1, -1):
        suffix |= entry_users[i]
        suffix_values[i] = len(suffix)

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

    return {"course": course_payload, "stages": stages}
