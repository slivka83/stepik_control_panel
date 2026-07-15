from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.models import Course, StudentEnrollment, FinancialTransaction
from app.api.auth import get_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpi")
async def get_kpi(user=Depends(get_user), db: AsyncSession = Depends(get_db)):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {
            "total_revenue": 0,
            "total_students": 0,
            "certificates_issued": 0,
            "total_steps": 0,
            "courses_count": 0,
        }

    students_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(StudentEnrollment.course_id.in_(course_ids))
    )
    total_students = students_result.scalar() or 0

    revenue_result = await db.execute(
        select(func.sum(FinancialTransaction.amount))
        .where(
            FinancialTransaction.course_id.in_(course_ids),
            FinancialTransaction.is_refund == False,
            FinancialTransaction.transaction_date >= datetime.now(timezone.utc).replace(day=1),
        )
    )
    total_revenue = float(revenue_result.scalar() or 0)

    certs_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.certificate_issued == True,
        )
    )
    certificates_issued = certs_result.scalar() or 0

    return {
        "total_revenue": total_revenue,
        "total_students": total_students,
        "certificates_issued": certificates_issued,
        "total_steps": 0,
        "courses_count": len(courses),
    }


@router.get("/cohorts")
async def get_cohorts(user=Depends(get_user), db: AsyncSession = Depends(get_db)):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}

    now = datetime.now(timezone.utc)
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
async def get_revenue(user=Depends(get_user), db: AsyncSession = Depends(get_db)):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {"months": []}

    result = await db.execute(
        select(
            func.date_trunc("month", FinancialTransaction.transaction_date).label("month"),
            func.sum(FinancialTransaction.amount).label("revenue"),
        )
        .where(
            FinancialTransaction.course_id.in_(course_ids),
            FinancialTransaction.is_refund == False,
        )
        .group_by(func.date_trunc("month", FinancialTransaction.transaction_date))
        .order_by(func.date_trunc("month", FinancialTransaction.transaction_date))
    )
    rows = result.all()

    return {
        "months": [
            {"month": row.month.isoformat(), "revenue": float(row.revenue)}
            for row in rows
        ]
    }
