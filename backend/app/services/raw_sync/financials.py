"""Financial data sync (client_credentials token)."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

from .common import _hub

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
