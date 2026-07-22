from contextlib import asynccontextmanager
import asyncio
import logging
import time as time_mod

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.api import auth, courses, dashboard, financials, sync
from app.services.token_refresh import refresh_user_tokens
from app.services.sync import sync_all, SYNC_COOLDOWN_SECONDS
from app.models import FinancialSnapshot

settings = get_settings()
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app):
    scheduler.add_job(refresh_user_tokens, "interval", minutes=50, id="token_refresh")
    scheduler.start()
    logger.info("Token auto-refresh started (every 50 min)")

    async def _startup_tasks():
        try:
            await refresh_user_tokens()
        except Exception as e:
            logger.warning("Initial token refresh failed: %s", e)

        async with async_session() as session:
            result = await session.execute(select(FinancialSnapshot).limit(1))
            snap = result.scalar_one_or_none()
            if snap and snap.updated_at:
                updated_ts = snap.updated_at.timestamp() if snap.updated_at.tzinfo is None else snap.updated_at.timestamp()
                elapsed = time_mod.time() - updated_ts
                if elapsed < SYNC_COOLDOWN_SECONDS:
                    logger.info("Data is %ds old, skipping sync (cooldown %ds)", int(elapsed), SYNC_COOLDOWN_SECONDS)
                else:
                    logger.info("Data is %ds old, running startup sync", int(elapsed))
                    try:
                        await sync_all()
                    except Exception as e:
                        logger.error("Startup sync failed: %s", e)
            else:
                logger.info("No existing data, running initial sync")
                try:
                    await sync_all()
                except Exception as e:
                    logger.error("Startup sync failed: %s", e)

    asyncio.create_task(_startup_tasks())

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Stepik Control Panel",
    description="CRM/BI-панель для авторов курсов на Stepik",
    version="0.2.0",
    lifespan=lifespan,
)

origins = (
    [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    if settings.allowed_origins
    else [settings.frontend_url]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Cookie"],
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(dashboard.router)
app.include_router(financials.router)
app.include_router(sync.router)


@app.get("/api/health")
async def health():
    try:
        from app.services.rate_limiter import redis_client
        await redis_client.ping()
        return {"status": "ok", "redis": "up"}
    except Exception as e:
        return {"status": "degraded", "redis": "down", "detail": str(e)}
