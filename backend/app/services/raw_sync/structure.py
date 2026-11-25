"""Full reload of the course structure: courses → sections → units → lessons → steps."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.stepik_api import StepikAPIError, get_user_profile

from .common import _as_int, _dedupe_by, _hub, _previous_raw_objects

logger = logging.getLogger(__name__)


async def _fetch_by_ids(token: str, path: str, key: str, ids: list[int]) -> list[dict]:
    """Fetch objects by `?ids[]=` in batches of 100.

    A 404 batch (objects deleted on Stepik between the parent and child
    requests) is retried one id at a time instead of dropping the whole batch:
    a single deleted id must not hide the other 99 valid objects from the
    full reload.
    """
    items: list[dict] = []
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        try:
            items.extend(await _hub()._paginated_fetch(path, token, key, {"ids[]": batch}, max_pages=10))
        except StepikAPIError as e:
            if e.status_code != 404:
                raise
            logger.warning("  %s batch %d: 404 — retrying ids individually", path, i // 100)
            for single_id in batch:
                try:
                    items.extend(await _hub()._paginated_fetch(path, token, key, {"ids[]": [single_id]}, max_pages=10))
                except StepikAPIError as inner:
                    if inner.status_code == 404:
                        logger.warning("  %s id %s: 404 (deleted) — skip", path, single_id)
                        continue
                    raise
    return items


async def sync_courses_structure(session: AsyncSession, token: str):
    """Sync courses, sections, units, lessons, steps → raw tables (full_reload)."""
    logger.info("=== Raw: courses structure ===")

    settings = get_settings()
    owner_id: int | None = settings.stepik_user_id
    if not owner_id:
        # STEPIK_USER_ID=0 документирован как «без проверки владельца», но
        # ?teacher=0 возвращает пустой список — и полный reload затирал все
        # курсы вместе с дочерними данными. Берём владельца токена.
        profile = await get_user_profile(token)
        owner_id = _as_int(profile.get("user")) if isinstance(profile, dict) else None
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
    section_ids = list(
        dict.fromkeys(
            sid
            for course in courses
            for raw_sid in (course.get("sections") or [])
            if (sid := _as_int(raw_sid)) is not None
        )
    )
    sections = await _fetch_by_ids(token, "/sections", "sections", section_ids)
    sections = _dedupe_by(sections, "id")
    mapping = await _hub()._get_fields_mapping(session, "sections")
    await _hub()._replace_raw_table(session, "raw_section", sections, mapping)
    logger.info("  raw_section: %d rows", len(sections))

    unit_ids = list(
        dict.fromkeys(
            uid
            for section in sections
            for raw_uid in (section.get("units") or [])
            if (uid := _as_int(raw_uid)) is not None
        )
    )
    units = await _fetch_by_ids(token, "/units", "units", unit_ids)
    units = _dedupe_by(units, "id")
    mapping = await _hub()._get_fields_mapping(session, "units")
    await _hub()._replace_raw_table(session, "raw_unit", units, mapping)
    logger.info("  raw_unit: %d rows", len(units))

    lesson_ids = sorted({lid for unit in units if (lid := _as_int(unit.get("lesson"))) is not None})
    lessons = await _fetch_by_ids(token, "/lessons", "lessons", lesson_ids)
    lessons = _dedupe_by(lessons, "id")
    mapping = await _hub()._get_fields_mapping(session, "lessons")
    await _hub()._replace_raw_table(session, "raw_lesson", lessons, mapping)
    logger.info("  raw_lesson: %d rows", len(lessons))

    step_ids = list(
        dict.fromkeys(
            sid
            for lesson in lessons
            for raw_sid in (lesson.get("steps") or [])
            if (sid := _as_int(raw_sid)) is not None
        )
    )

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
    skipped_courses: list[int] = []
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
            skipped_courses.append(cid)
            logger.warning("    course %d: 404 (deleted on Stepik) — keep previous rows", cid)

    # A 404 for one course must not erase its grades/enrollments: without this
    # the full reload below would replace the whole table with only the
    # successful courses, and the students page/cohorts would suddenly empty.
    if skipped_courses:
        all_grades.extend(await _previous_raw_objects(session, "raw_course_grade", "course_id", skipped_courses))
        all_certs.extend(await _previous_raw_objects(session, "raw_certificate", "course_id", skipped_courses))

    grades = _dedupe_by(all_grades, "course", "user")
    certs = _dedupe_by(all_certs, "id")
    await _hub()._replace_raw_table(session, "raw_course_grade", grades, mapping_grades)
    logger.info("  raw_course_grade: %d rows total", len(grades))
    await _hub()._replace_raw_table(session, "raw_certificate", certs, mapping_certs)
    logger.info("  raw_certificate: %d rows total", len(certs))
