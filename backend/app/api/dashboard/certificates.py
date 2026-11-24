"""Certificates analytics: monthly/yearly/per-course aggregates + totals.

Reads the mart_certificates view (rebuilt by transform_certificates from
raw_certificate): course, user_id, year/month and type ('distinction') are
denormalized at transform time — the API never touches raw_*. «С отличием» =
type == 'distinction', «Обычные» = остальные. The split mirrors the
certificates chart on the Activities page (dark = total, light = regular,
overlap = distinction).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import (
    PeriodAggregator,
    course_label,
    format_month_label,
    get_courses_for_user,
    in_clause,
)
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import User

router = APIRouter()


def _empty() -> dict:
    return {
        "months": [],
        "years": [],
        "by_course": [],
        "totals": {"certificates": 0, "students": 0, "distinction": 0, "regular": 0},
    }


@router.get("/certificates/stats")
async def get_certificates_stats(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    courses, _ = await get_courses_for_user(db, user, parse_course_ids(course_ids))
    selected_stepik = {c.stepik_course_id for c in courses}
    if not selected_stepik:
        return _empty()

    placeholders, params = in_clause(selected_stepik, "cid")
    rows = await db.execute(
        text(
            "SELECT stepik_course_id, user_id, year, month, type "
            f"FROM mart_certificates WHERE stepik_course_id IN ({placeholders})"
        ),
        params,
    )

    agg = PeriodAggregator({"distinction": 0})
    for cid, user_id, year, month, ctype in rows:
        agg.add(
            year=year,
            month=month,
            course_id=cid,
            student_id=user_id,
            distinction=int(ctype == "distinction"),
        )

    months = [
        {
            "month": format_month_label(m["month"], m["year"]),
            "year": m["year"],
            "month_num": m["month"],
            "students": m["students"],
            "total": m["total"],
            "distinction": m["distinction"],
            "regular": m["total"] - m["distinction"],
        }
        for m in agg.months()
    ]

    years = [
        {
            "year": y["year"],
            "students": y["students"],
            "total": y["total"],
            "distinction": y["distinction"],
            "regular": y["total"] - y["distinction"],
        }
        for y in agg.years()
    ]

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    by_course = []
    for c in agg.courses():
        course_uuid, title = course_label(course_by_stepik, c["stepik_course_id"])
        by_course.append(
            {
                "course_id": course_uuid,
                "stepik_course_id": c["stepik_course_id"],
                "title": title,
                "students": c["students"],
                "total": c["total"],
                "distinction": c["distinction"],
                "regular": c["total"] - c["distinction"],
            }
        )

    t = agg.totals()
    totals = {
        "certificates": t["total"],
        "students": t["students"],
        "distinction": t["distinction"],
        "regular": t["total"] - t["distinction"],
    }

    return {"months": months, "years": years, "by_course": by_course, "totals": totals}
