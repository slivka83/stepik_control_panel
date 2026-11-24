"""Reviews analytics: monthly/yearly/per-course aggregates + totals.

Reads the mart_reviews view (rebuilt by transform_reviews from
raw_course_review): course, user_id, year/month and score are denormalized at
transform time — the API never touches raw_*. Students are distinct numeric
users (non-numeric values — OAuth client names — are skipped by the
transform). avg_score is the mean review score per group (0 when no scores).
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
        "totals": {"reviews": 0, "students": 0, "avg_score": 0},
    }


def _avg_score(score_sum: float, score_count: int) -> float:
    return round(score_sum / score_count, 2) if score_count else 0


@router.get("/reviews/stats")
async def get_reviews_stats(
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
            "SELECT stepik_course_id, user_id, year, month, score "
            f"FROM mart_reviews WHERE stepik_course_id IN ({placeholders})"
        ),
        params,
    )

    agg = PeriodAggregator({"score_sum": 0.0, "score_count": 0})
    for cid, user_id, year, month, score in rows:
        has_score = score is not None
        agg.add(
            year=year,
            month=month,
            course_id=cid,
            student_id=user_id,
            score_sum=score if has_score else 0,
            score_count=1 if has_score else 0,
        )

    months = [
        {
            "month": format_month_label(m["month"], m["year"]),
            "year": m["year"],
            "month_num": m["month"],
            "students": m["students"],
            "total": m["total"],
            "avg_score": _avg_score(m["score_sum"], m["score_count"]),
        }
        for m in agg.months()
    ]

    years = [
        {
            "year": y["year"],
            "students": y["students"],
            "total": y["total"],
            "avg_score": _avg_score(y["score_sum"], y["score_count"]),
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
                "avg_score": _avg_score(c["score_sum"], c["score_count"]),
            }
        )

    t = agg.totals()
    totals = {
        "reviews": t["total"],
        "students": t["students"],
        "avg_score": _avg_score(t["score_sum"], t["score_count"]),
    }

    return {"months": months, "years": years, "by_course": by_course, "totals": totals}
