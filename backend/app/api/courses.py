from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Course, StudentEnrollment
from app.api.auth import get_user

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(user=Depends(get_user), db: AsyncSession = Depends(get_db)):
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
async def get_course(course_id: str, user=Depends(get_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.user_id == user.id)
    )
    course = result.scalar_one_or_none()
    if not course:
        return {"error": "Course not found"}, 404
    return {"course": course}
