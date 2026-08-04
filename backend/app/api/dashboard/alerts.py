"""Pending certificates and zero-score student alerts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import Course, StudentEnrollment, User

router = APIRouter()


@router.get("/alerts")
async def get_alerts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    _, course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    certs_pending_query = (
        select(
            Course.id,
            Course.title,
            Course.stepik_course_id,
            func.count(StudentEnrollment.id).label("count"),
        )
        .join(StudentEnrollment, Course.id == StudentEnrollment.course_id)
        .where(
            Course.id.in_(course_ids),
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
            Course.id.in_(course_ids),
            StudentEnrollment.points_earned == 0,
        )
        .group_by(Course.id, Course.title, Course.stepik_course_id)
        .having(func.count(StudentEnrollment.id) > 10)
    )
    low_score_result = await db.execute(low_score_query)
    low_score_rows = low_score_result.all()

    alerts = []
    for row in certs_rows:
        alerts.append(
            {
                "type": "warning",
                "message": f"{row.count} студентов набрали проходной балл, но не получили сертификат",
                "link": f"https://stepik.org/course/{row.stepik_course_id}/certificates",
                "link_text": "Открыть на Stepik",
            }
        )
    for row in low_score_rows:
        alerts.append(
            {
                "type": "error",
                "message": f"{row.count} студентов на курсе «{row.title}» не набрали ни одного балла",
                "link": f"https://stepik.org/course/{row.stepik_course_id}/students",
                "link_text": "Посмотреть на Stepik →",
            }
        )

    return {"alerts": alerts}
