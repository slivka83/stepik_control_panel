"""Financial data sync (client_credentials token)."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.stepik_api import StepikAPIError

from .common import _hub, _previous_raw_objects

logger = logging.getLogger(__name__)


async def sync_financials(session: AsyncSession):
    """Sync financial data (client_credentials)."""
    logger.info("=== Raw: financials ===")

    settings = get_settings()
    token = await _hub().get_finance_token(
        settings.stepik_finance_client_id, settings.stepik_finance_client_secret
    )
    if not token:
        logger.warning("  no finance token, skipping")
        return

    by_months = await _hub()._paginated_fetch("/course-benefit-by-months", token, "course-benefit-by-months")
    mapping = await _hub()._get_fields_mapping(session, "course_benefit_by_months")
    await _hub()._replace_raw_table(session, "raw_course_benefit_by_month", by_months, mapping)
    logger.info("  raw_course_benefit_by_month: %d rows", len(by_months))

    benefits = await _hub()._paginated_fetch("/course-benefits", token, "course-benefits")
    mapping = await _hub()._get_fields_mapping(session, "course_benefits")
    await _hub()._replace_raw_table(session, "raw_course_benefit", benefits, mapping)
    logger.info("  raw_course_benefit: %d rows", len(benefits))

    mapping = await _hub()._get_fields_mapping(session, "promo_codes")
    promo_codes: list[dict] = []
    failed_courses: list[int] = []
    course_ids = sorted(set(await _hub()._raw_course_ids(session)))
    for course_id in course_ids:
        try:
            promo_codes.extend(
                await _hub()._paginated_fetch("/promo-codes", token, "promo-codes", {"course": course_id})
            )
        except StepikAPIError as e:
            # Один недоступный курс не должен обнулять финансы всего sync.
            failed_courses.append(course_id)
            logger.warning("  promo-codes course %d: %s — skip", course_id, e)

    if course_ids and len(failed_courses) == len(course_ids) and not promo_codes:
        logger.warning("  all promo-codes requests failed — keeping previous rows")
        return

    # При частичном сбое сохраняем промокоды упавших курсов: иначе флаги
    # is_stepik_side терялись и «подозрительная комиссия» начинала врать.
    promo_codes.extend(
        await _previous_raw_objects(session, "raw_promo_code", "course", failed_courses)
    )

    unique_promos: dict[object, dict] = {}
    for promo in promo_codes:
        key = promo.get("id") if promo.get("id") is not None else promo.get("name")
        if key is not None:
            unique_promos[key] = promo
    await _hub()._replace_raw_table(session, "raw_promo_code", list(unique_promos.values()), mapping)
    logger.info("  raw_promo_code: %d rows", len(unique_promos))
