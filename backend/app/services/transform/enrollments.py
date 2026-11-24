"""Зачисления: raw_course_grade + raw_certificate → student_enrollments."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import _to_float, _to_int, calculate_cohort_status, load_course_map, parse_dt

logger = logging.getLogger(__name__)


async def transform_enrollments(session: AsyncSession):
    logger.info("=== Enrollments ===")

    course_map = await load_course_map(session)

    if not course_map:
        logger.warning("  no courses, skipping")
        return

    for stepik_cid, course_uuid in course_map.items():
        r = await session.execute(
            text("""
                SELECT user_id AS student_id, score, last_viewed, date_joined
                FROM raw_course_grade
                WHERE course_id = :cid
            """),
            {"cid": str(stepik_cid)},
        )
        grade_rows = [dict(r._mapping) for r in r]

        r = await session.execute(
            text("""
                SELECT DISTINCT user_id FROM raw_certificate
                WHERE course_id = :cid AND user_id IS NOT NULL
            """),
            {"cid": str(stepik_cid)},
        )
        cert_users = {uid for row in r if (uid := _to_int(row[0])) is not None}

        enrollments = []
        for g in grade_rows:
            student_id = _to_int(g.get("student_id"))
            if student_id is None:
                continue
            lv = parse_dt(g.get("last_viewed"))
            dj = parse_dt(g.get("date_joined"))
            score = int(_to_float(g.get("score")) or 0)
            enrollments.append(
                {
                    "id": str(uuid.uuid4()),
                    "course_id": course_uuid,
                    "student_id": student_id,
                    "cohort_status": calculate_cohort_status(lv, dj),
                    "points_earned": score,
                    "certificate_issued": student_id in cert_users,
                    "last_viewed_at": lv,
                    "date_joined": dj,
                    "created_at": datetime.now(UTC),
                }
            )

        await session.execute(
            text("DELETE FROM student_enrollments WHERE course_id = :cid"),
            {"cid": course_uuid},
        )
        if enrollments:
            col_names = [
                "id",
                "course_id",
                "student_id",
                "cohort_status",
                "points_earned",
                "certificate_issued",
                "last_viewed_at",
                "date_joined",
                "created_at",
            ]
            placeholders = ", ".join(f":{c}" for c in col_names)
            cols_str = ", ".join(f'"{c}"' for c in col_names)
            await session.execute(
                text(f"INSERT INTO student_enrollments ({cols_str}) VALUES ({placeholders})"),
                enrollments,
            )

        logger.info("  course %d: %d enrollments", stepik_cid, len(enrollments))
