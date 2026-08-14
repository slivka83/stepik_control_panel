import asyncio
import time as time_mod
from datetime import UTC

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.sync as sync_mod
from app.api.auth import get_user
from app.database import get_db
from app.models import FinancialSnapshot, User

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status")
async def sync_status(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    await sync_mod.ensure_state_loaded()
    result = await db.execute(select(FinancialSnapshot).limit(1))
    snap = result.scalar_one_or_none()
    last_sync = None
    if snap is not None:
        # Колонка в PG — timestamp without time zone, значение в ней UTC (naive).
        # Без явного смещения фронтенд трактует строку как локальное время.
        updated = snap.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        last_sync = updated.isoformat()

    remaining = 0
    if sync_mod._last_sync_completed_at > 0:
        elapsed = sync_mod._last_sync_completed_at + sync_mod.SYNC_COOLDOWN_SECONDS - time_mod.time()
        remaining = max(0, int(elapsed))

    return {
        "in_progress": sync_mod._sync_in_progress,
        "progress": sync_mod._sync_progress,
        "step": sync_mod._sync_step,
        "last_sync": last_sync,
        "last_error": sync_mod._last_sync_error,
        "cooldown_remaining_seconds": remaining,
    }


@router.post("")
async def trigger_sync(
    force: bool = False,
    user: User = Depends(get_user),
):
    await sync_mod.ensure_state_loaded()
    if sync_mod._sync_in_progress:
        return {"status": "already_in_progress"}
    if not force and not sync_mod.can_sync():
        remaining = int(sync_mod.SYNC_COOLDOWN_SECONDS - (time_mod.time() - sync_mod._last_sync_completed_at))
        return {"status": "cooldown", "cooldown_remaining_seconds": max(0, remaining)}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, sync_mod.sync_all_sync, force, user.id)
    return {"status": "sync_started"}
