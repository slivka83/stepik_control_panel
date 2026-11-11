"""Витрина студентов: student_enrollments + submissions + комментарии → student_marts."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import _ensure_json

logger = logging.getLogger(__name__)


STATUS_RANK = {"Active": 0, "Passive": 1, "Fading": 2, "Sleeping": 3, "Zombie": 4}


async def transform_students(session: AsyncSession):
    """Rebuild the student marts view layer — one row per student.

    Reads enrollments, submissions (app layer), comments and user profiles
    (raw layer), then replaces student_marts entirely.
    """
    logger.info("=== Student marts ===")

    agg = await session.execute(
        text("""
        SELECT student_id,
               count(*) AS courses_count,
               count(*) FILTER (WHERE certificate_issued) AS certificates,
               max(last_viewed_at) AS last_activity
        FROM student_enrollments
        GROUP BY student_id
    """)
    )
    agg_rows = list(agg)

    status_rows = await session.execute(
        text("""
        SELECT student_id, cohort_status FROM student_enrollments
        WHERE cohort_status IS NOT NULL
    """)
    )
    best_status: dict[int, str] = {}
    for sid, st in status_rows:
        if sid not in best_status or STATUS_RANK.get(st, 99) < STATUS_RANK.get(best_status[sid], 99):
            best_status[sid] = st

    sub_rows = await session.execute(
        text("""
        SELECT user_id,
               count(*) AS cnt,
               count(*) FILTER (WHERE status = 'correct') AS correct_cnt
        FROM submissions
        WHERE user_id IS NOT NULL AND is_author = FALSE
        GROUP BY user_id
    """)
    )
    subs_by_user = {int(r.user_id): (r.cnt, r.correct_cnt) for r in sub_rows}

    # Comments live in the raw layer; the real author is in _raw_json because
    # the mapped `user` column may hold a stale OAuth client name
    comment_rows = await session.execute(text("SELECT _raw_json FROM raw_comment"))
    comments_by_user: dict[int, int] = {}
    solutions_by_user: dict[int, int] = {}
    for (raw_json,) in comment_rows:
        obj = _ensure_json(raw_json)
        if not isinstance(obj, dict):
            continue
        try:
            uid = int(obj.get("user"))
        except (TypeError, ValueError):
            continue
        comments_by_user[uid] = comments_by_user.get(uid, 0) + 1
        thread = obj.get("thread")
        if isinstance(thread, str) and "solution" in thread:
            solutions_by_user[uid] = solutions_by_user.get(uid, 0) + 1

    name_rows = await session.execute(text("SELECT user_id, first_name, last_name FROM raw_user"))
    names: dict[int, str] = {}
    for row in name_rows:
        if row[0] is None:
            continue
        first = (row[1] or "").strip()
        last = (row[2] or "").strip()
        if first or last:
            names[int(row[0])] = f"{first} {last}".strip()

    rows = []
    for r in agg_rows:
        sid = int(r.student_id)
        subs_cnt, subs_correct = subs_by_user.get(sid, (0, 0))
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "student_id": sid,
                "name": names.get(sid),
                "cohort_status": best_status.get(sid, "Sleeping"),
                "courses_count": r.courses_count,
                "certificates": r.certificates,
                "submissions_count": subs_cnt,
                "submissions_successful": subs_correct,
                "comments_count": comments_by_user.get(sid, 0),
                "published_solutions": solutions_by_user.get(sid, 0),
                "last_activity": r.last_activity,
                "updated_at": datetime.now(UTC),
            }
        )

    await session.execute(text("DELETE FROM student_marts"))
    if rows:
        col_names = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_str = ", ".join(f'"{c}"' for c in col_names)
        await session.execute(
            text(f"INSERT INTO student_marts ({cols_str}) VALUES ({placeholders})"),
            rows,
        )

    logger.info("  student_marts: %d rows", len(rows))
