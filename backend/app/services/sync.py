import logging
import time
import asyncio
import threading
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker as _sessionmaker

from app.config import get_settings
import app.database as _db
from app.models import User
from app.services.crypto import decrypt_token
from app.services import raw_sync, transform

logger = logging.getLogger(__name__)

# Local reference to the default DB session (can be overridden by sync_all_sync in a thread)
async_session = _db.async_session

_sync_lock = threading.Lock()
_sync_in_progress = False
_sync_progress: int = 0
_sync_step: str = ""
_last_sync_completed_at: float = 0

SYNC_COOLDOWN_SECONDS = 60  # 1 minute

MONTH_NAMES = {  # kept for test imports
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


async def _get_user_token(user_id=None) -> str | None:
    async with async_session() as session:
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
        else:
            result = await session.execute(select(User))
        users = result.scalars().all()
        if not users:
            logger.warning("No user found")
            return None
        return decrypt_token(users[0].access_token)

def calculate_cohort_status(last_viewed_at: datetime | None, date_joined: datetime | None = None) -> str:
    if last_viewed_at is None:
        return "Sleeping"
    if last_viewed_at.tzinfo is None:
        last_viewed_at = last_viewed_at.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - last_viewed_at).days
    if days <= 7:
        return "Active"
    if days <= 30:
        return "Passive"
    if days <= 90:
        return "Fading"
    if date_joined is not None:
        if date_joined.tzinfo is None:
            date_joined = date_joined.replace(tzinfo=timezone.utc)
        days_after_join = (last_viewed_at.date() - date_joined.date()).days
        if 0 <= days_after_join <= 3:
            return "Zombie"
    return "Sleeping"


def can_sync() -> bool:
    with _sync_lock:
        if _sync_in_progress:
            return False
        if _last_sync_completed_at == 0:
            return True
        return (time.time() - _last_sync_completed_at) >= SYNC_COOLDOWN_SECONDS


async def sync_courses_and_enrollments(user_id=None):
    """Raw sync → transform for courses and enrollments."""
    global _sync_progress, _sync_step

    token = await _get_user_token(user_id)
    if not token:
        return
    user_id_db = user_id

    _sync_step = "курсы: структура"
    _sync_progress = 3
    async with async_session() as session:
        async with session.begin():
            await raw_sync.sync_courses_structure(session, token)
    logger.info("Course structure synced")

    _sync_step = "курсы: оценки и сертификаты"
    _sync_progress = 15
    async with async_session() as session:
        r = await session.execute(text("SELECT course_id FROM raw_course"))
        course_ids = [int(row[0]) for row in r if row[0] is not None]
    async with async_session() as session:
        async with session.begin():
            await raw_sync.sync_course_grades_and_certs(session, token, course_ids)
    logger.info("Course grades & certs synced")

    _sync_step = "курсы: трансформация"
    _sync_progress = 30
    async with async_session() as session:
        async with session.begin():
            await transform.transform_courses(session, user_id_db)
    async with async_session() as session:
        async with session.begin():
            await transform.transform_enrollments(session)
    _sync_progress = 40
    logger.info("Courses & enrollments transformed")


async def sync_submissions(user_id=None):
    """Raw sync → transform for submissions."""
    global _sync_progress, _sync_step

    token = await _get_user_token(user_id)
    if not token:
        return

    _sync_step = "решения: загрузка"
    _sync_progress = 42
    # raw_sync.sync_submissions коммитит сам (пошагово, для инкрементальности) —
    # внешний session.begin() конфликтует с внутренними commit()
    async with async_session() as session:
        await raw_sync.sync_submissions(session, token)
    _sync_progress = 75
    logger.info("Raw submissions synced")

    _sync_step = "решения: трансформация"
    async with async_session() as session:
        async with session.begin():
            await transform.transform_submissions(session)
    _sync_progress = 85
    logger.info("Submissions transformed")


async def sync_financials(user_id=None):
    """Raw sync → transform for financials."""
    global _sync_progress, _sync_step

    _sync_step = "финансы: загрузка"
    async with async_session() as session:
        async with session.begin():
            await raw_sync.sync_financials(session)
    _sync_progress = 90
    logger.info("Raw financials synced")

    _sync_step = "финансы: трансформация"
    async with async_session() as session:
        async with session.begin():
            await transform.transform_financials(session)
    _sync_progress = 95
    logger.info("Financials transformed")


async def sync_community_stats(user_id=None):
    """Raw sync → transform for community."""
    global _sync_progress, _sync_step

    token = await _get_user_token(user_id)
    if not token:
        return

    _sync_step = "сообщество: загрузка"
    # raw_sync.sync_community коммитит сам (пошагово) — без внешнего session.begin()
    async with async_session() as session:
        await raw_sync.sync_community(session, token)
    _sync_progress = 98
    logger.info("Raw community synced")

    _sync_step = "сообщество: трансформация"
    async with async_session() as session:
        async with session.begin():
            await transform.transform_community(session)
    _sync_progress = 100
    logger.info("Community transformed")


async def sync_all(force: bool = False, user_id=None):
    """Run all sync jobs. Skips if cooldown hasn't passed (unless force=True).

    If user_id is provided, sync only that user's data; otherwise sync all users.
    """
    global _sync_in_progress, _sync_progress, _sync_step, _last_sync_completed_at

    with _sync_lock:
        if _sync_in_progress:
            logger.info("Sync already in progress, skipping")
            return {"status": "skipped", "reason": "already_in_progress"}
        if not force and _last_sync_completed_at > 0:
            remaining = SYNC_COOLDOWN_SECONDS - (time.time() - _last_sync_completed_at)
            if remaining > 0:
                logger.info("Sync skipped, cooldown remaining: %ds", int(remaining))
                return {"status": "skipped", "reason": "cooldown", "remaining_seconds": int(remaining)}
        _sync_in_progress = True
        _sync_progress = 0
        _sync_step = "курсы"

    logger.info("=== Full sync started ===")
    try:
        _sync_step = "курсы и студенты"
        await sync_courses_and_enrollments(user_id)
        with _sync_lock:
            _sync_progress = 40
        _sync_step = "отправленные решения"
        await sync_submissions(user_id)
        with _sync_lock:
            _sync_progress = 85
        _sync_step = "финансы"
        await sync_financials(user_id)
        with _sync_lock:
            _sync_progress = 95
        _sync_step = "рейтинги"
        await sync_community_stats(user_id)
        with _sync_lock:
            _sync_progress = 100
        _sync_step = "готово"
        with _sync_lock:
            _last_sync_completed_at = time.time()
        logger.info("=== Full sync completed ===")
        return {"status": "ok"}
    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        return {"status": "error", "detail": str(e)}
    finally:
        with _sync_lock:
            _sync_in_progress = False
            _sync_progress = 0
            _sync_step = ""


def sync_all_sync(force: bool = False, user_id=None) -> dict:
    """Synchronous wrapper for sync_all, runs in its own event loop in a thread.
    Creates a separate DB engine to avoid "attached to a different loop" errors.
    Skips Redis rate limiter (sync thread uses its own loop, Redis client is bound to main loop).
    """
    global async_session

    from app.services import rate_limiter

    rate_limiter._sync_thread_local.skip_rate_limit = True

    engine = create_async_engine(get_settings().database_url, pool_size=5, max_overflow=2)
    thread_session = _sessionmaker(engine, expire_on_commit=False)

    old_session = async_session
    async_session = thread_session

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(sync_all(force=force, user_id=user_id))
    finally:
        async_session = old_session
        rate_limiter._sync_thread_local.skip_rate_limit = False
        loop.run_until_complete(engine.dispose())
        loop.close()
