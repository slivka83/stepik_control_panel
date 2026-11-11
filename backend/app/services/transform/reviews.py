"""Витрина отзывов: raw_course_review → mart_reviews."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import (
    _ensure_json,
    _insert_rows,
    _month_tuple,
    _to_float,
    _to_int,
    load_course_map,
)

logger = logging.getLogger(__name__)


async def transform_reviews(session: AsyncSession):
    """Build mart_reviews from raw_course_review (courses in the courses table)."""
    logger.info("=== Mart reviews ===")

    course_map = await load_course_map(session)
    if not course_map:
        logger.warning("  no courses, skipping")
        return

    r = await session.execute(text('SELECT review_id, "user", course, _raw_json FROM raw_course_review'))
    rows = []
    for review_id_raw, user_raw, course_raw, raw_json in r:
        data = _ensure_json(raw_json)
        if not isinstance(data, dict):
            continue
        cid = _to_int(course_raw)
        if cid is None:
            cid = _to_int(data.get("course"))
        course_uuid = course_map.get(cid) if cid is not None else None
        if course_uuid is None:
            continue
        ym = _month_tuple(data.get("create_date"))
        if ym is None:
            continue
        user_id = _to_int(user_raw)
        if user_id is None:
            user_id = _to_int(data.get("user"))
        score = _to_float(data.get("score"))
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "course_id": course_uuid,
                "stepik_course_id": cid,
                "review_id": _to_int(data.get("id")) if _to_int(data.get("id")) is not None else _to_int(review_id_raw),
                "user_id": user_id,
                "year": ym[0],
                "month": ym[1],
                "score": score,
            }
        )

    await session.execute(text("DELETE FROM mart_reviews"))
    await _insert_rows(session, "mart_reviews", rows)
    logger.info("  reviews=%d", len(rows))
