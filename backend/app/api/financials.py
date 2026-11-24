import contextlib

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import filter_community, filter_financials, parse_course_ids
from app.database import get_db
from app.models import FinancialSnapshot, User

router = APIRouter(prefix="/api/financials", tags=["financials"])


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
                "total_refunds_count": 0,
                "current_month_turnover": 0,
                "current_month_income": 0,
                "current_month_payments": 0,
            },
            "months": [],
            "years": [],
            "courses": [],
            "promos": [],
            "utms": [],
            "recent_payments": [],
            "community": {},
        }
    snapshot_data = snapshot.data if isinstance(snapshot.data, dict) else {}
    if parsed is not None:
        courses, _ = await get_courses_for_user(db, user, parsed)
        selected_stepik_ids = {c.stepik_course_id for c in courses}
        course_meta = {c.stepik_course_id: {"title": c.title} for c in courses}
        data = filter_financials(snapshot_data, selected_stepik_ids, course_meta)
        data["community"] = await filter_community(db, snapshot_data, selected_stepik_ids)
    else:
        data = dict(snapshot_data)
    if not isinstance(data.get("summary"), dict):
        data["summary"] = {}
    for key in ("months", "courses", "promos", "utms", "recent_payments"):
        value = data.get(key)
        data[key] = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    year_stats: dict[int, dict] = {}
    for m in data["months"]:
        try:
            y = int(m.get("year"))
        except (TypeError, ValueError):
            continue
        agg = year_stats.setdefault(
            y, {"year": y, "payments_count": 0, "turnover": 0.0, "income": 0.0, "refunds": 0.0}
        )
        with contextlib.suppress(TypeError, ValueError):
            agg["payments_count"] += int(m.get("payments_count") or 0)
        for key in ("turnover", "income", "refunds"):
            with contextlib.suppress(TypeError, ValueError):
                agg[key] += float(m.get(key) or 0)
    data["years"] = [year_stats[y] for y in sorted(year_stats)]
    return data
