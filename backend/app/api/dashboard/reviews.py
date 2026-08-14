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
from app.api.dashboard.common import format_month_label, get_courses_for_user
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


def _round2(val: float) -> float:
    return round(val, 2)


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

    stepik_ids = sorted(selected_stepik)
    placeholders = ", ".join(f":cid{i}" for i in range(len(stepik_ids)))
    params = {f"cid{i}": cid for i, cid in enumerate(stepik_ids)}
    rows = await db.execute(
        text(
            "SELECT stepik_course_id, user_id, year, month, score "
            f"FROM mart_reviews WHERE stepik_course_id IN ({placeholders})"
        ),
        params,
    )

    month_buckets: dict[tuple[int, int], dict] = {}
    month_students: dict[tuple[int, int], set] = {}
    year_students: dict[int, set] = {}
    course_stats: dict[int, dict] = {}
    course_students: dict[int, set] = {}
    all_students: set[int] = set()

    for cid, user_id, year, month, score in rows:
        if year is None or month is None:
            continue
        ym = (year, month)

        bucket = month_buckets.setdefault(ym, {"total": 0, "score_sum": 0.0, "score_count": 0})
        bucket["total"] += 1
        if score is not None:
            bucket["score_sum"] += score
            bucket["score_count"] += 1

        if user_id is not None:
            month_students.setdefault(ym, set()).add(user_id)
            year_students.setdefault(year, set()).add(user_id)
            course_students.setdefault(cid, set()).add(user_id)
            all_students.add(user_id)

        cstats = course_stats.setdefault(cid, {"stepik_course_id": cid, "total": 0, "score_sum": 0.0, "score_count": 0})
        cstats["total"] += 1
        if score is not None:
            cstats["score_sum"] += score
            cstats["score_count"] += 1

    months = []
    for (y, m) in sorted(month_buckets):
        b = month_buckets[(y, m)]
        months.append(
            {
                "month": format_month_label(m, y),
                "students": len(month_students.get((y, m), ())),
                "total": b["total"],
                "avg_score": _round2(b["score_sum"] / b["score_count"]) if b["score_count"] else 0,
            }
        )

    year_aggs: dict[int, dict] = {}
    for (y, _m), b in month_buckets.items():
        agg = year_aggs.setdefault(y, {"year": y, "total": 0, "score_sum": 0.0, "score_count": 0})
        agg["total"] += b["total"]
        agg["score_sum"] += b["score_sum"]
        agg["score_count"] += b["score_count"]
    years = []
    for y in sorted(year_aggs):
        agg = year_aggs[y]
        years.append(
            {
                "year": y,
                "students": len(year_students.get(y, ())),
                "total": agg["total"],
                "avg_score": _round2(agg["score_sum"] / agg["score_count"]) if agg["score_count"] else 0,
            }
        )

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    by_course = []
    for cid in sorted(course_stats):
        st = course_stats[cid]
        course_obj = course_by_stepik.get(cid)
        by_course.append(
            {
                "course_id": str(course_obj.id) if course_obj else "",
                "stepik_course_id": cid,
                "title": course_obj.title if course_obj else "Unknown",
                "students": len(course_students.get(cid, ())),
                "total": st["total"],
                "avg_score": _round2(st["score_sum"] / st["score_count"]) if st["score_count"] else 0,
            }
        )

    total_scores = sum(b["score_sum"] for b in month_buckets.values())
    total_score_count = sum(b["score_count"] for b in month_buckets.values())

    totals = {
        "reviews": sum(b["total"] for b in month_buckets.values()),
        "students": len(all_students),
        "avg_score": _round2(total_scores / total_score_count) if total_score_count else 0,
    }

    return {"months": months, "years": years, "by_course": by_course, "totals": totals}
