from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import filter_community, filter_financials, parse_course_ids
from app.database import get_db
from app.models import FinancialSnapshot, User

router = APIRouter(prefix="/api/financials", tags=["financials"])

DAYS_BACK = 30


def _build_daily_stats(recent_payments: list[dict]) -> list[dict]:
    """Aggregate payments by calendar day over the last DAYS_BACK days.

    Zeros-inclusive window (every calendar day is present), newest first.
    Mirrors the refunds formula from filter_financials/transform_financials.
    """
    today = datetime.now(UTC).date()
    start = today - timedelta(days=DAYS_BACK - 1)
    buckets: dict[str, dict] = {}
    for p in recent_payments or []:
        try:
            d = datetime.fromisoformat(str(p.get("time", "")).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        if d < start or d > today:
            continue
        b = buckets.setdefault(
            d.isoformat(),
            {
                "day": d.isoformat(),
                "payments_count": 0,
                "turnover": 0.0,
                "income": 0.0,
                "refunds": 0.0,
                "refunds_count": 0,
            },
        )
        b["payments_count"] += 1
        status = p.get("status", "")
        amount = float(p.get("amount", 0) or 0)
        payment_amount = float(p.get("payment_amount", 0) or 0)
        if status == "refunded":
            b["refunds"] += abs(amount)
            b["refunds_count"] += 1
            b["turnover"] -= payment_amount
        else:
            b["turnover"] += payment_amount
            b["income"] += amount

    days = []
    for offset in range(DAYS_BACK):
        d = (start + timedelta(days=offset)).isoformat()
        days.append(
            buckets.get(
                d,
                {
                    "day": d,
                    "payments_count": 0,
                    "turnover": 0.0,
                    "income": 0.0,
                    "refunds": 0.0,
                    "refunds_count": 0,
                },
            )
        )
    days.sort(key=lambda x: x["day"], reverse=True)
    return days


@router.get("")
async def get_financials(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    parsed = parse_course_ids(course_ids)
    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    if not snapshot:
        return {
            "summary": {
                "total_turnover": 0,
                "total_income": 0,
                "total_refunds": 0,
                "total_payments": 0,
                "net_income": 0,
            },
            "months": [],
            "years": [],
            "days": [],
            "courses": [],
            "recent_payments": [],
        }
    if parsed is not None:
        courses, _ = await get_courses_for_user(db, user, parsed)
        selected_stepik_ids = {c.stepik_course_id for c in courses}
        data = filter_financials(snapshot.data, selected_stepik_ids)
        data["community"] = await filter_community(db, snapshot.data, selected_stepik_ids)
    else:
        data = dict(snapshot.data)
    year_stats = {}
    for m in data.get("months", []):
        y = m.get("year")
        if y is None:
            continue
        agg = year_stats.setdefault(y, {"year": y, "payments_count": 0, "turnover": 0.0, "income": 0.0, "refunds": 0.0})
        agg["payments_count"] += int(m.get("payments_count", 0) or 0)
        agg["turnover"] += float(m.get("turnover", 0) or 0)
        agg["income"] += float(m.get("income", 0) or 0)
        agg["refunds"] += float(m.get("refunds", 0) or 0)
    data["years"] = [year_stats[y] for y in sorted(year_stats)]
    data["days"] = _build_daily_stats(data.get("recent_payments", []))
    return data
