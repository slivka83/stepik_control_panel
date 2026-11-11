"""Витрина комментариев: raw_comment → mart_comments (атрибуция через mart_steps)."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import (
    _ensure_json,
    _get_buyer_names,
    _insert_rows,
    _month_tuple,
    _strip_html,
    _to_int,
    load_course_map,
)

logger = logging.getLogger(__name__)


async def transform_comments(session: AsyncSession):
    """Build mart_comments from raw_comment, attributed via mart_steps.

    Only attributable comments (step→course in the courses table). Aggregates
    keep deleted comments; the list filters them out at read time.
    """
    logger.info("=== Mart comments ===")

    course_map = await load_course_map(session)
    if not course_map:
        logger.warning("  no courses, skipping")
        return

    r = await session.execute(
        text(
            "SELECT step_id, course_id, stepik_course_id, lesson_id, step_number, "
            "module_number, lesson_number, module_title, lesson_title "
            "FROM mart_steps WHERE stepik_course_id IS NOT NULL"
        )
    )
    step_attr = {}
    for row in r:
        step_attr[row[0]] = {
            "course_uuid": row[1],
            "stepik_course_id": row[2],
            "lesson_id": row[3],
            "step_number": row[4],
            "module_number": row[5],
            "lesson_number": row[6],
            "module_title": row[7],
            "lesson_title": row[8],
        }

    user_names = await _get_buyer_names(session)

    r = await session.execute(text("SELECT _raw_json FROM raw_comment"))
    rows = []
    for (raw_json,) in r:
        cm = _ensure_json(raw_json)
        if not isinstance(cm, dict):
            continue
        time_raw = cm.get("time")
        if not time_raw:
            continue
        ym = _month_tuple(time_raw)
        if ym is None:
            continue
        try:
            sid = int(cm.get("target"))
        except (TypeError, ValueError):
            continue
        attr = step_attr.get(sid)
        if attr is None:
            continue
        comment_id = _to_int(cm.get("id"))
        if comment_id is None:
            continue
        user_id = _to_int(cm.get("user"))
        thread = cm.get("thread", "")
        is_solution = "solution" in thread if thread else False
        vote_delta = _to_int(cm.get("vote_delta")) or 0
        is_unanswered = not (cm.get("is_staff_replied") is True or cm.get("user_role") == "teacher")
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "course_id": attr["course_uuid"],
                "stepik_course_id": attr["stepik_course_id"],
                "comment_id": comment_id,
                "time": str(time_raw),
                "year": ym[0],
                "month": ym[1],
                "user_id": user_id,
                "user_name": user_names.get(user_id) if user_id is not None else None,
                "text": _strip_html(cm.get("text")),
                "likes": vote_delta if vote_delta > 0 else 0,
                "dislikes": -vote_delta if vote_delta < 0 else 0,
                "replies": _to_int(cm.get("reply_count")) or 0,
                "is_solution": bool(is_solution),
                "is_unanswered": bool(is_unanswered),
                "is_disliked": bool(vote_delta < 0),
                "is_deleted": bool(cm.get("is_deleted")),
                "lesson_id": attr["lesson_id"],
                "step_number": attr["step_number"],
                "module_number": attr["module_number"],
                "lesson_number": attr["lesson_number"],
                "module_title": attr["module_title"],
                "lesson_title": attr["lesson_title"],
            }
        )

    await session.execute(text("DELETE FROM mart_comments"))
    await _insert_rows(session, "mart_comments", rows)
    logger.info("  comments=%d", len(rows))
