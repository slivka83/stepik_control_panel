"""Course-filtered recomputation of snapshot-backed dashboard data.

The financial snapshot is a single global JSON document: months/summary are
aggregates across ALL courses. When the user selects a subset of courses
(?course_ids=u1,u2), these aggregates are recomputed from the per-payment
records (recent_payments[i].raw) and per-course community data instead of
being read verbatim from the snapshot.

Mirrors the aggregation formulas in transform_financials/transform_community,
so the filtered view keeps the same shape as the unfiltered snapshot.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dashboard.common import in_clause, votes_weighted_grade
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


def _float_or_zero(val) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _month_tuple(time_raw) -> tuple[int, int] | None:
    try:
        dt = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.year, dt.month


def _apply_payment(
    bucket: dict,
    status: str,
    amount: float,
    payment_amount: float,
    count_key: str = "payments",
    refund_count_key: str | None = None,
) -> None:
    """Accumulate one payment into an aggregate bucket (course/month/promo/utm).

    Refunds increase `refunds` (positive), decrease turnover by the paid amount
    and add the refunded amount back to income — same as transform_financials.
    """
    bucket[count_key] += 1
    if status == "refunded":
        bucket["refunds"] += abs(amount)
        if refund_count_key:
            bucket[refund_count_key] += 1
        bucket["turnover"] -= payment_amount
        bucket["income"] += amount
    else:
        bucket["turnover"] += payment_amount
        bucket["income"] += amount


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


def filter_financials(
    data: dict, selected_stepik_ids: set[int], course_meta: dict[int, dict] | None = None
) -> dict:
    """Recompute summary/months/courses/promos/utms/recent_payments from
    per-payment records restricted to the selected courses.

    `course_meta` (stepik id → {title, price}) fills the course table for
    courses that are not in the snapshot yet (fresh selection/first sync).
    """
    payments = _filtered_payments(data, selected_stepik_ids)

    months_map: dict[tuple[int, int], dict] = {}
    promo_stats: dict[str, dict] = {}
    utm_stats: dict[str, dict] = {}
    orig_courses: dict[int, dict] = {}
    for c in data.get("courses", []) or []:
        if not isinstance(c, dict):
            continue
        cid = _int_or_none(c.get("course_id"))
        if cid is not None:
            orig_courses[cid] = c
    meta = course_meta or {}
    # Все выбранные курсы остаются в таблице «По курсам», даже без платежей:
    # иначе фильтр «все курсы» и «без фильтра» давали разные наборы строк.
    course_stats: dict[int, dict] = {
        cid: {
            "course_id": cid,
            "title": (
                (orig_courses.get(cid) or {}).get("title")
                or (meta.get(cid) or {}).get("title")
                or f"Курс #{cid}"
            ),
            "price": (orig_courses.get(cid) or {}).get("price")
            or (meta.get(cid) or {}).get("price"),
            "payments": 0,
            "turnover": 0.0,
            "income": 0.0,
            "refunds": 0.0,
        }
        for cid in selected_stepik_ids
    }

    for b in payments:
        cid = _int_or_none(b.get("course"))
        status = b.get("status", "")
        amount = _float_or_zero(b.get("amount"))
        payment_amount = _float_or_zero(b.get("payment_amount"))
        time_raw = b.get("time") or ""
        if not isinstance(time_raw, str):
            time_raw = str(time_raw)

        cs = course_stats[cid]
        _apply_payment(cs, status, amount, payment_amount)

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
            _apply_payment(ms, status, amount, payment_amount, "payments_count", "refunds_count")

        code = b.get("promo_code")
        if code:
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
            _apply_payment(ps, status, amount, payment_amount)
            if time_raw > ps["last_used"]:
                ps["last_used"] = time_raw

        last_utm = b.get("last_course_click_utm")
        source = last_utm.get("utm_source") if isinstance(last_utm, dict) else None
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
            _apply_payment(us, status, amount, payment_amount)
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

    # Итоги считаем по всем отфильтрованным платежам, а не по сумме months:
    # платёж с нераспознаваемой датой не попадает в месяцы, но обязан попасть
    # в общий итог — иначе «Оборот» фильтра расходится с таблицей курсов.
    totals = {"payments": 0, "turnover": 0.0, "income": 0.0, "refunds": 0.0}
    total_refunds_count = 0
    for b in payments:
        status = b.get("status", "")
        amount = _float_or_zero(b.get("amount"))
        payment_amount = _float_or_zero(b.get("payment_amount"))
        _apply_payment(totals, status, amount, payment_amount)
        if status == "refunded":
            total_refunds_count += 1
    total_turnover = totals["turnover"]
    total_income = totals["income"]
    total_refunds = totals["refunds"]
    total_payments = totals["payments"]

    now = datetime.now(UTC)
    current_month_turnover = 0.0
    current_month_income = 0.0
    current_month_payments = 0
    for m in months:
        if m["year"] == now.year and m["month_num"] == now.month:
            current_month_turnover = m["turnover"]
            current_month_income = m["income"]
            current_month_payments = m["payments_count"]

    courses = [
        {
            "course_id": cid,
            "title": cs["title"],
            "price": cs["price"],
            "turnover": round(cs["turnover"], 2),
            "income": round(cs["income"], 2),
            "refunds": round(cs["refunds"], 2),
            "payments": cs["payments"],
        }
        for cid, cs in course_stats.items()
    ]
    courses.sort(key=lambda x: x["turnover"], reverse=True)

    recent_payments = [
        p
        for p in data.get("recent_payments", []) or []
        if isinstance(p, dict)
        and isinstance(p.get("raw"), dict)
        and _int_or_none(p["raw"].get("course")) in selected_stepik_ids
    ]
    return {
        "summary": {
            "total_turnover": total_turnover,
            "total_income": total_income,
            "total_refunds": total_refunds,
            "total_payments": total_payments,
            "total_refunds_count": total_refunds_count,
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


async def published_solutions_stats(
    db: AsyncSession, selected_stepik_ids: set[int]
) -> tuple[dict[tuple[int, int], int], dict[int, int], dict[int, int]]:
    """Count of published solutions (comments in solution threads) grouped by
    month `(year, month)`, by year, and by stepik course id.

    Reads the mart_comments view: `is_solution` is precomputed by
    transform_comments from `_raw_json.thread` containing "solution"; course
    attribution and month/year are denormalized in the view. Returns
    `(monthly, yearly, per_course)`.
    """
    monthly: dict[tuple[int, int], int] = {}
    yearly: dict[int, int] = {}
    per_course: dict[int, int] = {}
    if not selected_stepik_ids:
        return monthly, yearly, per_course
    placeholders, params = in_clause(selected_stepik_ids, "cid")
    rows = await db.execute(
        text(
            "SELECT stepik_course_id, year, month, COUNT(*) FROM mart_comments "
            f"WHERE is_solution = TRUE AND stepik_course_id IN ({placeholders}) "
            "GROUP BY stepik_course_id, year, month"
        ),
        params,
    )
    for cid, year, month, count in rows:
        if year is None or month is None:
            continue
        monthly[(year, month)] = monthly.get((year, month), 0) + count
        yearly[year] = yearly.get(year, 0) + count
        per_course[cid] = per_course.get(cid, 0) + count
    return monthly, yearly, per_course


async def filter_community(db: AsyncSession, data: dict, selected_stepik_ids: set[int]) -> dict:
    """Recompute community stats for the selected courses.

    Totals/rating come from the per-course section of the snapshot; the
    monthly comment/solution series are rebuilt from mart_comments (course and
    year/month are denormalized in the view — no step→course map needed).
    """
    community = data.get("community")
    if not isinstance(community, dict):
        community = {}
    per_course = community.get("per_course")
    if not isinstance(per_course, dict):
        per_course = {}
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

    comments_monthly = {}
    solutions_monthly = {}
    total_comments = 0
    total_solutions = 0
    if selected_stepik_ids:
        placeholders, params = in_clause(selected_stepik_ids, "cid")
        rows = await db.execute(
            text(
                "SELECT year, month, is_solution, COUNT(*) FROM mart_comments "
                f"WHERE stepik_course_id IN ({placeholders}) "
                "GROUP BY year, month, is_solution"
            ),
            params,
        )
        for year, month, is_solution, count in rows:
            if year is None or month is None:
                continue
            # Published solutions are counted separately (total_solutions /
            # solutions_monthly); plain "comments" excludes them.
            if is_solution:
                total_solutions += count
                key = f"{year}-{month:02d}"
                solutions_monthly[key] = solutions_monthly.get(key, 0) + count
                continue
            key = f"{year}-{month:02d}"
            total_comments += count
            comments_monthly[key] = comments_monthly.get(key, 0) + count

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
    """Average step grade (votes-weighted) over steps of selected courses.

    Reads mart_steps (grade/grade_votes precomputed by transform_steps from
    raw_step._raw_json.num_grades).
    """
    if not selected_stepik_ids:
        return 0.0
    placeholders, params = in_clause(selected_stepik_ids, "cid")
    rows = await db.execute(
        text(
        "SELECT grade, grade_votes FROM mart_steps "
        f"WHERE stepik_course_id IN ({placeholders})"
        ),
        params,
    )
    return votes_weighted_grade(rows)
