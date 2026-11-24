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
        # Колонка в PG — timestamp with time zone, значение в ней UTC.
        # Фронтенд ожидает явное смещение +00:00, иначе трактует время как локальное.
        updated = snap.updated_at
        if updated is not None and updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        last_sync = updated.isoformat() if updated is not None else None

    remaining = 0
    if sync_mod._last_sync_completed_at > 0:
        elapsed = sync_mod._last_sync_completed_at + sync_mod.SYNC_COOLDOWN_SECONDS - time_mod.time()
        remaining = max(0, int(elapsed))

    return {
        "in_progress": sync_mod.status_in_progress(),
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
    # request_sync reserves the slot synchronously: the executor thread may not
    # have started yet, and a status poll right after POST must not see idle.
    result = sync_mod.request_sync(force)
    if result["status"] != "sync_started":
        return result
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, sync_mod.run_sync_thread, force, user.id)
    return result
