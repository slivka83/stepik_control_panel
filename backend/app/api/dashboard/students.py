"""Paginated aggregated student list.

Reads the student_marts view layer only — one row per student, rebuilt
by transform_students at the end of each sync.

With ?course_ids= the list is restricted to students enrolled in at least
one of the selected courses (student_marts has no per-course breakdown, so
the membership is resolved via student_enrollments).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import StudentEnrollment, StudentMart, User

router = APIRouter()

SORTABLE = {
    "name": StudentMart.name,
    "cohort_status": StudentMart.cohort_status,
    "courses_count": StudentMart.courses_count,
    "certificates": StudentMart.certificates,
    "submissions_count": StudentMart.submissions_count,
    "comments_count": StudentMart.comments_count,
    "published_solutions": StudentMart.published_solutions,
    "last_activity": StudentMart.last_activity,
}


@router.get("/students")
async def get_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("last_activity"),
    order: str = Query("desc"),
    course_ids: str = Query(None),
):
    parsed = parse_course_ids(course_ids)
    course_uuids = None
    if parsed is not None:
        _, course_uuids = await get_courses_for_user(db, user, parsed)

    col = SORTABLE.get(sort)
    if col is None:
        raise HTTPException(status_code=400, detail=f"invalid sort field: {sort!r}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    order_by = col.asc().nullslast() if order == "asc" else col.desc().nullslast()

    base = select(StudentMart)
    count_base = select(func.count(StudentMart.id))
    if course_uuids is not None:
        in_selected = exists().where(
            StudentEnrollment.student_id == StudentMart.student_id,
            StudentEnrollment.course_id.in_(course_uuids),
        )
        base = base.where(in_selected)
        count_base = count_base.where(in_selected)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    result = await db.execute(base.order_by(order_by).offset(skip).limit(limit))

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
                "published_solutions": m.published_solutions,
                "last_activity": m.last_activity.isoformat() if m.last_activity else None,
            }
        )

    return {"students": students, "total": total}
