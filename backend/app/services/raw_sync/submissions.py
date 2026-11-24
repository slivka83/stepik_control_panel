"""Incremental submissions sync: per-step pass, per-course author pass, attempts."""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.stepik_api import StepikAPIError

from .common import _as_int, _hub, _raw_course_ids, _save_sync_state

logger = logging.getLogger(__name__)

STATE_ENDPOINT = "submissions"
# 5000 страниц × 20 = 100 000 решений на шаг. Лимит защищает от вечного
# has_next=true, но не отрезает популярный шаг на 40 000 (как прежние 2000).
MAX_PAGES = 5000


def _page_state_key(prefix: str, value: int) -> str:
    return f"{prefix}_{value}"


async def _load_page_state(session: AsyncSession, prefix: str) -> dict[int, int]:
    r = await session.execute(
        text(
            "SELECT key, value FROM raw_sync_state "
            f"WHERE endpoint_name = '{STATE_ENDPOINT}' AND key LIKE '{prefix}_%'"
        ),
    )
    return {int(row[0].split("_", 1)[1]): int(row[1]) for row in r}


async def _step_ids(session: AsyncSession) -> list[int]:
    """All non-theory steps: text-шаги не опрашиваем (на них нет решений)."""
    r = await session.execute(text("SELECT step_id, _raw_json FROM raw_step"))
    step_ids = []
    for sid, raw_json in r:
        step_id = _as_int(sid)
        if step_id is None:
            continue
        if _hub()._is_text_step(raw_json):
            continue
        step_ids.append(step_id)
    return step_ids


async def _sync_step_submissions(
    session: AsyncSession, token: str, mapping_subs: dict[str, str], step_ids: list[int]
) -> tuple[int, list[int]]:
    """Download submissions for every step (incremental by step page cursor)."""
    page_state = await _load_page_state(session, "step")

    total = 0
    skipped_steps = []
    for sid in step_ids:
        last_page = page_state.get(int(sid), 0)
        # Продолжаем С последней сохранённой страницы, а не со следующей:
        # API отдаёт решения oldest-first, и новые записи сначала заполняют
        # хвост последней скачанной страницы (она могла быть неполной).
        # Старт с last_page+1 пропускал бы их навсегда (upsert дедупит повторы).
        page = last_page if last_page > 0 else 1
        step_new = 0
        while page <= MAX_PAGES:
            try:
                data = await _hub()._request(
                    "GET", "/submissions", token, {"step": sid, "page": page, "page_size": 500}
                )
            except StepikAPIError as e:
                # Stepik возвращает 404 для удалённых/недоступных шагов и
                # 400 «Bad step parameter» для теоретических (text) шагов, у
                # которых нет решений, — ни то, ни другое не должно убивать sync
                is_deleted = e.status_code == 404
                is_theory_step = e.status_code == 400 and "Bad step parameter" in (e.detail or "")
                if is_deleted or is_theory_step:
                    skipped_steps.append(sid)
                    break
                raise
            objects = data.get("submissions", [])
            if not objects:
                if page > 1 and last_page > 0:
                    # Список сократился (удалённые решения): сохранённой
                    # страницы больше нет. Идём назад, чтобы не пропустить
                    # новые записи, которые заполняют хвост предыдущей.
                    logger.info("  step %d: page %d empty — rewinding cursor", sid, page)
                    last_page = 0
                    page -= 1
                    continue
                if page == 1 and last_page > 0:
                    await _save_sync_state(session, STATE_ENDPOINT, _page_state_key("step", sid), "0")
                    await session.commit()
                break
            # API не возвращает step в объекте submission — шаг известен
            # только из контекста запроса ?step=; пишем его в колонку step
            # (и в _raw_json для целостности)
            for obj in objects:
                obj["step"] = sid
            await _hub()._upsert_raw_table(
                session, "raw_submission", objects, mapping_subs, extra_columns={"step": str(sid)}
            )
            step_new += len(objects)
            total += len(objects)

            await _save_sync_state(session, STATE_ENDPOINT, _page_state_key("step", sid), str(page))
            # Документированный принцип «пишем по мере поступления»: страница
            # и её курсор коммитятся вместе. Иначе падение в конце шага
            # откатывало часы загрузки (до 5000 страниц).
            await session.commit()

            if not data.get("meta", {}).get("has_next"):
                break
            page += 1

        if page > MAX_PAGES and step_new > 0:
            logger.warning(
                "  step %d: достигнут лимит %d страниц — хвост решений не догружен", sid, MAX_PAGES
            )

        if step_new > 0:
            logger.info("  step %d: +%d (page %d+)", sid, step_new, last_page if last_page > 0 else 1)

    if skipped_steps:
        logger.warning("  skipped %d steps (404/теория): %s", len(skipped_steps), skipped_steps[:10])
    logger.info("  raw_submission: +%d rows (incremental)", total)
    return total, skipped_steps


async def _sync_author_submissions(
    session: AsyncSession, token: str, mapping_subs: dict[str, str]
) -> tuple[int, list[int]]:
    """Author pass: submissions of the current user per course (?course=X)."""
    course_page_state = await _load_page_state(session, "course")
    course_ids = await _raw_course_ids(session)
    author_total = 0
    skipped_courses = []
    for cid in course_ids:
        last_page = course_page_state.get(cid, 0)
        # Инкремент с последней страницы (не +1): новые записи заполняют хвост
        # последней страницы; upsert дедуплит уже загруженные строки
        page = last_page if last_page > 0 else 1
        course_new = 0
        while page <= MAX_PAGES:
            try:
                data = await _hub()._request(
                    "GET", "/submissions", token, {"course": cid, "page": page, "page_size": 500}
                )
            except StepikAPIError as e:
                # Курс удалён на Stepik — не убиваем весь sync (как 404-шаги)
                if e.status_code == 404:
                    skipped_courses.append(cid)
                    break
                raise
            objects = data.get("submissions", [])
            if not objects:
                if page > 1 and last_page > 0:
                    logger.info("    course %d: page %d empty — rewinding cursor", cid, page)
                    last_page = 0
                    page -= 1
                    continue
                if page == 1 and last_page > 0:
                    await _save_sync_state(session, STATE_ENDPOINT, _page_state_key("course", cid), "0")
                    await session.commit()
                break
            await _hub()._upsert_raw_table(session, "raw_submission", objects, mapping_subs)
            course_new += len(objects)
            author_total += len(objects)

            await _save_sync_state(session, STATE_ENDPOINT, _page_state_key("course", cid), str(page))
            # Страница и курсор — одной транзакцией (см. step-pass).
            await session.commit()
            if not data.get("meta", {}).get("has_next"):
                break
            page += 1
        if course_new > 0:
            start_page = last_page if last_page > 0 else 1
            logger.info("    course %d: +%d author subs (page %d+)", cid, course_new, start_page)
    if skipped_courses:
        logger.warning("  skipped %d courses (404): %s", len(skipped_courses), skipped_courses[:10])
    logger.info("  raw_submission: +%d rows (author pass, incremental)", author_total)
    return author_total, skipped_courses

async def _sync_attempts(session: AsyncSession, token: str, mapping_attempts: dict[str, str]) -> int:
    """Download only attempts newly referenced by submissions (attempts are immutable)."""
    r = await session.execute(text("SELECT _raw_json FROM raw_submission"))
    attempt_ids = set()
    for (raw_json,) in r:
        try:
            data = raw_json if isinstance(raw_json, dict) else json.loads(raw_json)
            aid = _as_int(data.get("attempt")) if isinstance(data, dict) else None
        except (json.JSONDecodeError, TypeError):
            continue
        if aid is not None:
            attempt_ids.add(aid)
    attempt_ids = sorted(attempt_ids)

    if attempt_ids:
        r = await session.execute(text("SELECT attempt_id FROM raw_attempt WHERE attempt_id IS NOT NULL"))
        existing_ids = {aid for row in r if (aid := _as_int(row[0])) is not None}
        new_ids = [aid for aid in attempt_ids if aid not in existing_ids]
    else:
        new_ids = []

    logger.info(
        "  attempts: %d referenced, %d already loaded, %d to fetch",
        len(attempt_ids),
        len(attempt_ids) - len(new_ids),
        len(new_ids),
    )

    total_attempts = 0
    for i in range(0, len(new_ids), 100):
        batch = new_ids[i : i + 100]
        try:
            attempts = await _hub()._paginated_fetch("/attempts", token, "attempts", {"ids[]": batch})
            await _hub()._upsert_raw_table(session, "raw_attempt", attempts, mapping_attempts)
            total_attempts += len(attempts)
        except StepikAPIError as e:
            # Удалённые попытки (404) не должны убивать sync; остальные ошибки
            # нельзя глотать: без attempt submissions остаются без user_id и
            # is_author, и статистика студентов молча искажается.
            if e.status_code == 404:
                logger.warning("  attempts batch %d: 404 (deleted) — skip", i // 100)
                continue
            raise
    await session.commit()
    logger.info("  raw_attempt: +%d rows (incremental)", total_attempts)
    return total_attempts


async def sync_submissions(session: AsyncSession, token: str):
    """Sync submissions and attempts (incremental: per-step, per-course, attempts delta)."""
    logger.info("=== Raw: submissions & attempts ===")

    mapping_subs = await _hub()._get_fields_mapping(session, "submissions")
    mapping_attempts = await _hub()._get_fields_mapping(session, "attempts")

    step_ids = await _step_ids(session)
    if not step_ids:
        logger.warning("  no steps, skipping")
        return

    await _sync_step_submissions(session, token, mapping_subs, step_ids)
    await _sync_author_submissions(session, token, mapping_subs)
    await _sync_attempts(session, token, mapping_attempts)
