"""Full reload of the course structure: courses → sections → units → lessons → steps."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

from .common import _hub

logger = logging.getLogger(__name__)


async def _fetch_by_ids(token: str, path: str, key: str, ids: list[int]) -> list[dict]:
    """Fetch objects by `?ids[]=` in batches of 100."""
    items: list[dict] = []
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        items.extend(await _hub()._paginated_fetch(path, token, key, {"ids[]": batch}))
    return items


async def sync_courses_structure(session: AsyncSession, token: str):
    """Sync courses, sections, units, lessons, steps → raw tables (full_reload)."""
    logger.info("=== Raw: courses structure ===")

    settings = get_settings()
    courses = await _hub()._paginated_fetch("/courses", token, "courses", {"teacher": settings.stepik_user_id})
    mapping = await _hub()._get_fields_mapping(session, "courses")
    await _hub()._replace_raw_table(session, "raw_course", courses, mapping)
    logger.info("  raw_course: %d rows", len(courses))

    section_ids = []
    for c in courses:
        section_ids.extend(c.get("sections", []) or [])

    sections = await _fetch_by_ids(token, "/sections", "sections", section_ids)
    mapping = await _hub()._get_fields_mapping(session, "sections")
    await _hub()._replace_raw_table(session, "raw_section", sections, mapping)
    logger.info("  raw_section: %d rows", len(sections))

    unit_ids = []
    for sec in sections:
        unit_ids.extend(sec.get("units", []) or [])

    units = await _fetch_by_ids(token, "/units", "units", unit_ids)
    mapping = await _hub()._get_fields_mapping(session, "units")
    await _hub()._replace_raw_table(session, "raw_unit", units, mapping)
    logger.info("  raw_unit: %d rows", len(units))

    lesson_ids = list(set(u["lesson"] for u in units if u.get("lesson")))
    lessons = await _fetch_by_ids(token, "/lessons", "lessons", lesson_ids)
    mapping = await _hub()._get_fields_mapping(session, "lessons")
    await _hub()._replace_raw_table(session, "raw_lesson", lessons, mapping)
    logger.info("  raw_lesson: %d rows", len(lessons))

    step_ids = []
    for lesson in lessons:
        step_ids.extend(lesson.get("steps", []) or [])

    steps = await _fetch_by_ids(token, "/steps", "steps", step_ids)
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
        grades = await _hub()._paginated_fetch(
            "/course-grades",
            token,
            "course-grades",
            {"course": cid, "is_assistant": "true"},
        )
        all_grades.extend(grades)
        logger.info("    course %d: %d grades", cid, len(grades))

        certs = await _hub()._paginated_fetch("/certificates", token, "certificates", {"course": cid})
        all_certs.extend(certs)
        logger.info("    course %d: %d certs", cid, len(certs))

    await _hub()._replace_raw_table(session, "raw_course_grade", all_grades, mapping_grades)
    logger.info("  raw_course_grade: %d rows total", len(all_grades))
    await _hub()._replace_raw_table(session, "raw_certificate", all_certs, mapping_certs)
    logger.info("  raw_certificate: %d rows total", len(all_certs))
