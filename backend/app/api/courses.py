import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Course, StudentEnrollment, User
from app.api.auth import get_user

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            Course,
            func.count(StudentEnrollment.id).label("enrollment_count"),
        )
        .outerjoin(StudentEnrollment, Course.id == StudentEnrollment.course_id)
        .where(Course.user_id == user.id)
        .group_by(Course.id)
    )
    rows = result.all()
    courses = []
    for course, enrollment_count in rows:
        courses.append({
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
            "health_score": course.health_score,
            "enrollment_count": enrollment_count,
        })
    return {"courses": courses}


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found")
    result = await db.execute(
        select(Course).where(Course.id == course_uuid, Course.user_id == user.id)
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {
        "course": {
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
            "health_score": course.health_score,
        }
    }
