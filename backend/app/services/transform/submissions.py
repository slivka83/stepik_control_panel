"""Решения: raw_submission + raw_attempt → submissions."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.transform.common import _ensure_json, _to_int, load_course_map, parse_dt
from app.services.transform.courses import build_step_course_map

logger = logging.getLogger(__name__)


def _merge_submission_row(row) -> dict:
    """Колонки raw_submission (пишутся loader'ом по маппингу) — источник
    истины; _raw_json — fallback для колонок-пустышек (например, строки,
    загруженные до введения колонки step)."""
    raw = _ensure_json(row[6]) or {}
    merged = dict(raw)
    for idx, key in ((0, "id"), (1, "step"), (2, "attempt"), (3, "status"), (4, "time"), (5, "score")):
        if row[idx] is not None:
            merged[key] = row[idx]
    return merged


async def transform_submissions(session: AsyncSession):
    logger.info("=== Submissions ===")

    step_course = await build_step_course_map(session)
    if not step_course:
        logger.warning("  no step→course mapping, skipping")
        return

    app_course_map = await load_course_map(session)

    r = await session.execute(
        text("""
        SELECT submission_id, step, attempt, status, time, score, _raw_json
        FROM raw_submission
    """)
    )
    submission_rows = sorted(
        (_merge_submission_row(row) for row in r),
        key=lambda x: int(x.get("id", 0) or 0),
    )

    r = await session.execute(
        text("""
        SELECT attempt_id, step, "user" FROM raw_attempt
    """)
    )
    attempt_step: dict[int, int] = {}
    attempt_user: dict[int, int] = {}
    for row in r:
        aid = row[0]
        if aid is None:
            continue
        if row[1] is not None:
            attempt_step[int(aid)] = int(row[1])
        if row[2] is not None:
            attempt_user[int(aid)] = int(row[2])

    author_uid = get_settings().stepik_user_id

    total = 0
    batch = []
    batch_size = 500

    for sub in submission_rows:
        sid = sub.get("id")
        attempt_id = sub.get("attempt")
        step_id = sub.get("step")
        # API не возвращает step в объекте submission — шаг известен только
        # из контекста запроса ?step= и пишется loader'ом в raw_submission.step.
        # Fallback: step определяется через attempt (raw_attempt.step).
        if not step_id and attempt_id is not None:
            try:
                step_id = attempt_step.get(int(attempt_id))
            except (TypeError, ValueError):
                step_id = None
        if not sid or not step_id:
            continue
        step_cid = step_course.get(int(step_id))
        if step_cid not in app_course_map:
            continue
        course_uuid = app_course_map[step_cid]
        status = sub.get("status", "")
        sub_time_raw = sub.get("time")
        sub_time = parse_dt(sub_time_raw)
        if not sub_time:
            continue
        reply = sub.get("reply") or {}
        try:
            attempt_int = int(attempt_id) if attempt_id is not None else None
        except (TypeError, ValueError):
            attempt_int = None
        try:
            uid = attempt_user.get(attempt_int) if attempt_int is not None else None
        except (TypeError, ValueError):
            uid = None
        sub_user = sub.get("user")
        # int() без защиты: одна мусорная запись (не-числовой user из API)
        # поднимала ValueError и убивала весь этап трансформа
        sub_user_int = _to_int(sub_user)
        is_author = bool(sub_user_int is not None and sub_user_int == author_uid) or bool(uid and uid == author_uid)
        score = float(sub.get("score") or 0)
        eta_val = int(sub.get("eta") or 0)

        batch.append(
            {
                "id": str(uuid.uuid4()),
                "ssid": int(sid),
                "step_id": int(step_id),
                "cid": course_uuid,
                "status": status,
                "score": score,
                "lang": reply.get("language"),
                "attempt": attempt_int,
                "uid": uid,
                "eta": eta_val,
                "stime": sub_time,
                "author": is_author,
                "now": datetime.now(UTC),
            }
        )

        if len(batch) >= batch_size:
            await session.execute(
                text("""
                    INSERT INTO submissions
                        (id, stepik_submission_id, stepik_step_id, course_id,
                         status, score, language, attempt_id, user_id, eta,
                         submission_time, is_author, created_at)
                    VALUES
                        (:id, :ssid, :step_id, :cid,
                         :status, :score, :lang, :attempt, :uid, :eta,
                         :stime, :author, :now)
                    ON CONFLICT (stepik_submission_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        score = EXCLUDED.score,
                        language = EXCLUDED.language,
                        attempt_id = EXCLUDED.attempt_id,
                        user_id = EXCLUDED.user_id,
                        eta = EXCLUDED.eta,
                        is_author = EXCLUDED.is_author
                """),
                batch,
            )
            total += len(batch)
            logger.info("  ... %d submissions upserted", total)
            batch = []

    if batch:
        await session.execute(
            text("""
                INSERT INTO submissions
                    (id, stepik_submission_id, stepik_step_id, course_id,
                     status, score, language, attempt_id, user_id, eta,
                     submission_time, is_author, created_at)
                VALUES
                    (:id, :ssid, :step_id, :cid,
                     :status, :score, :lang, :attempt, :uid, :eta,
                     :stime, :author, :now)
                ON CONFLICT (stepik_submission_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    score = EXCLUDED.score,
                    language = EXCLUDED.language,
                    attempt_id = EXCLUDED.attempt_id,
                    user_id = EXCLUDED.user_id,
                    eta = EXCLUDED.eta,
                    is_author = EXCLUDED.is_author
            """),
            batch,
        )
        total += len(batch)

    logger.info("  %d submissions upserted", total)
