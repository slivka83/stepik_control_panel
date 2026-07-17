from contextlib import asynccontextmanager
import logging
import asyncio
import time as time_mod

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import get_settings
from app.database import engine, Base, async_session
from app.api import auth, courses, dashboard, financials, sync
from app.services.token_refresh import refresh_user_tokens
from app.services.sync import sync_all
from app.models.models import FinancialSnapshot

settings = get_settings()
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler.add_job(refresh_user_tokens, "interval", minutes=50, id="token_refresh")
    scheduler.start()
    logger.info("Token auto-refresh started (every 50 min)")

    try:
        await refresh_user_tokens()
    except Exception as e:
        logger.warning("Initial token refresh failed: %s", e)

    import app.services.sync as sync_mod
    async with async_session() as session:
        result = await session.execute(select(FinancialSnapshot).limit(1))
        snap = result.scalar_one_or_none()
        if snap and snap.updated_at:
            updated_ts = snap.updated_at.timestamp()
            elapsed = time_mod.time() - updated_ts
            if elapsed < sync_mod.SYNC_COOLDOWN_SECONDS:
                sync_mod._last_sync_completed_at = updated_ts
                logger.info("Data is %ds old, skipping sync (cooldown %ds)", int(elapsed), sync_mod.SYNC_COOLDOWN_SECONDS)
            else:
                logger.info("Data is %ds old, sync needed", int(elapsed))
                asyncio.create_task(_startup_sync())
        else:
            logger.info("No existing data, running initial sync")
            asyncio.create_task(_startup_sync())

    yield

    scheduler.shutdown()


async def _startup_sync():
    try:
        await sync_all()
    except Exception as e:
        logger.error("Startup sync failed: %s", e)


app = FastAPI(
    title="Stepik Control Panel",
    description="CRM/BI-панель для авторов курсов на Stepik",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(dashboard.router)
app.include_router(financials.router)
app.include_router(sync.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
