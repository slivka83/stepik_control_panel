"""User profile sync (names) → raw_user."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .common import _hub

logger = logging.getLogger(__name__)

USER_ID_SOURCES = [
    "SELECT DISTINCT student_id FROM student_enrollments WHERE student_id IS NOT NULL",
    "SELECT DISTINCT user_id FROM submissions WHERE user_id IS NOT NULL",
    "SELECT DISTINCT user_id FROM raw_course_grade WHERE user_id IS NOT NULL",
    "SELECT DISTINCT user_id FROM raw_certificate WHERE user_id IS NOT NULL",
    "SELECT DISTINCT user FROM raw_course_review WHERE user IS NOT NULL",
]


async def sync_users(session: AsyncSession, token: str):
    """Sync user profiles (names) → raw_user (full_reload, ?ids[]= batches).

    IDs come from enrollments/submissions (app layer) and grades/certs/reviews
    (raw layer). Non-numeric garbage is filtered out — e.g. raw_comment.user
    holds the OAuth client name instead of a real user id.
    """
    logger.info("=== Raw: users ===")

    ids: set[str] = set()
    for q in USER_ID_SOURCES:
        r = await session.execute(text(q))
        for (val,) in r:
            if val is None:
                continue
            s = str(val)
            if s.lstrip("-").isdigit():
                ids.add(s)

    if not ids:
        logger.warning("  no user IDs to sync")
        return

    users = []
    id_list = sorted(ids, key=int)
    for i in range(0, len(id_list), 100):
        batch = id_list[i : i + 100]
        u = await _hub()._paginated_fetch("/users", token, "users", {"ids[]": batch})
        users.extend(u)
        logger.info("  ... %d profiles", len(users))

    mapping = await _hub()._get_fields_mapping(session, "users")
    await _hub()._replace_raw_table(session, "raw_user", users, mapping)
    logger.info("  raw_user: %d rows", len(users))
