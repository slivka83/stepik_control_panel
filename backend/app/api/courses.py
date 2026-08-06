import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.database import get_db
from app.models import Course, FinancialSnapshot, StudentEnrollment, User

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(select(Course).where(Course.user_id == user.id))
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    enroll_counts = {}
    cert_counts = {}
    if course_ids:
        enroll_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(StudentEnrollment.course_id.in_(course_ids))
            .group_by(StudentEnrollment.course_id)
        )
        enroll_counts = {row[0]: row[1] for row in enroll_result.all()}

        cert_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.certificate_issued.is_(True),
            )
            .group_by(StudentEnrollment.course_id)
        )
        cert_counts = {row[0]: row[1] for row in cert_result.all()}

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    per_course_community = snapshot.data.get("community", {}).get("per_course", {}) if snapshot else {}
    finance_courses = {c["course_id"]: c for c in (snapshot.data.get("courses", []) if snapshot else [])}

    courses_list = []
    for course in courses:
        sid = str(course.stepik_course_id)
        fc = finance_courses.get(course.stepik_course_id, {})
        pc = per_course_community.get(sid, {})
        courses_list.append(
            {
                "id": str(course.id),
                "stepik_course_id": course.stepik_course_id,
                "title": course.title,
                "status": course.status,
                "price": fc.get("price"),
                "income": fc.get("income"),
                "published_at": course.published_at.isoformat() if course.published_at else None,
                "enrollment_count": enroll_counts.get(course.id, 0),
                "certificates_count": cert_counts.get(course.id, 0),
                "comments_count": pc.get("comments", 0),
                "reviews_count": pc.get("reviews_count", 0),
                "average_rating": pc.get("average_rating", 0),
            }
        )
    courses_list.sort(key=lambda c: (c["published_at"] is not None, c["published_at"] or ""), reverse=True)
    return {"courses": courses_list}


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {
        "course": {
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
        }
    }
