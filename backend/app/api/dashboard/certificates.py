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
    params = {f"cid{i}": cid for i, cid in enumerate(stepik_ids)}
    rows = await db.execute(
        text(
            "SELECT stepik_course_id, user_id, year, month, type "
            f"FROM mart_certificates WHERE stepik_course_id IN ({placeholders})"
        ),
        params,
    )

    month_buckets: dict[tuple[int, int], dict] = {}
    month_students: dict[tuple[int, int], set] = {}
    year_students: dict[int, set] = {}
    course_stats: dict[int, dict] = {}
    course_students: dict[int, set] = {}
    all_students: set[int] = set()

    for cid, user_id, year, month, ctype in rows:
        if year is None or month is None:
            continue
        ym = (year, month)
        is_distinction = ctype == "distinction"

        bucket = month_buckets.setdefault(ym, {"total": 0, "distinction": 0})
        bucket["total"] += 1
        if is_distinction:
            bucket["distinction"] += 1

        if user_id is not None:
            month_students.setdefault(ym, set()).add(user_id)
            year_students.setdefault(year, set()).add(user_id)
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
