import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Course, StudentEnrollment, Submission, FinancialSnapshot, User
from app.api.auth import get_user

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]
    course_id_to_stepik = {c.id: c.stepik_course_id for c in courses}

    enroll_counts = {}
    if course_ids:
        enroll_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(StudentEnrollment.course_id.in_(course_ids))
            .group_by(StudentEnrollment.course_id)
        )
        enroll_counts = dict(enroll_result.all())

    sub_totals = {}
    if course_ids:
        sub_result = await db.execute(
            select(
                Submission.course_id,
                func.count(Submission.id).label("total"),
                func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
            )
            .where(Submission.course_id.in_(course_ids), Submission.is_author == False)
            .group_by(Submission.course_id)
        )
        for row in sub_result.all():
            sub_totals[row.course_id] = {"total": row.total, "correct": row.correct}

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    per_course_community = snapshot.data.get("community", {}).get("per_course", {}) if snapshot else {}
    finance_courses = {c["course_id"]: c for c in (snapshot.data.get("courses", []) if snapshot else [])}

    courses_list = []
    for course in courses:
        sid = str(course.stepik_course_id)
        fc = finance_courses.get(course.stepik_course_id, {})
        pc = per_course_community.get(sid, {})
        subs = sub_totals.get(course.id, {"total": 0, "correct": 0})
        courses_list.append({
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
            "price": fc.get("price"),
            "income": fc.get("income"),
            "published_at": course.published_at.isoformat() if course.published_at else None,
            "enrollment_count": enroll_counts.get(course.id, 0),
            "submissions_total": subs["total"],
            "submissions_correct": subs["correct"],
            "comments_count": pc.get("comments", 0),
            "reviews_count": pc.get("reviews_count", 0),
            "average_rating": pc.get("average_rating", 0),
        })
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
        }
    }
