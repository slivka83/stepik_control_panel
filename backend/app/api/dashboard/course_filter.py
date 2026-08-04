"""Course-filtered recomputation of snapshot-backed dashboard data.

The financial snapshot is a single global JSON document: months/summary are
aggregates across ALL courses. When the user selects a subset of courses
(?course_ids=u1,u2), these aggregates are recomputed from the per-payment
records (recent_payments[i].raw) and per-course community data instead of
being read verbatim from the snapshot.

Mirrors the aggregation formulas in transform_financials/transform_community,
so the filtered view keeps the same shape as the unfiltered snapshot.
"""

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MONTH_NAMES, UTM_SOURCE_LABELS


def parse_course_ids(raw: str | None) -> list[uuid.UUID] | None:
    """Parse comma-joined ?course_ids=u1,u2 into a UUID list.

    None (param absent) → None = no filter. Present-but-empty (or only
    garbage) → [] = explicitly nothing selected (empty dashboard).
    """
    if raw is None:
        return None
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(uuid.UUID(part))
        except (ValueError, TypeError):
            continue
    return ids


def _int_or_none(val):
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


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


def _month_tuple(time_raw) -> tuple[int, int] | None:
    try:
        dt = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.year, dt.month


def _filtered_payments(data: dict, selected_stepik_ids: set[int]) -> list[dict]:
    """raw_course_benefit objects restricted to the selected courses."""
    payments = []
    for p in data.get("recent_payments", []) or []:
        raw = p.get("raw") if isinstance(p, dict) else None
        if not isinstance(raw, dict):
            continue
        cid = _int_or_none(raw.get("course"))
        if cid is not None and cid in selected_stepik_ids:
            payments.append(raw)
    return payments


def filter_financials(data: dict, selected_stepik_ids: set[int]) -> dict:
    """Recompute summary/months/courses/promos/utms/recent_payments from
    per-payment records restricted to the selected courses.
    """
    payments = _filtered_payments(data, selected_stepik_ids)

    months_map: dict[tuple[int, int], dict] = {}
    course_stats: dict[int, dict] = {}
    promo_stats: dict[str, dict] = {}
    utm_stats: dict[str, dict] = {}

    for b in payments:
        cid = b.get("course")
        status = b.get("status", "")
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        time_raw = b.get("time", "")

        cs = course_stats.setdefault(
            cid,
            {"course_id": cid, "payments": 0, "turnover": 0.0, "income": 0.0, "refunds": 0.0},
        )
        cs["payments"] += 1
        if status == "refunded":
            cs["refunds"] += abs(amount)
            cs["turnover"] -= payment_amount
        else:
            cs["turnover"] += payment_amount
            cs["income"] += amount

        ym = _month_tuple(time_raw)
        if ym:
            ms = months_map.setdefault(
                ym,
                {
                    "year": ym[0],
                    "month_num": ym[1],
                    "turnover": 0.0,
                    "income": 0.0,
                    "refunds": 0.0,
                    "payments_count": 0,
                    "refunds_count": 0,
                },
            )
            ms["payments_count"] += 1
            if status == "refunded":
                ms["refunds"] += abs(amount)
                ms["refunds_count"] += 1
                ms["turnover"] -= payment_amount
            else:
                ms["turnover"] += payment_amount
                ms["income"] += amount

        code = b.get("promo_code")
        if code is not None:
            ps = promo_stats.setdefault(
                code,
                {
                    "promo_code": code,
                    "payments": 0,
                    "turnover": 0.0,
                    "income": 0.0,
                    "refunds": 0.0,
                    "last_used": "",
                },
            )
            ps["payments"] += 1
            if status == "refunded":
                ps["refunds"] += abs(amount)
            else:
                ps["turnover"] += payment_amount
                ps["income"] += amount
            if time_raw > ps["last_used"]:
                ps["last_used"] = time_raw

        last_utm = b.get("last_course_click_utm") or {}
        source = last_utm.get("utm_source")
        if source:
            label = UTM_SOURCE_LABELS.get(source, source)
            us = utm_stats.setdefault(
                label,
                {
                    "utm_source": label,
                    "payments": 0,
                    "turnover": 0.0,
                    "income": 0.0,
                    "refunds": 0.0,
                    "last_used": "",
                },
            )
            us["payments"] += 1
            if status == "refunded":
                us["refunds"] += abs(amount)
            else:
                us["turnover"] += payment_amount
                us["income"] += amount
            if time_raw > us["last_used"]:
                us["last_used"] = time_raw

    months = []
    for y, m in sorted(months_map):
        ms = months_map[(y, m)]
        months.append(
            {
                "month": f"{MONTH_NAMES.get(m, str(m))} {y}",
                "year": y,
                "month_num": m,
                "turnover": ms["turnover"],
                "income": ms["income"],
                "refunds": ms["refunds"],
                "payments_count": ms["payments_count"],
                "refunds_count": ms["refunds_count"],
            }
        )

    total_turnover = sum(m["turnover"] for m in months)
    total_income = sum(m["income"] for m in months)
    total_refunds = sum(m["refunds"] for m in months)
    total_payments = sum(m["payments_count"] for m in months)
    total_refunds_count = sum(m["refunds_count"] for m in months)

    now = datetime.now(UTC)
    current_month_turnover = 0.0
    current_month_income = 0.0
    current_month_payments = 0
    for m in months:
        if m["year"] == now.year and m["month_num"] == now.month:
            current_month_turnover = m["turnover"]
            current_month_income = m["income"]
            current_month_payments = m["payments_count"]

    orig_courses = {
        c.get("course_id"): c for c in data.get("courses", []) or [] if isinstance(c, dict)
    }
    courses = []
    for cid, cs in course_stats.items():
        o = orig_courses.get(cid, {})
        courses.append(
            {
                "course_id": cid,
                "title": o.get("title", f"Курс #{cid}"),
                "price": o.get("price"),
                "turnover": round(cs["turnover"], 2),
                "income": round(cs["income"], 2),
                "refunds": round(cs["refunds"], 2),
                "payments": cs["payments"],
            }
        )
    courses.sort(key=lambda x: x["turnover"], reverse=True)

    selected_ids = selected_stepik_ids
    recent_payments = [
        p
        for p in data.get("recent_payments", []) or []
        if _int_or_none(p.get("raw", {}).get("course")) in selected_ids
    ]

    return {
        "summary": {
            "total_turnover": total_turnover,
            "total_income": total_income,
            "total_refunds": total_refunds,
            "total_payments": total_payments,
            "total_refunds_count": total_refunds_count,
            "net_income": total_income - total_refunds,
            "current_month_turnover": current_month_turnover,
            "current_month_income": current_month_income,
            "current_month_payments": current_month_payments,
        },
        "months": months,
        "courses": courses,
        "promos": sorted(promo_stats.values(), key=lambda x: x["last_used"], reverse=True),
        "utms": sorted(utm_stats.values(), key=lambda x: x["last_used"], reverse=True),
        "recent_payments": recent_payments,
    }


async def _build_step_course_map(db: AsyncSession) -> dict[int, int]:
    r = await db.execute(
        text(
            """
            SELECT DISTINCT s.step_id, sec.course
            FROM raw_step s
            JOIN raw_unit u ON u.lesson_id = s.lesson
            JOIN raw_section sec ON sec.section_id = u.section_id
            WHERE s.step_id IS NOT NULL AND sec.course IS NOT NULL
        """
        )
    )
    result = {}
    for step_id, course in r:
        sid = _int_or_none(step_id)
        cid = _int_or_none(course)
        if sid is not None and cid is not None:
            result[sid] = cid
    return result


async def filter_community(db: AsyncSession, data: dict, selected_stepik_ids: set[int]) -> dict:
    """Recompute community stats for the selected courses.

    Totals/rating come from the per-course section of the snapshot; the
    monthly comment/solution series are rebuilt from raw_comment via the
    step→course map (the snapshot only stores the global series).
    """
    community = data.get("community", {}) or {}
    per_course = community.get("per_course", {}) or {}
    selected_keys = {str(cid) for cid in selected_stepik_ids}

    total_reviews = 0
    ratings = []
    for key, info in per_course.items():
        if key not in selected_keys or not isinstance(info, dict):
            continue
        total_reviews += int(info.get("reviews_count", 0) or 0)
        avg = info.get("average_rating")
        if avg:
            ratings.append(float(avg))
    average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    step_course = await _build_step_course_map(db)
    comments_monthly = {}
    solutions_monthly = {}
    total_comments = 0
    total_solutions = 0
    rows = await db.execute(text("SELECT _raw_json FROM raw_comment"))
    for (raw_json,) in rows:
        cm = _parse_json(raw_json)
        if not cm:
            continue
        time_raw = cm.get("time")
        target = _int_or_none(cm.get("target"))
        if not time_raw or target is None:
            continue
        cid = step_course.get(target)
        if cid is None or cid not in selected_stepik_ids:
            continue
        ym = _month_tuple(time_raw)
        if not ym:
            continue
        key = f"{ym[0]}-{ym[1]:02d}"
        thread = cm.get("thread", "")
        is_solution = "solution" in thread if thread else False
        total_comments += 1
        comments_monthly[key] = comments_monthly.get(key, 0) + 1
        if is_solution:
            total_solutions += 1
            solutions_monthly[key] = solutions_monthly.get(key, 0) + 1

    return {
        "average_rating": average_rating,
        "total_reviews": total_reviews,
        "total_comments": total_comments,
        "comments_monthly": comments_monthly,
        "total_solutions": total_solutions,
        "solutions_monthly": solutions_monthly,
        "per_course": {k: v for k, v in per_course.items() if k in selected_keys},
    }


async def filter_steps_average_grade(db: AsyncSession, selected_stepik_ids: set[int]) -> float:
    """Average step grade (votes-weighted) over steps of selected courses."""
    step_course = await _build_step_course_map(db)
    if not step_course:
        return 0.0
    rows = await db.execute(text("SELECT step_id, _raw_json FROM raw_step"))
    votes_total = 0
    votes_count = 0
    for step_id, raw_json in rows:
        sid = _int_or_none(step_id)
        if sid is None or step_course.get(sid) not in selected_stepik_ids:
            continue
        rc = _parse_json(raw_json)
        if not rc:
            continue
        ng = rc.get("num_grades")
        if not isinstance(ng, list):
            continue
        for i, cnt in enumerate(ng):
            try:
                c = int(cnt)
            except (TypeError, ValueError):
                continue
            votes_total += c * (i + 1)
            votes_count += c
    return round(votes_total / votes_count, 2) if votes_count else 0.0
