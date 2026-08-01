"""Hardest steps ranking by success rate."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.database import get_db
from app.models import Course, Submission, User

router = APIRouter()


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
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author.is_(False),
        )
        .group_by(Submission.stepik_step_id, Submission.course_id)
        .having(func.count(Submission.id) >= min_submissions)
        .order_by(
            (func.count(case((Submission.status == "correct", 1), else_=None)) * 1.0 / func.count(Submission.id)).asc()
        )
        .limit(limit)
    )
    rows = result.all()

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
                "success_pct": round((correct / total) * 100, 1) if total > 0 else 0,
            }
        )

    return {"steps": steps}
