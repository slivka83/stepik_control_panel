"""Hardest steps ranking by success rate."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import (
    _parse_step_positions,
    build_step_path_maps,
    get_courses_for_user,
    weighted_success_pct,
    wilson_success_pct,
)
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import Submission, User

router = APIRouter()


@router.get("/hardest-steps")
async def get_hardest_steps(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    min_submissions: int = Query(10, ge=1),
    course_ids: str = Query(None),
):
    course_uuids, course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    if not course_ids:
        return {"steps": []}

    course_map = {c.id: c.title for c in course_uuids}

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

    if steps:
        path_maps = await build_step_path_maps(db, [s["stepik_step_id"] for s in steps])
        for s in steps:
            s.update(path_maps.get(s["stepik_step_id"], {}))

    return {"steps": steps}
