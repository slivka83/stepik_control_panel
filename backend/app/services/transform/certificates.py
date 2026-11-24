"""Витрина сертификатов: raw_certificate → mart_certificates."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import _ensure_json, _insert_rows, _month_tuple, _to_int, load_course_map

logger = logging.getLogger(__name__)


async def transform_certificates(session: AsyncSession):
    """Build mart_certificates from raw_certificate (courses in the courses table)."""
    logger.info("=== Mart certificates ===")

    course_map = await load_course_map(session)
    if not course_map:
        logger.warning("  no courses, skipping")
        return

    r = await session.execute(
        text("SELECT certificate_id, user_id, course_id, _raw_json FROM raw_certificate")
    )
    rows = []
    for cert_id_raw, user_raw, course_raw, raw_json in r:
        data = _ensure_json(raw_json)
        if not isinstance(data, dict):
            continue
        cid = _to_int(course_raw)
        if cid is None:
            cid = _to_int(data.get("course"))
        course_uuid = course_map.get(cid) if cid is not None else None
        if course_uuid is None:
            continue
        ym = _month_tuple(data.get("issue_date"))
        if ym is None:
            continue
        user_id = _to_int(user_raw)
        if user_id is None:
            user_id = _to_int(data.get("user"))
        cert_id = _to_int(data.get("id")) or _to_int(cert_id_raw)
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "course_id": course_uuid,
                "stepik_course_id": cid,
                "certificate_id": cert_id,
                "user_id": user_id,
                "year": ym[0],
                "month": ym[1],
                "type": data.get("type"),
            }
        )

    await session.execute(text("DELETE FROM mart_certificates"))
    await _insert_rows(session, "mart_certificates", rows)
    logger.info("  certificates=%d", len(rows))
