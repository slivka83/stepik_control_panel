"""Shared helpers for the courses API."""

import uuid as uuid_module

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, User

_COURSE_NOT_FOUND = "Course not found"


async def load_owned_course(db: AsyncSession, user: User, course_id: str) -> Course:
    """Return the user's course or raise 404 (invalid UUID and foreign course alike)."""
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND) from None

    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND)
    return course


def course_payload(course: Course) -> dict:
    return {
        "id": str(course.id),
        "stepik_course_id": course.stepik_course_id,
        "title": course.title,
    }
