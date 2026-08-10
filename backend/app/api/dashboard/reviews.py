"""Reviews analytics: monthly/yearly/per-course aggregates + totals.

Reads raw_course_review (course on the row, no step→course map needed).
create_date/score are parsed from _raw_json (the SQLite fixture stores them in
columns, live PG keeps the raw layer as TEXT/jsonb too — reading _raw_json
works for both). Students are distinct numeric users (non-numeric values —
OAuth client names — are skipped). avg_score is the mean review score per
group (0 when no scores).
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import format_month_label, get_courses_for_user, json_field
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import User

router = APIRouter()


def _int_or_none(val):
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float_or_none(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _month_tuple(time_raw) -> tuple[int, int] | None:
    try:
        dt = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.year, dt.month


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
    params = {f"cid{i}": str(cid) for i, cid in enumerate(stepik_ids)}
    rows = await db.execute(
        text(f"SELECT \"user\", course, _raw_json FROM raw_course_review WHERE course IN ({placeholders})"),
        params,
    )

    month_buckets: dict[tuple[int, int], dict] = {}
    month_students: dict[tuple[int, int], set] = {}
    year_students: dict[int, set] = {}
    course_stats: dict[int, dict] = {}
    course_students: dict[int, set] = {}
    all_students: set[int] = set()

    for user_raw, course_raw, raw_json in rows:
        data = raw_json if isinstance(raw_json, dict) else _parse_json(raw_json)
        if not data:
            continue
        ym = _month_tuple(json_field(data, "create_date"))
        if not ym:
            continue

        user_id = _int_or_none(user_raw)
        if user_id is None:
            user_id = _int_or_none(json_field(data, "user"))

        cid = _int_or_none(course_raw)
        if cid is None:
            cid = _int_or_none(json_field(data, "course"))
        if cid is None or cid not in selected_stepik:
            continue

        score = _float_or_none(json_field(data, "score"))

        bucket = month_buckets.setdefault(ym, {"total": 0, "score_sum": 0.0, "score_count": 0})
        bucket["total"] += 1
        if score is not None:
            bucket["score_sum"] += score
            bucket["score_count"] += 1

        if user_id is not None:
            month_students.setdefault(ym, set()).add(user_id)
            year_students.setdefault(ym[0], set()).add(user_id)
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


def _parse_json(raw) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None
