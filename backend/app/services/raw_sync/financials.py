"""Financial data sync (client_credentials token)."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.stepik_api import StepikAPIError

from .common import _dedupe_by, _hub, _previous_raw_objects, is_fatal_api_error

logger = logging.getLogger(__name__)


async def sync_financials(session: AsyncSession):
    """Sync financial data (client_credentials)."""
    logger.info("=== Raw: financials ===")

    settings = get_settings()
    try:
        token = await _hub().get_finance_token(settings.stepik_finance_client_id, settings.stepik_finance_client_secret)
    except StepikAPIError as e:
        # Нет доступа к финансовому API (не заполнены/отозваны креды) — это не
        # повод валить весь sync: курсы, решения и сообщество должны обновиться.
        if e.status_code in (400, 401, 403):
            logger.warning("  finance token rejected (%s) — skipping financials", e.status_code)
            return
        raise
    if not token:
        logger.warning("  no finance token, skipping")
        return

    by_months = await _hub()._paginated_fetch("/course-benefit-by-months", token, "course-benefit-by-months")
    by_months = _dedupe_by(by_months, "year", "month")

    benefits = await _hub()._paginated_fetch("/course-benefits", token, "course-benefits", max_pages=5000)
    benefits = _dedupe_by(benefits, "id")

    # An empty answer while the raw layer already has finance rows is almost
    # certainly an API/permission glitch, not "the author deleted all sales".
    # Replacing the tables would zero the dashboard until the next sync.
    previous_months = int(
        (await session.execute(text("SELECT count(*) FROM raw_course_benefit_by_month"))).scalar() or 0
    )
    previous_benefits = int((await session.execute(text("SELECT count(*) FROM raw_course_benefit"))).scalar() or 0)
    if (not by_months and previous_months) or (not benefits and previous_benefits):
        raise RuntimeError(
            "Stepik вернул пустые финансовые данные при непустой базе — "
            "синхронизация финансов отменена, чтобы не обнулить отчёты"
        )

    mapping = await _hub()._get_fields_mapping(session, "course_benefit_by_months")
    await _hub()._replace_raw_table(session, "raw_course_benefit_by_month", by_months, mapping)
    logger.info("  raw_course_benefit_by_month: %d rows", len(by_months))

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
            if is_fatal_api_error(e):
                raise
            # Один недоступный курс не должен обнулять финансы всего sync.
            failed_courses.append(course_id)
            logger.warning("  promo-codes course %d: %s — skip", course_id, e)

    if course_ids and len(failed_courses) == len(course_ids) and not promo_codes:
        logger.warning("  all promo-codes requests failed — keeping previous rows")
        return

    # При частичном сбое сохраняем промокоды упавших курсов: иначе флаги
    # is_stepik_side терялись и «подозрительная комиссия» начинала врать.
    promo_codes.extend(await _previous_raw_objects(session, "raw_promo_code", "course", failed_courses))

    unique_promos: dict[object, dict] = {}
    for promo in promo_codes:
        key = promo.get("id") if promo.get("id") is not None else promo.get("name")
        if key is not None:
            unique_promos[key] = promo
    await _hub()._replace_raw_table(session, "raw_promo_code", list(unique_promos.values()), mapping)
    logger.info("  raw_promo_code: %d rows", len(unique_promos))
