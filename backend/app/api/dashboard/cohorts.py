"""Cohort segmentation counts (one student = one segment)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.constants import COHORT_RANK
from app.database import get_db
from app.models import StudentEnrollment, User
from app.services.transform.common import calculate_cohort_status

router = APIRouter()

SEGMENTS = ("active", "passive", "fading", "sleeping", "zombie")


def _segment_for(stored_status, last_viewed_at, date_joined) -> str:
    """Best status of ONE enrollment.

    Stored Zombie is authoritative (it encodes "opened only in the first days
    after joining" — time alone cannot reproduce that without date_joined).
    Other stored statuses are intentionally recomputed from the latest
    activity, so the bar stays fresh between syncs.
    """
    if str(stored_status or "").strip().lower() == "zombie" or last_viewed_at is None:
        return "Zombie"
    return calculate_cohort_status(last_viewed_at, date_joined)


@router.get("/cohorts")
async def get_cohorts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    _, selected_course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    # An empty dict must still contain every segment key (the bar expects all).
    cohorts = dict.fromkeys(SEGMENTS, 0)
    if not selected_course_ids:
        return cohorts

    rows = await db.execute(
        select(
            StudentEnrollment.student_id,
            StudentEnrollment.cohort_status,
            StudentEnrollment.last_viewed_at,
            StudentEnrollment.date_joined,
        ).where(StudentEnrollment.course_id.in_(selected_course_ids))
    )

    # One student may study several courses with different activity. Collapse
    # to the best status (Active > Passive > …), exactly like student_marts.
    best: dict[int, tuple[int, str]] = {}
    for student_id, stored_status, last_viewed, joined in rows:
        status = _segment_for(stored_status, last_viewed, joined)
        rank = COHORT_RANK.get(status, 99)
        current = best.get(student_id)
        if current is None or rank < current[0]:
            best[student_id] = (rank, status)

    for _rank, status in best.values():
        key = status.lower()
        if key in cohorts:
            cohorts[key] += 1
    return cohorts
