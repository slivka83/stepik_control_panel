"""Cohort segmentation counts."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import StudentEnrollment, User

router = APIRouter()


@router.get("/cohorts")
async def get_cohorts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    _, course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    if not course_ids:
        return {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}

    now = datetime.now(UTC)
    cohorts = {}

    for label, days_min, days_max in [
        ("active", 0, 7),
        ("passive", 7, 30),
        ("fading", 30, 90),
    ]:
        result = await db.execute(
            select(func.count(StudentEnrollment.id)).where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.cohort_status != "Zombie",
                StudentEnrollment.last_viewed_at >= now - timedelta(days=days_max),
                StudentEnrollment.last_viewed_at < now - timedelta(days=days_min),
            )
        )
        cohorts[label] = result.scalar() or 0

    sleeping_result = await db.execute(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.last_viewed_at < now - timedelta(days=90),
            StudentEnrollment.cohort_status != "Zombie",
        )
    )
    cohorts["sleeping"] = sleeping_result.scalar() or 0

    zombie_result = await db.execute(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.cohort_status == "Zombie",
        )
    )
    cohorts["zombie"] = zombie_result.scalar() or 0

    return cohorts
