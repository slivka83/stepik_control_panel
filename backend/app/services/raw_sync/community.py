"""Community sync: review summaries, individual reviews, comments."""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.stepik_api import StepikAPIError

from .common import _hub, _raw_course_ids, _save_sync_state

logger = logging.getLogger(__name__)

COMMENTS_ENDPOINT = "comments"


async def _sync_review_summaries(session: AsyncSession, token: str) -> None:
    """Review summaries: all review_summary_json in one pass (batches of 100)."""
    review_ids = []
    r = await session.execute(text("SELECT review_summary_json FROM raw_course"))
    for (rs_json,) in r:
        if not rs_json:
            continue
        try:
            rid = json.loads(rs_json) if isinstance(rs_json, str) else rs_json
            if isinstance(rid, (list, tuple)):
                review_ids.extend(rid)
            else:
                review_ids.append(rid)
        except (json.JSONDecodeError, TypeError):
            pass
    review_ids = list(set(int(x) for x in review_ids if x is not None))

    if not review_ids:
        return

    review_summaries = []
    for i in range(0, len(review_ids), 100):
        batch = review_ids[i : i + 100]
        try:
            rs = await _hub()._paginated_fetch(
                "/course-review-summaries",
                token,
                "course-review-summaries",
                {"ids[]": batch},
            )
        except StepikAPIError as e:
            logger.warning("  course-review-summaries batch %d: %s — skip", i // 100, e)
            continue
        review_summaries.extend(rs)
    mapping = await _hub()._get_fields_mapping(session, "course_review_summaries")
    await _hub()._replace_raw_table(session, "raw_course_review_summary", review_summaries, mapping)
    logger.info("  raw_course_review_summary: %d rows", len(review_summaries))


async def _sync_reviews(session: AsyncSession, token: str, course_ids: list[int]) -> None:
    """Individual reviews — full reload per course (kept fresh with the app sync).

    Previously only the summaries were refreshed here and the actual reviews
    were left to scripts/sync_raw.py, so new courses' reviews went stale.
    """
    mapping_reviews = await _hub()._get_fields_mapping(session, "course_reviews")
    all_reviews = []
    for cid in course_ids:
        try:
            reviews = await _hub()._paginated_fetch("/course-reviews", token, "course-reviews", {"course": cid})
        except StepikAPIError as e:
            logger.warning("  course-reviews course %d: %s — skip", cid, e)
            continue
        all_reviews.extend(reviews)
        logger.info("    course %d: %d reviews", cid, len(reviews))
    await _hub()._replace_raw_table(session, "raw_course_review", all_reviews, mapping_reviews)
    logger.info("  raw_course_review: %d rows total", len(all_reviews))
    await session.commit()


async def _sync_comments(session: AsyncSession, token: str, course_ids: list[int]) -> int:
    """Comments — incremental by time per course."""
    r = await session.execute(
        text(
            "SELECT key, value FROM raw_sync_state "
            f"WHERE endpoint_name = '{COMMENTS_ENDPOINT}' AND key LIKE 'last_time_course_%'"
        ),
    )
    last_times = {row[0]: row[1] for row in r}

    mapping = await _hub()._get_fields_mapping(session, "comments")
    total_new = 0
    for cid in course_ids:
        last_time = last_times.get(f"last_time_course_{cid}", "")
        course_new = 0
        page = 1
        max_time_str = last_time
        while page <= 50:
            try:
                data = await _hub()._request(
                    "GET", "/comments", token, {"course": cid, "page": page, "page_size": 20}
                )
            except StepikAPIError as e:
                logger.warning("  comments course %d page %d: %s — skip", cid, page, e)
                break
            objects = data.get("comments", [])
            if not objects:
                break

            new_objects = []
            for obj in objects:
                t = obj.get("time", "") or ""
                if isinstance(t, str) and t > last_time:
                    new_objects.append(obj)
                    if t > max_time_str:
                        max_time_str = t

            if new_objects:
                await _hub()._upsert_raw_table(session, "raw_comment", new_objects, mapping)
                course_new += len(new_objects)

                await _save_sync_state(
                    session, COMMENTS_ENDPOINT, f"last_time_course_{cid}", max_time_str
                )

            if not data.get("meta", {}).get("has_next"):
                break
            page += 1

        if course_new > 0:
            logger.info("    course %d: +%d comments", cid, course_new)
            await session.commit()
        total_new += course_new

    logger.info("  raw_comment: +%d rows (incremental_time)", total_new)
    return total_new


async def sync_community(session: AsyncSession, token: str):
    """Sync reviews and comments (incremental time for comments)."""
    logger.info("=== Raw: community ===")

    course_ids = await _raw_course_ids(session)

    await _sync_review_summaries(session, token)
    await session.commit()

    await _sync_reviews(session, token, course_ids)
    await _sync_comments(session, token, course_ids)
