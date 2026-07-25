from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models import Course, StudentEnrollment, FinancialSnapshot, User
from app.api.auth import get_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/alerts")
async def get_alerts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    certs_pending_query = (
        select(
            Course.id,
            Course.title,
            Course.stepik_course_id,
            func.count(StudentEnrollment.id).label("count"),
        )
        .join(StudentEnrollment, Course.id == StudentEnrollment.course_id)
        .where(
            Course.user_id == user.id,
            StudentEnrollment.points_earned >= 100,
            StudentEnrollment.certificate_issued.is_(False),
        )
        .group_by(Course.id, Course.title, Course.stepik_course_id)
    )
    certs_result = await db.execute(certs_pending_query)
    certs_rows = certs_result.all()

    low_score_query = (
        select(
            Course.id,
            Course.title,
            Course.stepik_course_id,
            func.count(StudentEnrollment.id).label("count"),
        )
        .join(StudentEnrollment, Course.id == StudentEnrollment.course_id)
        .where(
            Course.user_id == user.id,
            StudentEnrollment.points_earned == 0,
        )
        .group_by(Course.id, Course.title, Course.stepik_course_id)
        .having(func.count(StudentEnrollment.id) > 10)
    )
    low_score_result = await db.execute(low_score_query)
    low_score_rows = low_score_result.all()

    alerts = []
    for row in certs_rows:
        alerts.append({
            "type": "warning",
            "message": f"{row.count} студентов набрали проходной балл, но не получили сертификат",
            "link": f"https://stepik.org/course/{row.stepik_course_id}/certificates",
            "link_text": "Открыть на Stepik",
        })
    for row in low_score_rows:
        alerts.append({
            "type": "error",
            "message": f"{row.count} студентов на курсе «{row.title}» не набрали ни одного балла",
            "link": f"https://stepik.org/course/{row.stepik_course_id}/students",
            "link_text": "Посмотреть на Stepik →",
        })

    return {"alerts": alerts}


@router.get("/kpi")
async def get_kpi(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {
            "total_revenue": 0, "total_students": 0, "certificates_issued": 0,
            "courses_count": 0, "courses_published": 0, "courses_unpublished": 0,
            "total_income": 0, "net_income": 0,
            "total_turnover": 0, "total_refunds": 0, "total_payments": 0,
            "current_month_turnover": 0,
            "total_comments": 0, "total_reviews": 0, "average_rating": 0,
        }

    students_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(StudentEnrollment.course_id.in_(course_ids))
    )
    total_students = students_result.scalar() or 0

    certs_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.certificate_issued.is_(True),
        )
    )
    certificates_issued = certs_result.scalar() or 0

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    summary = snapshot.data.get("summary", {}) if snapshot else {}
    community = snapshot.data.get("community", {}) if snapshot else {}

    return {
        "total_revenue": summary.get("current_month_income", 0),
        "total_students": total_students,
        "certificates_issued": certificates_issued,
        "courses_count": len(courses),
        "courses_published": sum(1 for c in courses if c.status == "Published"),
        "courses_unpublished": sum(1 for c in courses if c.status != "Published"),
        "total_income": summary.get("total_income", 0),
        "net_income": summary.get("net_income", 0),
        "total_turnover": summary.get("total_turnover", 0),
        "total_refunds": summary.get("total_refunds", 0),
        "total_refunds_count": summary.get("total_refunds_count", 0),
        "total_payments": summary.get("total_payments", 0),
        "current_month_turnover": summary.get("current_month_turnover", 0),
        "total_comments": community.get("total_comments", 0),
        "total_reviews": community.get("total_reviews", 0),
        "average_rating": community.get("average_rating", 0),
    }


@router.get("/cohorts")
async def get_cohorts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    cohorts = {}

    for label, days_min, days_max in [
        ("active", 0, 7),
        ("passive", 7, 30),
        ("fading", 30, 90),
    ]:
        result = await db.execute(
            select(func.count(StudentEnrollment.id))
            .where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.last_viewed_at >= now - timedelta(days=days_max),
                StudentEnrollment.last_viewed_at < now - timedelta(days=days_min),
            )
        )
        cohorts[label] = result.scalar() or 0

    sleeping_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.last_viewed_at < now - timedelta(days=90),
        )
    )
    cohorts["sleeping"] = sleeping_result.scalar() or 0

    return cohorts


@router.get("/revenue")
async def get_revenue(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    months = snapshot.data.get("months", []) if snapshot else []
    return {"months": months}
