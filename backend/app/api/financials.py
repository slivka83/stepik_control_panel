from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.database import get_db
from app.models import FinancialSnapshot, User

router = APIRouter(prefix="/api/financials", tags=["financials"])


@router.get("")
async def get_financials(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
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
            "courses": [],
            "recent_payments": [],
        }
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
    return data
