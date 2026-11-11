"""Сообщество: рейтинги и комментарии → financial_snapshots.community."""

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import _ensure_json, _serialize_data, _to_int, load_course_map
from app.services.transform.courses import build_step_course_map

logger = logging.getLogger(__name__)


async def transform_community(session: AsyncSession):
    logger.info("=== Community ===")

    course_map = await load_course_map(session)

    if not course_map:
        logger.warning("  no courses, skipping")
        return

    r = await session.execute(
        text("""
        SELECT _raw_json FROM raw_course_review_summary
    """)
    )
    reviews = [_ensure_json(r[0]) for r in r]

    average_rating = 0.0
    total_reviews = 0
    per_course_rating = {}
    per_course_reviews_count = {}
    if reviews:
        for rv in reviews:
            cid = rv.get("course") or rv.get("id")
            avg = rv.get("average")
            cnt = int(rv.get("count", 0) or 0)
            total_reviews += cnt
            if cid and avg:
                try:
                    avg_f = float(avg)
                    if avg_f > 0:
                        per_course_rating[str(cid)] = round(avg_f, 2)
                        per_course_reviews_count[str(cid)] = cnt
                except (ValueError, TypeError):
                    pass
        if per_course_rating:
            average_rating = round(sum(per_course_rating.values()) / len(per_course_rating), 2)

    r = await session.execute(
        text("""
        SELECT _raw_json FROM raw_comment
    """)
    )
    comments = sorted((_ensure_json(r[0]) for r in r), key=lambda x: x.get("time") or "")

    total_comments = 0
    comments_monthly = {}
    total_solutions = 0
    solutions_monthly = {}
    per_course_comments = {}

    step_course = await build_step_course_map(session)

    for cm in comments:
        time_raw = cm.get("time")
        if not time_raw:
            continue
        try:
            dt = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        key = f"{dt.year}-{dt.month:02d}"
        thread = cm.get("thread", "")
        is_solution = "solution" in thread if thread else False

        # Only comments attributable to one of the user's courses count towards
        # the global/per-course totals. Prefer step→course mapping; fall back to
        # the course id reported by the comment itself. This keeps the snapshot
        # consistent with mart_comments and with the filtered (course selection)
        # community stats — otherwise "all courses" would not equal "no filter".
        target = cm.get("target")
        step_cid = step_course.get(_to_int(target)) if (target and step_course) else None
        if not step_cid:
            course_raw = cm.get("course")
            course_raw_int = _to_int(course_raw)
            if course_raw_int is not None and course_raw_int in course_map:
                step_cid = course_raw_int
            else:
                continue

        if is_solution:
            total_solutions += 1
            solutions_monthly[key] = solutions_monthly.get(key, 0) + 1
        else:
            # Published solutions are counted separately (total_solutions /
            # solutions_monthly); plain "comments" excludes them so the two
            # categories don't double-count.
            total_comments += 1
            comments_monthly[key] = comments_monthly.get(key, 0) + 1

            cid_str = str(step_cid)
            per_course_comments[cid_str] = per_course_comments.get(cid_str, 0) + 1

    per_course = {}
    for cid, _ in course_map.items():
        cid_str = str(cid)
        per_course[cid_str] = {
            "comments": per_course_comments.get(cid_str, 0),
            "reviews_count": per_course_reviews_count.get(cid_str, 0),
            "average_rating": per_course_rating.get(cid_str, 0),
        }

    community = {
        "average_rating": average_rating,
        "total_reviews": total_reviews,
        "total_comments": total_comments,
        "comments_monthly": comments_monthly,
        "total_solutions": total_solutions,
        "solutions_monthly": solutions_monthly,
        "per_course": per_course,
    }

    r = await session.execute(text("SELECT id, data FROM financial_snapshots LIMIT 1"))
    row = r.fetchone()
    if row:
        snap_id = row[0]
        data = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        data["community"] = community
        await session.execute(
            text("UPDATE financial_snapshots SET data = :data, updated_at = :now WHERE id = :id"),
            {"data": _serialize_data(data, session), "now": datetime.now(UTC), "id": snap_id},
        )
    else:
        await session.execute(
            text("INSERT INTO financial_snapshots (id, data, updated_at) VALUES (:id, :data, :now)"),
            {
                "id": str(uuid.uuid4()),
                "data": _serialize_data({"community": community}, session),
                "now": datetime.now(UTC),
            },
        )

    logger.info(
        "  rating=%.2f reviews=%d comments=%d solutions=%d",
        average_rating,
        total_reviews,
        total_comments,
        total_solutions,
    )
