"""Курсы: raw_course → courses и карта шаг → курс."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import get_course_status, parse_dt

logger = logging.getLogger(__name__)


async def transform_courses(session: AsyncSession, user_id: str | None = None):
    logger.info("=== Courses ===")
    r = await session.execute(
        text("""
        SELECT course_id, title, became_published_at, is_public
        FROM raw_course ORDER BY course_id
    """)
    )
    raw_courses = [dict(r._mapping) for r in r]
    uid_param = str(user_id) if user_id else None
    if uid_param:
        r = await session.execute(
            text("SELECT id, stepik_course_id FROM courses WHERE user_id = :uid"),
            {"uid": uid_param},
        )
    else:
        r = await session.execute(text("SELECT id, stepik_course_id FROM courses"))
    existing = {row[1]: str(row[0]) for row in r}

    if uid_param:
        r = await session.execute(
            text("SELECT id FROM users WHERE id = :uid LIMIT 1"),
            {"uid": uid_param},
        )
    else:
        r = await session.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = r.fetchone()
    if not user_row:
        logger.warning("No user found")
        return
    user_id_db = str(user_row[0])

    seen_ids = set()
    upserted = 0
    for rc in raw_courses:
        sid = rc["course_id"]
        if sid is None:
            continue
        sid = int(sid)
        seen_ids.add(sid)
        is_pub_raw = rc.get("is_public")
        if is_pub_raw is not None:
            if isinstance(is_pub_raw, bool):
                is_pub = is_pub_raw
            elif isinstance(is_pub_raw, (int, float)):
                is_pub = bool(is_pub_raw)
            else:
                is_pub = str(is_pub_raw).lower() in ("true", "1")
        else:
            is_pub = None
        pub_dt = None
        if is_pub:
            pub_raw = rc.get("became_published_at")
            pub_dt = parse_dt(pub_raw) if pub_raw else None
        status = get_course_status(is_pub) if is_pub is not None else "Draft"
        title = (rc.get("title") or "Untitled")[:255]

        if sid in existing:
            await session.execute(
                text("""
                    UPDATE courses SET title = :t, status = :s, published_at = :p
                    WHERE stepik_course_id = :sid
                """),
                {"t": title, "s": status, "p": pub_dt, "sid": sid},
            )
        else:
            await session.execute(
                text("""
                    INSERT INTO courses (id, user_id, stepik_course_id, title, status, published_at, created_at)
                    VALUES (:id, :uid, :sid, :t, :s, :p, :now)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "uid": user_id_db,
                    "sid": sid,
                    "t": title,
                    "s": status,
                    "p": pub_dt,
                    "now": datetime.now(UTC),
                },
            )
        upserted += 1

    deleted = 0
    for sid, cid_str in existing.items():
        if sid not in seen_ids:
            await session.execute(
                text("DELETE FROM courses WHERE id = :cid"),
                {"cid": cid_str},
            )
            deleted += 1

    logger.info("  %d upserted, %d deleted", upserted, deleted)


async def build_step_course_map(session: AsyncSession) -> dict[int, int]:
    r = await session.execute(
        text("""
        SELECT DISTINCT s.step_id, sec.course
        FROM raw_step s
        JOIN raw_unit u ON u.lesson_id = s.lesson
        JOIN raw_section sec ON sec.section_id = u.section_id
        WHERE s.step_id IS NOT NULL AND sec.course IS NOT NULL
    """)
    )
    return {int(r[0]): int(r[1]) for r in r}
