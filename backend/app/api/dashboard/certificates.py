"""Certificates analytics: monthly/yearly/per-course aggregates + totals.

Reads raw_certificate (course_id on the row, no step→course map needed).
issue_date/type are parsed from _raw_json (the SQLite fixture has no such
columns; live PG stores the raw layer as TEXT/jsonb too). «С отличием» =
type == 'distinction', «Обычные» = остальные. The split mirrors the
certificates chart on the Activities page (dark = total, light = regular,
overlap = distinction).
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

    stepik_ids = sorted(selected_stepik)
    placeholders = ", ".join(f":cid{i}" for i in range(len(stepik_ids)))
    params = {f"cid{i}": str(cid) for i, cid in enumerate(stepik_ids)}
    rows = await db.execute(
        text(f"SELECT user_id, course_id, _raw_json FROM raw_certificate WHERE course_id IN ({placeholders})"),
        params,
    )

    month_buckets: dict[tuple[int, int], dict] = {}
    month_students: dict[tuple[int, int], set] = {}
    year_students: dict[int, set] = {}
    course_stats: dict[int, dict] = {}
    course_students: dict[int, set] = {}
    all_students: set[int] = set()

    for user_id_raw, course_id_raw, raw_json in rows:
        data = raw_json if isinstance(raw_json, dict) else _parse_json(raw_json)
        if not data:
            continue
        ym = _month_tuple(json_field(data, "issue_date"))
        if not ym:
            continue

        user_id = _int_or_none(user_id_raw)
        if user_id is None:
            user_id = _int_or_none(json_field(data, "user"))

        cid = _int_or_none(course_id_raw)
        if cid is None:
            cid = _int_or_none(json_field(data, "course"))
        if cid is None or cid not in selected_stepik:
            continue

        is_distinction = json_field(data, "type") == "distinction"

        bucket = month_buckets.setdefault(ym, {"total": 0, "distinction": 0})
        bucket["total"] += 1
        if is_distinction:
            bucket["distinction"] += 1

        if user_id is not None:
            month_students.setdefault(ym, set()).add(user_id)
            year_students.setdefault(ym[0], set()).add(user_id)
            course_students.setdefault(cid, set()).add(user_id)
            all_students.add(user_id)

        cstats = course_stats.setdefault(cid, {"stepik_course_id": cid, "total": 0, "distinction": 0})
        cstats["total"] += 1
        if is_distinction:
            cstats["distinction"] += 1

    months = []
    for (y, m) in sorted(month_buckets):
        b = month_buckets[(y, m)]
        total = b["total"]
        distinction = b["distinction"]
        months.append(
            {
                "month": format_month_label(m, y),
                "students": len(month_students.get((y, m), ())),
                "total": total,
                "distinction": distinction,
                "regular": total - distinction,
            }
        )

    year_aggs: dict[int, dict] = {}
    for (y, _m), b in month_buckets.items():
        agg = year_aggs.setdefault(y, {"year": y, "total": 0, "distinction": 0})
        agg["total"] += b["total"]
        agg["distinction"] += b["distinction"]
    years = []
    for y in sorted(year_aggs):
        agg = year_aggs[y]
        total = agg["total"]
        years.append(
            {
                "year": y,
                "students": len(year_students.get(y, ())),
                "total": total,
                "distinction": agg["distinction"],
                "regular": total - agg["distinction"],
            }
        )

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    by_course = []
    for cid in sorted(course_stats):
        st = course_stats[cid]
        course_obj = course_by_stepik.get(cid)
        total = st["total"]
        distinction = st["distinction"]
        by_course.append(
            {
                "course_id": str(course_obj.id) if course_obj else "",
                "stepik_course_id": cid,
                "title": course_obj.title if course_obj else "Unknown",
                "students": len(course_students.get(cid, ())),
                "total": total,
                "distinction": distinction,
                "regular": total - distinction,
            }
        )

    totals = {
        "certificates": sum(b["total"] for b in month_buckets.values()),
        "students": len(all_students),
        "distinction": sum(b["distinction"] for b in month_buckets.values()),
        "regular": sum(b["total"] - b["distinction"] for b in month_buckets.values()),
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
