"""Full reload of the course structure: courses → sections → units → lessons → steps."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.stepik_api import StepikAPIError, get_user_profile

from .common import _dedupe_by, _hub

logger = logging.getLogger(__name__)


async def _fetch_by_ids(token: str, path: str, key: str, ids: list[int]) -> list[dict]:
    """Fetch objects by `?ids[]=` in batches of 100.

    A 404 batch (objects deleted on Stepik between the parent and child
    requests) is skipped instead of aborting the whole structure sync.
    """
    items: list[dict] = []
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        try:
            items.extend(
                await _hub()._paginated_fetch(path, token, key, {"ids[]": batch}, max_pages=10)
            )
        except StepikAPIError as e:
            if e.status_code != 404:
                raise
            logger.warning("  %s batch %d: 404 (deleted on Stepik) — skip", path, i // 100)
    return items


async def sync_courses_structure(session: AsyncSession, token: str):
    """Sync courses, sections, units, lessons, steps → raw tables (full_reload)."""
    logger.info("=== Raw: courses structure ===")

    settings = get_settings()
    owner_id = settings.stepik_user_id
    if not owner_id:
        # STEPIK_USER_ID=0 документирован как «без проверки владельца», но
        # ?teacher=0 возвращает пустой список — и полный reload затирал все
        # курсы вместе с дочерними данными. Берём владельца токена.
        profile = await get_user_profile(token)
        try:
            owner_id = int(profile.get("user")) if isinstance(profile, dict) else None
        except (TypeError, ValueError):
            owner_id = None
    if not owner_id:
        raise RuntimeError(
            "STEPIK_USER_ID не задан, и не удалось определить владельца токена: "
            "синхронизация отменена, чтобы не удалить существующие курсы"
        )

    courses = await _hub()._paginated_fetch("/courses", token, "courses", {"teacher": owner_id})
    courses = _dedupe_by(courses, "id")
    if not courses:
        # Пустой ответ при непустой базе — почти наверняка сбой API/прав, а не
        # «автор удалил все курсы». Полный reload затёр бы курсы и все витрины.
        r = await session.execute(text("SELECT count(*) FROM raw_course"))
        previous = int(r.scalar() or 0)
        if previous:
            raise RuntimeError(
                "Stepik вернул пустой список курсов, хотя в базе уже есть курсы — "
                "синхронизация отменена, чтобы не удалить данные"
            )
    mapping = await _hub()._get_fields_mapping(session, "courses")
    await _hub()._replace_raw_table(session, "raw_course", courses, mapping)
    logger.info("  raw_course: %d rows", len(courses))

    # ID-списки дедуплицируем: ids[] с повторами тратит запросы впустую и
    # может вернуть один объект дважды (дубли в витринах структуры).
    section_ids = list(dict.fromkeys(sid for c in courses for sid in (c.get("sections") or [])))
    sections = await _fetch_by_ids(token, "/sections", "sections", section_ids)
    sections = _dedupe_by(sections, "id")
    mapping = await _hub()._get_fields_mapping(session, "sections")
    await _hub()._replace_raw_table(session, "raw_section", sections, mapping)
    logger.info("  raw_section: %d rows", len(sections))

    unit_ids = list(dict.fromkeys(uid for sec in sections for uid in (sec.get("units") or [])))
    units = await _fetch_by_ids(token, "/units", "units", unit_ids)
    units = _dedupe_by(units, "id")
    mapping = await _hub()._get_fields_mapping(session, "units")
    await _hub()._replace_raw_table(session, "raw_unit", units, mapping)
    logger.info("  raw_unit: %d rows", len(units))

    lesson_ids = sorted({u["lesson"] for u in units if u.get("lesson")})
    lessons = await _fetch_by_ids(token, "/lessons", "lessons", lesson_ids)
    lessons = _dedupe_by(lessons, "id")
    mapping = await _hub()._get_fields_mapping(session, "lessons")
    await _hub()._replace_raw_table(session, "raw_lesson", lessons, mapping)
    logger.info("  raw_lesson: %d rows", len(lessons))

    step_ids = list(dict.fromkeys(sid for lesson in lessons for sid in (lesson.get("steps") or [])))

    steps = await _fetch_by_ids(token, "/steps", "steps", step_ids)
    steps = _dedupe_by(steps, "id")
    mapping = await _hub()._get_fields_mapping(session, "steps")
    await _hub()._replace_raw_table(session, "raw_step", steps, mapping)
    logger.info("  raw_step: %d rows", len(steps))


async def sync_course_grades_and_certs(session: AsyncSession, token: str, course_ids: list[int]):
    """Sync course grades and certificates per course (full_reload, ?course=X).

    Collects all data from all courses first, then replaces tables once.
    """
    logger.info("=== Raw: course grades & certificates ===")

    mapping_grades = await _hub()._get_fields_mapping(session, "course_grades")
    mapping_certs = await _hub()._get_fields_mapping(session, "certificates")

    all_grades = []
    all_certs = []
    for cid in course_ids:
        try:
            grades = await _hub()._paginated_fetch(
                "/course-grades",
                token,
                "course-grades",
                {"course": cid, "is_assistant": "true"},
                max_pages=5000,
            )
            all_grades.extend(grades)
            logger.info("    course %d: %d grades", cid, len(grades))

            certs = await _hub()._paginated_fetch(
                "/certificates", token, "certificates", {"course": cid}, max_pages=5000
            )
            all_certs.extend(certs)
            logger.info("    course %d: %d certs", cid, len(certs))
        except StepikAPIError as e:
            # Курс удалён между structure и grades — не убиваем весь sync.
            if e.status_code != 404:
                raise
            logger.warning("    course %d: 404 (deleted on Stepik) — skip", cid)

    grades = _dedupe_by(all_grades, "course", "user")
    certs = _dedupe_by(all_certs, "id")
    await _hub()._replace_raw_table(session, "raw_course_grade", grades, mapping_grades)
    logger.info("  raw_course_grade: %d rows total", len(grades))
    await _hub()._replace_raw_table(session, "raw_certificate", certs, mapping_certs)
    logger.info("  raw_certificate: %d rows total", len(certs))
