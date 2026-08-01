"""Paginated aggregated student list.

Reads the student_marts view layer only — one row per student, rebuilt
by transform_students at the end of each sync.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.database import get_db
from app.models import StudentMart, User

router = APIRouter()


@router.get("/students")
async def get_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    total_result = await db.execute(select(func.count(StudentMart.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(StudentMart)
        .order_by(StudentMart.last_activity.desc().nullslast())
        .offset(skip)
        .limit(limit)
    )

    students = []
    for m in result.scalars().all():
        students.append(
            {
                "student_id": m.student_id,
                "name": m.name,
                "profile_url": f"https://stepik.org/users/{m.student_id}",
                "cohort_status": m.cohort_status,
                "courses_count": m.courses_count,
                "certificates": m.certificates,
                "submissions_count": m.submissions_count,
                "submissions_successful": m.submissions_successful,
                "comments_count": m.comments_count,
                "last_activity": m.last_activity.isoformat() if m.last_activity else None,
            }
        )

    return {"students": students, "total": total}
