from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Course, StudentEnrollment, FinancialTransaction
from app.api.auth import get_user

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(user=Depends(get_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = result.scalars().all()
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
