import asyncio
import logging
from contextlib import asynccontextmanager, suppress

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, courses, dashboard, financials, sync
from app.config import get_settings
from app.services.rate_limiter import bind_main_loop, close_redis
from app.services.stepik_api import close_client
from app.services.token_refresh import refresh_user_tokens

settings = get_settings()
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app):
    # Bind the main event loop before any sync thread touches Redis; otherwise
    # the sync loop can become "main" and the app later reuses its client.
    bind_main_loop()
    scheduler.add_job(refresh_user_tokens, "interval", minutes=5, id="token_refresh")
    scheduler.start()
    logger.info("Token auto-refresh started (every 5 min, 15 min before expiry)")

    async def _startup_tasks():
        try:
            await refresh_user_tokens()
        except Exception as e:
            logger.warning("Initial token refresh failed: %s", e)

        logger.info("Startup tasks complete, data available via sync button")

    startup_task = asyncio.create_task(_startup_tasks())

    yield

    startup_task.cancel()
    with suppress(asyncio.CancelledError):
        await startup_task
    scheduler.shutdown()
    await close_client()
    await close_redis()


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
        logger.warning("Health check: Redis unavailable: %s", e)
        return {"status": "degraded", "redis": "down"}
