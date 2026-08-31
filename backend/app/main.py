import asyncio
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, courses, dashboard, financials, sync
from app.config import get_settings
from app.services.stepik_api import close_client
from app.services.token_refresh import refresh_user_tokens

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

        logger.info("Startup tasks complete, data available via sync button")

    asyncio.create_task(_startup_tasks())

    yield

    scheduler.shutdown()
    await close_client()


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
