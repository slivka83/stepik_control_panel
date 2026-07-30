import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.stepik_api import _request, get_finance_token

logger = logging.getLogger(__name__)

API_PAGE_SIZE = 20


def _query_params(extra: dict | None = None, page: int = 1) -> dict:
    p = {"page": page, "page_size": API_PAGE_SIZE}
    if extra:
        p.update(extra)
    return p


async def _paginated_fetch(path: str, token: str, key: str, extra: dict | None = None, max_pages: int = 500) -> list[dict]:
    all_items = []
    page = 1
    while page <= max_pages:
        data = await _request("GET", path, token, _query_params(extra, page))
        items = data.get(key, [])
        if not items:
            break
        all_items.extend(items)
        if not data.get("meta", {}).get("has_next"):
            break
        page += 1
    return all_items


async def _get_fields_mapping(session: AsyncSession, endpoint_name: str) -> dict[str, str]:
    r = await session.execute(
        text("""
            SELECT api_field, db_column FROM meta_field_mapping
            WHERE endpoint_name = :ep AND is_loaded = True
        """),
        {"ep": endpoint_name},
    )
    return {row[0]: row[1] for row in r}


async def _replace_raw_table(session: AsyncSession, raw_table: str, objects: list[dict], mapping: dict[str, str]):
    if not objects:
        return

    try:
        col_r = await session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t
        """), {"t": raw_table})
        table_cols = {row[0] for row in col_r}
    except Exception:
        table_cols = set()

    all_db_cols = [c for c in mapping.values() if not table_cols or c in table_cols]

    try:
        pk_r = await session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t AND column_default LIKE 'nextval(%'
        """), {"t": raw_table})
        serial_pks = {row[0] for row in pk_r}
    except Exception:
        serial_pks = set()

    col_names = [c for c in all_db_cols if c not in serial_pks] + ["_raw_json"]
    if not col_names:
        return

    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)

    try:
        await session.execute(text(f'TRUNCATE TABLE "{raw_table}" RESTART IDENTITY CASCADE'))
    except Exception:
        await session.execute(text(f'DELETE FROM "{raw_table}"'))

    for obj in objects:
        raw_json = json.dumps(obj, ensure_ascii=False)
        values = {"_raw_json": raw_json}
        api_to_db = {v: k for k, v in mapping.items()} if mapping else {}
        for c in col_names:
            if c == "_raw_json":
                continue
            api_field = next((k for k, v in mapping.items() if v == c), c)
            val = obj.get(api_field)
            if val is not None and isinstance(val, (dict, list)):
                values[c] = json.dumps(val, ensure_ascii=False)
            elif val is not None:
                values[c] = str(val)
            else:
                values[c] = None
        await session.execute(
            text(f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders})'),
            values,
        )


async def _upsert_raw_table(session: AsyncSession, raw_table: str, objects: list[dict], mapping: dict[str, str]):
    if not objects:
        return

    try:
        col_r = await session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t
        """), {"t": raw_table})
        table_cols = {row[0] for row in col_r}
    except Exception:
        table_cols = set()

    all_db_cols = [c for c in mapping.values() if not table_cols or c in table_cols]

    try:
        pk_r = await session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t AND column_default LIKE 'nextval(%'
        """), {"t": raw_table})
        serial_pks = {row[0] for row in pk_r}
    except Exception:
        serial_pks = set()

    col_names = [c for c in all_db_cols if c not in serial_pks] + ["_raw_json"]
    if not col_names:
        return

    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)

    # Find the id field for conflict detection (usually the first unique column)
    id_field = None
    for c in col_names:
        if c.endswith("_id") or c in ("id",):
            id_field = c
            break

    conflict_clause = f' ON CONFLICT ("{id_field}") DO NOTHING' if id_field else ''

    for obj in objects:
        raw_json = json.dumps(obj, ensure_ascii=False)
        values = {"_raw_json": raw_json}
        for c in col_names:
            if c == "_raw_json":
                continue
            api_field = next((k for k, v in mapping.items() if v == c), c)
            val = obj.get(api_field)
            if val is not None and isinstance(val, (dict, list)):
                values[c] = json.dumps(val, ensure_ascii=False)
            elif val is not None:
                values[c] = str(val)
            else:
                values[c] = None
        await session.execute(
            text(f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders}){conflict_clause}'),
            values,
        )


async def sync_courses_structure(session: AsyncSession, token: str):
    """Sync courses, sections, units, lessons, steps → raw tables (full_reload)."""
    logger.info("=== Raw: courses structure ===")

    # Courses
    settings = get_settings()
    courses = await _paginated_fetch("/courses", token, "courses", {"teacher": settings.stepik_user_id})
    mapping = await _get_fields_mapping(session, "courses")
    await _replace_raw_table(session, "raw_course", courses, mapping)
    logger.info("  raw_course: %d rows", len(courses))

    # Build course → sections map for section_ids resolution
    section_ids = []
    for c in courses:
        sids = c.get("sections", [])
        if sids:
            section_ids.extend(sids)

    # Sections
    sections = []
    for i in range(0, len(section_ids), 100):
        batch = section_ids[i:i + 100]
        s = await _paginated_fetch("/sections", token, "sections", {"ids[]": batch})
        sections.extend(s)
    mapping = await _get_fields_mapping(session, "sections")
    await _replace_raw_table(session, "raw_section", sections, mapping)
    logger.info("  raw_section: %d rows", len(sections))

    # Units
    unit_ids = []
    for sec in sections:
        uids = sec.get("units", [])
        if uids:
            unit_ids.extend(uids)
    units = []
    for i in range(0, len(unit_ids), 100):
        batch = unit_ids[i:i + 100]
        u = await _paginated_fetch("/units", token, "units", {"ids[]": batch})
        units.extend(u)
    mapping = await _get_fields_mapping(session, "units")
    await _replace_raw_table(session, "raw_unit", units, mapping)
    logger.info("  raw_unit: %d rows", len(units))

    # Lessons
    lesson_ids = list(set(u["lesson"] for u in units if u.get("lesson")))
    lessons = []
    for i in range(0, len(lesson_ids), 100):
        batch = lesson_ids[i:i + 100]
        l = await _paginated_fetch("/lessons", token, "lessons", {"ids[]": batch})
        lessons.extend(l)
    mapping = await _get_fields_mapping(session, "lessons")
    await _replace_raw_table(session, "raw_lesson", lessons, mapping)
    logger.info("  raw_lesson: %d rows", len(lessons))

    # Steps
    step_ids = []
    for lesson in lessons:
        ss = lesson.get("steps", [])
        if ss:
            step_ids.extend(ss)
    steps = []
    for i in range(0, len(step_ids), 100):
        batch = step_ids[i:i + 100]
        s = await _paginated_fetch("/steps", token, "steps", {"ids[]": batch})
        steps.extend(s)
    mapping = await _get_fields_mapping(session, "steps")
    await _replace_raw_table(session, "raw_step", steps, mapping)
    logger.info("  raw_step: %d rows", len(steps))


async def sync_course_grades_and_certs(session: AsyncSession, token: str, course_ids: list[int]):
    """Sync course grades and certificates per course (full_reload, ?course=X).
    Collects all data from all courses first, then replaces tables once."""
    logger.info("=== Raw: course grades & certificates ===")

    mapping_grades = await _get_fields_mapping(session, "course_grades")
    mapping_certs = await _get_fields_mapping(session, "certificates")

    all_grades = []
    all_certs = []
    for cid in course_ids:
        grades = await _paginated_fetch("/course-grades", token, "course-grades", {"course": cid, "is_assistant": "true"})
        all_grades.extend(grades)
        logger.info("    course %d: %d grades", cid, len(grades))

        certs = await _paginated_fetch("/certificates", token, "certificates", {"course": cid})
        all_certs.extend(certs)
        logger.info("    course %d: %d certs", cid, len(certs))

    await _replace_raw_table(session, "raw_course_grade", all_grades, mapping_grades)
    logger.info("  raw_course_grade: %d rows total", len(all_grades))
    await _replace_raw_table(session, "raw_certificate", all_certs, mapping_certs)
    logger.info("  raw_certificate: %d rows total", len(all_certs))


async def sync_submissions(session: AsyncSession, token: str):
    """Sync submissions and attempts (incremental per step)."""
    logger.info("=== Raw: submissions & attempts ===")

    mapping_subs = await _get_fields_mapping(session, "submissions")
    mapping_attempts = await _get_fields_mapping(session, "attempts")

    # Get all steps from raw_step
    r = await session.execute(text("SELECT step_id FROM raw_step"))
    step_ids = [int(row[0]) for row in r if row[0] is not None]

    if not step_ids:
        logger.warning("  no steps, skipping")
        return

    # Track state for incremental sync
    r = await session.execute(
        text("SELECT key, value FROM raw_sync_state WHERE endpoint_name = 'submissions' AND key LIKE 'step_%'"),
    )
    page_state = {int(row[0].split("_", 1)[1]): int(row[1]) for row in r}

    total = 0
    for sid in step_ids:
        last_page = page_state.get(int(sid), 0)
        page = last_page + 1 if last_page > 0 else 1
        step_new = 0
        while page <= 200:
            data = await _request("GET", "/submissions", token,
                                  {"step": sid, "page": page, "page_size": 500})
            objects = data.get("submissions", [])
            if not objects:
                break
            await _upsert_raw_table(session, "raw_submission", objects, mapping_subs)
            step_new += len(objects)
            total += len(objects)

            await session.execute(
                text("INSERT INTO raw_sync_state (endpoint_name, key, value) VALUES ('submissions', :k, :v) ON CONFLICT (endpoint_name, key) DO UPDATE SET value = :v2"),
                {"k": f"step_{sid}", "v": str(page), "v2": str(page)},
            )

            if not data.get("meta", {}).get("has_next"):
                break
            page += 1

        if step_new > 0:
            logger.info("  step %d: +%d (page %d+)", sid, step_new, last_page + 1 if last_page > 0 else 1)
            await session.commit()

    logger.info("  raw_submission: +%d rows (incremental)", total)

    # Author submissions pass
    r = await session.execute(text("SELECT course_id FROM raw_course"))
    course_ids = [int(row[0]) for row in r if row[0] is not None]
    author_total = 0
    for cid in course_ids:
        page = 1
        while page <= 50:
            data = await _request("GET", "/submissions", token,
                                  {"course": cid, "page": page, "page_size": 500})
            objects = data.get("submissions", [])
            if not objects:
                break
            await _upsert_raw_table(session, "raw_submission", objects, mapping_subs)
            author_total += len(objects)
            if not data.get("meta", {}).get("has_next"):
                break
            page += 1
        logger.info("    course %d: author subs so far: %d", cid, author_total)
    logger.info("  raw_submission: +%d rows (author pass)", author_total)

    # Sync attempts for user_id mapping
    r = await session.execute(text("""
        SELECT DISTINCT CAST(json_extract(sub._raw_json, '$.attempt') AS INTEGER) AS attempt_id
        FROM raw_submission sub
        WHERE json_extract(sub._raw_json, '$.attempt') IS NOT NULL
    """))
    attempt_ids = [int(row[0]) for row in r if row[0] is not None]
    total_attempts = 0
    for i in range(0, len(attempt_ids), 100):
        batch = attempt_ids[i:i + 100]
        try:
            attempts = await _paginated_fetch("/attempts", token, "attempts", {"ids[]": batch})
            await _upsert_raw_table(session, "raw_attempt", attempts, mapping_attempts)
            total_attempts += len(attempts)
        except Exception as e:
            logger.warning("  attempts batch error: %s", e)
    logger.info("  raw_attempt: %d rows", total_attempts)


async def sync_financials(session: AsyncSession):
    """Sync financial data (client_credentials)."""
    logger.info("=== Raw: financials ===")

    settings = get_settings()
    token = await get_finance_token(settings.stepik_finance_client_id, settings.stepik_finance_client_secret)
    if not token:
        logger.warning("  no finance token, skipping")
        return

    by_months = await _paginated_fetch("/course-benefit-by-months", token, "course-benefit-by-months")
    mapping = await _get_fields_mapping(session, "course_benefit_by_months")
    await _replace_raw_table(session, "raw_course_benefit_by_month", by_months, mapping)
    logger.info("  raw_course_benefit_by_month: %d rows", len(by_months))

    benefits = await _paginated_fetch("/course-benefits", token, "course-benefits")
    mapping = await _get_fields_mapping(session, "course_benefits")
    await _replace_raw_table(session, "raw_course_benefit", benefits, mapping)
    logger.info("  raw_course_benefit: %d rows", len(benefits))


async def sync_community(session: AsyncSession, token: str):
    """Sync reviews and comments (incremental time for comments)."""
    logger.info("=== Raw: community ===")

    r = await session.execute(text("SELECT course_id FROM raw_course"))
    course_ids = [int(row[0]) for row in r if row[0] is not None]

    # Reviews
    review_ids = []
    for cid in course_ids:
        r = await session.execute(
            text("SELECT review_summary_json FROM raw_course WHERE course_id = :cid"),
            {"cid": cid},
        )
        row = r.fetchone()
        if row and row[0]:
            try:
                rid = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if isinstance(rid, (list, tuple)):
                    review_ids.extend(rid)
                else:
                    review_ids.append(rid)
            except (json.JSONDecodeError, TypeError):
                pass
    review_ids = list(set(int(x) for x in review_ids if x is not None))

    if review_ids:
        review_summaries = []
        for i in range(0, len(review_ids), 100):
            batch = review_ids[i:i + 100]
            rs = await _paginated_fetch("/course-review-summaries", token, "course-review-summaries", {"ids[]": batch})
            review_summaries.extend(rs)
        mapping = await _get_fields_mapping(session, "course_review_summaries")
        await _replace_raw_table(session, "raw_course_review_summary", review_summaries, mapping)
        logger.info("  raw_course_review_summary: %d rows", len(review_summaries))

    # Comments — incremental by time per course
    r = await session.execute(
        text("SELECT key, value FROM raw_sync_state WHERE endpoint_name = 'comments' AND key LIKE 'last_time_course_%'"),
    )
    last_times = {row[0]: row[1] for row in r}

    mapping = await _get_fields_mapping(session, "comments")
    total_new = 0
    for cid in course_ids:
        last_time = last_times.get(f"last_time_course_{cid}", "")
        course_new = 0
        page = 1
        max_time_str = last_time
        while page <= 50:
            data = await _request("GET", "/comments", token,
                                  {"course": cid, "page": page, "page_size": 20})
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
                await _upsert_raw_table(session, "raw_comment", new_objects, mapping)
                course_new += len(new_objects)

                await session.execute(
                    text("INSERT INTO raw_sync_state (endpoint_name, key, value) VALUES ('comments', :k, :v) ON CONFLICT (endpoint_name, key) DO UPDATE SET value = :v2"),
                    {"k": f"last_time_course_{cid}", "v": max_time_str, "v2": max_time_str},
                )

            if not data.get("meta", {}).get("has_next"):
                break
            page += 1

        if course_new > 0:
            logger.info("    course %d: +%d comments", cid, course_new)
            await session.commit()
        total_new += course_new

    logger.info("  raw_comment: +%d rows (incremental_time)", total_new)
