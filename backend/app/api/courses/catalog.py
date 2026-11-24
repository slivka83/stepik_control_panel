"""Course catalog endpoints: list of courses and one course."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.courses.common import load_owned_course
from app.database import get_db
from app.models import Course, FinancialSnapshot, StudentEnrollment, User

router = APIRouter()


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
    snapshot_data = snapshot.data if snapshot is not None and isinstance(snapshot.data, dict) else {}
    community = snapshot_data.get("community")
    per_course_community = (
        community.get("per_course", {}) if isinstance(community, dict) else {}
    )
    if not isinstance(per_course_community, dict):
        per_course_community = {}
    finance_courses = {}
    for c in snapshot_data.get("courses", []):
        if not isinstance(c, dict):
            continue
        try:
            finance_courses[int(c["course_id"])] = c
        except (KeyError, TypeError, ValueError):
            continue

    courses_list = []
    for course in courses:
        sid = str(course.stepik_course_id)
        fc = finance_courses.get(course.stepik_course_id, {})
        if not isinstance(fc, dict):
            fc = {}
        pc = per_course_community.get(sid, {})
        if not isinstance(pc, dict):
            pc = {}
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
    # Stable order: published first (newest on top), drafts after them, ties by
    # title. Without the tiebreak the table order changed between requests.
    courses_list.sort(key=lambda c: (c["title"] or "").casefold())
    courses_list.sort(key=lambda c: c["published_at"] or "", reverse=True)
    courses_list.sort(key=lambda c: c["published_at"] is not None, reverse=True)
    return {"courses": courses_list}


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    course = await load_owned_course(db, user, course_id)
    return {
        "course": {
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
        }
    }
