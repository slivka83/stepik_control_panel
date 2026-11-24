"""Community sync: review summaries, individual reviews, comments."""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.stepik_api import StepikAPIError

from .common import _as_int, _dedupe_by, _hub, _previous_raw_objects, _raw_course_ids, _save_sync_state

logger = logging.getLogger(__name__)

COMMENTS_ENDPOINT = "comments"


def _parse_time(value) -> datetime | None:
    """ISO-время Stepik → aware datetime (None для мусора).

    Сравнивать время строками нельзя: `...00.123Z` лексикографически меньше
    `...00Z`, хотя это более новый комментарий, а часовые пояса дают ложный
    порядок. Поэтому курсор и граница сравниваются как моменты времени.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

# Страховка от вечного has_next=true. С курсором синк останавливается на
# первой странице, где встретил уже сохранённый комментарий; большой лимит
# нужен только для догоняющей загрузки после долгого простоя.
COMMENTS_MAX_PAGES = 500


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
    review_ids = sorted({rid for value in review_ids if (rid := _as_int(value)) is not None})

    review_summaries = []
    failed_batches = 0
    failed_ids: set[int] = set()
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
            failed_batches += 1
            failed_ids.update(batch)
            logger.warning("  course-review-summaries batch %d: %s — skip", i // 100, e)
            continue
        review_summaries.extend(rs)
    if failed_batches and not review_summaries:
        # Ни одна сводка не пришла из-за ошибок: не затираем прошлые рейтинги.
        logger.warning("  all review-summary batches failed — keeping previous rows")
        return
    # Частичный сбой не должен удалять уже сохранённые сводки этого батча.
    review_summaries.extend(
        await _previous_raw_objects(
            session, "raw_course_review_summary", "review_summary_id", failed_ids
        )
    )
    review_summaries = _dedupe_by(review_summaries, "id")
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
    failed_courses: list[int] = []
    for cid in course_ids:
        try:
            reviews = await _hub()._paginated_fetch(
                "/course-reviews", token, "course-reviews", {"course": cid}, max_pages=2000
            )
        except StepikAPIError as e:
            failed_courses.append(cid)
            logger.warning("  course-reviews course %d: %s — skip", cid, e)
            continue
        all_reviews.extend(reviews)
        logger.info("    course %d: %d reviews", cid, len(reviews))
    if course_ids and len(failed_courses) == len(course_ids) and not all_reviews:
        logger.warning("  all course-reviews requests failed — keeping previous rows")
        return
    # Частичный сбой не должен удалять отзывы упавшего курса: возвращаем их
    # из прошлой загрузки и заменяем таблицу целиком.
    all_reviews.extend(
        await _previous_raw_objects(session, "raw_course_review", "course", failed_courses)
    )
    all_reviews = _dedupe_by(all_reviews, "id")
    await _hub()._replace_raw_table(session, "raw_course_review", all_reviews, mapping_reviews)
    logger.info("  raw_course_review: %d rows total", len(all_reviews))
    await session.commit()


async def _sync_comments(session: AsyncSession, token: str, course_ids: list[int]) -> int:
    """Comments — incremental by time per course.

    The endpoint returns newest-first. `>= last_time` (not `>`) keeps other
    comments created in the same second as the saved cursor: with `>` they were
    never fetched again and their edits/likes never refreshed. Upsert applies
    changes to already stored comments too (text, vote_delta, replies,
    is_staff_replied), so the "Не отвеченные"/"Дизлайки" lists stay current.

    The cursor is advanced only when the scan actually reached already stored
    comments (or the end of the list). A capped run (huge backlog) leaves the
    cursor untouched and logs a warning instead of silently skipping the gap.
    """
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
        last_dt = _parse_time(last_time)
        course_new = 0
        page = 1
        max_time_str = last_time
        max_dt = last_dt
        reached_boundary = False
        while page <= COMMENTS_MAX_PAGES:
            try:
                data = await _hub()._request(
                    "GET", "/comments", token, {"course": cid, "page": page, "page_size": 20}
                )
            except StepikAPIError as e:
                logger.warning("  comments course %d page %d: %s — skip", cid, page, e)
                break
            objects = data.get("comments", [])
            if not objects:
                reached_boundary = True
                break

            new_objects = []
            for obj in objects:
                t = obj.get("time", "") or ""
                if not isinstance(t, str):
                    continue
                t_dt = _parse_time(t)
                # Сравниваем моменты времени, если оба разобрались; иначе —
                # старый строковый порядок (для нестандартных значений API).
                is_old = (t_dt < last_dt) if (t_dt is not None and last_dt is not None) else bool(
                    last_time and t < last_time
                )
                if is_old:
                    # Дошли до уже сохранённого хвоста — дальше всё старое.
                    reached_boundary = True
                if not is_old:
                    new_objects.append(obj)
                    newer = (t_dt > max_dt) if (t_dt is not None and max_dt is not None) else t > max_time_str
                    if newer:
                        max_dt = t_dt
                        max_time_str = t

            if new_objects:
                await _hub()._upsert_raw_table(session, "raw_comment", new_objects, mapping)
                course_new += len(new_objects)

            if reached_boundary:
                break
            if not data.get("meta", {}).get("has_next"):
                reached_boundary = True
                break
            page += 1

        if course_new > 0:
            if reached_boundary:
                await _save_sync_state(
                    session, COMMENTS_ENDPOINT, f"last_time_course_{cid}", max_time_str
                )
            else:
                logger.warning(
                    "    course %d: %d-page backlog not fully fetched — cursor stays at %r",
                    cid,
                    COMMENTS_MAX_PAGES,
                    last_time or "the beginning",
                )
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
