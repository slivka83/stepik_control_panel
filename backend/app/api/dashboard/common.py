"""Shared helpers for dashboard endpoints."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MONTH_NAMES
from app.models import Course, User


async def get_courses_for_user(db: AsyncSession, user: User) -> tuple[list[Course], list]:
    """Return (courses, course_ids) for the current user, in title order."""
    courses_result = await db.execute(select(Course).where(Course.user_id == user.id))
    courses = list(courses_result.scalars().all())
    return courses, [c.id for c in courses]


def format_month_label(month: int, year: int) -> str:
    return f"{MONTH_NAMES.get(month, str(month))} {year}"
