from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.models import Course, StudentEnrollment, FinancialSnapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/alerts")
async def get_alerts(db: AsyncSession = Depends(get_db)):
    courses_result = await db.execute(select(Course))
    courses = courses_result.scalars().all()
    alerts = []

    for course in courses:
        certs_count_result = await db.execute(
            select(func.count(StudentEnrollment.id))
            .where(
                StudentEnrollment.course_id == course.id,
                StudentEnrollment.points_earned >= 100,
                StudentEnrollment.certificate_issued == False,
            )
        )
        certs_pending = certs_count_result.scalar() or 0
        if certs_pending > 0:
            alerts.append({
                "type": "warning",
                "message": f"{certs_pending} студентов набрали проходной балл, но не получили сертификат",
                "link": f"https://stepik.org/course/{course.stepik_course_id}/certificates",
                "link_text": "Открыть на Stepik",
            })

        low_score_result = await db.execute(
            select(func.count(StudentEnrollment.id))
            .where(
                StudentEnrollment.course_id == course.id,
                StudentEnrollment.points_earned == 0,
            )
        )
        low_score = low_score_result.scalar() or 0
        if low_score > 0 and low_score > 10:
            alerts.append({
                "type": "error",
                "message": f"{low_score} студентов на курсе «{course.title}» не набрали ни одного балла",
                "link": f"https://stepik.org/course/{course.stepik_course_id}/students",
                "link_text": "Посмотреть на Stepik →",
            })

    return {"alerts": alerts}


@router.get("/kpi")
async def get_kpi(db: AsyncSession = Depends(get_db)):
    courses_result = await db.execute(select(Course))
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    students_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(StudentEnrollment.course_id.in_(course_ids))
    )
    total_students = students_result.scalar() or 0

    certs_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.certificate_issued == True,
        )
    )
    certificates_issued = certs_result.scalar() or 0

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    summary = snapshot.data.get("summary", {}) if snapshot else {}

    return {
        "total_revenue": summary.get("current_month_turnover", 0),
        "total_students": total_students,
        "certificates_issued": certificates_issued,
        "total_steps": 0,
        "courses_count": len(courses),
        "total_income": summary.get("total_income", 0),
        "net_income": summary.get("net_income", 0),
        "total_turnover": summary.get("total_turnover", 0),
        "total_refunds": summary.get("total_refunds", 0),
        "total_payments": summary.get("total_payments", 0),
    }


@router.get("/cohorts")
async def get_cohorts(db: AsyncSession = Depends(get_db)):
    courses_result = await db.execute(select(Course))
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cohorts = {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}

    for status, days_min, days_max in [
        ("active", 0, 7),
        ("passive", 8, 30),
        ("fading", 31, 90),
        ("sleeping", 91, 99999),
    ]:
        result = await db.execute(
            select(func.count(StudentEnrollment.id))
            .where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.last_viewed_at >= now - timedelta(days=days_max),
                StudentEnrollment.last_viewed_at < now - timedelta(days=days_min),
            )
        )
        cohorts[status] = result.scalar() or 0

    return cohorts


@router.get("/revenue")
async def get_revenue(db: AsyncSession = Depends(get_db)):
    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    months = snapshot.data.get("months", []) if snapshot else []
    return {"months": months}
