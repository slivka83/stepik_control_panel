from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import FinancialSnapshot

router = APIRouter(prefix="/api/financials", tags=["financials"])


@router.get("")
async def get_financials(db: AsyncSession = Depends(get_db)):
    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    if not snapshot:
        return {
            "summary": {"total_turnover": 0, "total_income": 0, "total_refunds": 0, "total_payments": 0, "net_income": 0},
            "months": [], "courses": [], "recent_payments": [],
        }
    return snapshot.data
