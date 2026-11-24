"""Cohort segmentation counts."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.constants import COHORT_ACTIVE_DAYS, COHORT_FADING_DAYS, COHORT_PASSIVE_DAYS
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
    # NULL status (старые строки) не должен выпадать из всех сегментов:
    # `status != 'Zombie'` для NULL даёт NULL (false).
    not_zombie = or_(
        StudentEnrollment.cohort_status.is_(None),
        StudentEnrollment.cohort_status != "Zombie",
    )

    for label, days_min, days_max in [
        ("active", 0, COHORT_ACTIVE_DAYS),
        ("passive", COHORT_ACTIVE_DAYS, COHORT_PASSIVE_DAYS),
        ("fading", COHORT_PASSIVE_DAYS, COHORT_FADING_DAYS),
    ]:
        conditions = [
            StudentEnrollment.course_id.in_(course_ids),
            not_zombie,
            StudentEnrollment.last_viewed_at >= now - timedelta(days=days_max),
        ]
        if days_min:
            # Для active верхней границы нет: запись ровно «сейчас» (или с
            # небольшим сдвигом часов вперёд) иначе выпадала из всех сегментов.
            conditions.append(StudentEnrollment.last_viewed_at < now - timedelta(days=days_min))
        result = await db.execute(select(func.count(StudentEnrollment.id)).where(*conditions))
        cohorts[label] = result.scalar() or 0

    sleeping_result = await db.execute(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.last_viewed_at < now - timedelta(days=COHORT_FADING_DAYS),
            not_zombie,
        )
    )
    cohorts["sleeping"] = sleeping_result.scalar() or 0

    zombie_result = await db.execute(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.course_id.in_(course_ids),
            or_(
                StudentEnrollment.cohort_status == "Zombie",
                StudentEnrollment.last_viewed_at.is_(None),
            ),
        )
    )
    cohorts["zombie"] = zombie_result.scalar() or 0

    return cohorts
