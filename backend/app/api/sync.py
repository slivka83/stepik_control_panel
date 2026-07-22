import time as time_mod

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import FinancialSnapshot, User
from app.api.auth import get_user
import app.services.sync as sync_mod

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status")
async def sync_status(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FinancialSnapshot).limit(1))
    snap = result.scalar_one_or_none()
    last_sync = snap.updated_at.isoformat() if snap else None

    remaining = 0
    if sync_mod._last_sync_completed_at > 0:
        elapsed = sync_mod._last_sync_completed_at + sync_mod.SYNC_COOLDOWN_SECONDS - time_mod.time()
        remaining = max(0, int(elapsed))

    return {
        "in_progress": sync_mod._sync_in_progress,
        "last_sync": last_sync,
        "cooldown_remaining_seconds": remaining,
    }


@router.post("")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    force: bool = False,
    user: User = Depends(get_user),
):
    background_tasks.add_task(sync_mod.sync_all, force, user.id)
    return {"status": "sync_started"}
