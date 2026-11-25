"""Course structure: modules → lessons → steps with per-step metrics."""

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.courses.common import course_payload, load_owned_course
from app.database import get_db
from app.models import Submission, User

router = APIRouter()


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
    course = await load_owned_course(db, user, course_id)
    course_payload_ = course_payload(course)

    modules_result = await db.execute(
        text(
            "SELECT module_number, module_title FROM mart_modules WHERE stepik_course_id = :cid ORDER BY module_number"
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
    lesson_titles: dict[int, str] = {}
    for lesson_id, lesson_number, module_number, lesson_title in lessons_result:
        if module_number is None or lesson_number is None:
            continue
        lessons_by_module.setdefault(module_number, []).append((lesson_number, lesson_id))
        lesson_titles[lesson_id] = lesson_title

    steps_result = await db.execute(
        text(
            "SELECT step_id, lesson_id, step_number, block, viewed_by, passed_by, "
            "correct_ratio, grade, grade_votes FROM mart_steps WHERE stepik_course_id = :cid"
        ),
        {"cid": course.stepik_course_id},
    )
    steps_by_lesson: dict[int, list[dict]] = {}
    for (
        step_id,
        lesson_id,
        step_number,
        block,
        viewed_by,
        passed_by,
        correct_ratio,
        grade,
        grade_votes,
    ) in steps_result:
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
        .where(Submission.course_id == course.id, Submission.is_author.is_(False))
        .group_by(Submission.stepik_step_id)
    )
    for r in sub_result:
        if r[0] is None:
            continue
        stats[int(r[0])] = {"total": r[1], "correct": r[2], "students": r[3]}

    modules = []
    for module_number, module_title in module_rows:
        lessons = []
        for lesson_number, lid in sorted(lessons_by_module.get(module_number, [])):
            steps = []
            for s in sorted(
                steps_by_lesson.get(lid, []),
                key=lambda s: (s["step_number"] is None, s["step_number"] or 0),
            ):
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
                    "lesson_number": lesson_number,
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

    return {"course": course_payload_, "modules": modules}
