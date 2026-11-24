"""Финансы: raw_course_benefit_by_month + raw_course_benefit → financial_snapshots."""

import contextlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MONTH_NAMES, UTM_SOURCE_LABELS
from app.services.transform.common import (
    _ensure_json,
    _get_buyer_names,
    _serialize_data,
    _to_float,
    _to_int,
)

logger = logging.getLogger(__name__)


def _new_bucket(**extra) -> dict:
    """Агрегат платежей: одна формула для курсов/промокодов/UTM."""
    return {**extra, "payments": 0, "turnover": 0.0, "income": 0.0, "refunds": 0.0}


def _apply_benefit(bucket: dict, benefit: dict) -> None:
    """Добавить платёж в агрегат.

    Возврат (`status=refunded`): refunds растёт положительным (abs(amount)),
    оборот уменьшается на payment_amount, доход — на сумму возврата (amount
    отрицательный). Та же формула используется в фильтре по курсам.
    """
    amount = _to_float(benefit.get("amount")) or 0.0
    payment_amount = _to_float(benefit.get("payment_amount")) or 0.0
    bucket["payments"] += 1
    if benefit.get("status") == "refunded":
        bucket["refunds"] += abs(amount)
        bucket["turnover"] -= payment_amount
        bucket["income"] += amount
    else:
        bucket["turnover"] += payment_amount
        bucket["income"] += amount


def _as_bool(value) -> bool | None:
    """Разобрать bool из API/JSON/сырой TEXT-колонки без ложных True."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text_value = str(value).strip().lower()
    if text_value in ("true", "1", "yes"):
        return True
    if text_value in ("false", "0", "no"):
        return False
    return None


def _promo_side_map(rows) -> dict[str, bool | None]:
    """name (нормализованное) → True/False, если промокод на стороне Stepik.

    None — владелец кода неизвестен или разные курсы дали противоречивые
    данные: такой платёж не должен получать ложное предупреждение о комиссии.
    """
    result: dict[str, bool | None] = {}
    for name, is_stepik_side in rows:
        if name is None:
            continue
        key = str(name).strip().casefold()
        if not key:
            continue
        side = _as_bool(is_stepik_side)
        if key in result and side is not None and result[key] is not None and result[key] != side:
            result[key] = None
        elif key not in result:
            result[key] = side
    return result


def _promo_flags(code, promo_is_stepik: dict[str, bool | None]) -> tuple[bool, bool | None]:
    """(авторский, на стороне Stepik) для кода платежа.

    False/None — код неизвестен или данные противоречивы: не выдаём его за
    авторский и не выдаём за Stepik, чтобы не показывать ложные предупреждения
    о комиссии.
    """
    if not code:
        return False, False
    key = str(code).strip().casefold()
    if key not in promo_is_stepik:
        return False, None
    is_stepik = promo_is_stepik[key]
    if is_stepik is None:
        return False, None
    return (not is_stepik), is_stepik


async def transform_financials(session: AsyncSession):
    logger.info("=== Financials ===")

    r = await session.execute(text("SELECT id, stepik_course_id, title FROM courses"))
    course_map = {int(row[1]): {"id": str(row[0]), "title": row[2]} for row in r}

    course_prices: dict[int, float] = {}
    if course_map:
        r = await session.execute(text("SELECT _raw_json FROM raw_course"))
        for (raw_json,) in r:
            rc = _ensure_json(raw_json)
            cid = _to_int(rc.get("id")) if isinstance(rc, dict) else None
            if cid in course_map:
                price_val = rc.get("price")
                if price_val is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        course_prices[cid] = float(price_val)

    r = await session.execute(text("SELECT _raw_json FROM raw_course_benefit_by_month"))
    by_months = [obj for row in r if isinstance(obj := _ensure_json(row[0]), dict)]

    r = await session.execute(text("SELECT _raw_json FROM raw_course_benefit"))
    benefits = [obj for row in r if isinstance(obj := _ensure_json(row[0]), dict)]

    # Авторские промокоды: `is_stepik_side=False` в /api/promo-codes.
    r = await session.execute(text("SELECT name, is_stepik_side FROM raw_promo_code"))
    promo_is_stepik = _promo_side_map(r)

    total_turnover = sum(_to_float(m.get("total_turnover")) or 0.0 for m in by_months)
    total_income = sum(_to_float(m.get("total_user_income")) or 0.0 for m in by_months)
    total_refunds = sum(_to_float(m.get("total_refunds")) or 0.0 for m in by_months)
    total_payments = sum(_to_int(m.get("count_payments")) or 0 for m in by_months)
    total_refunds_count = sum(_to_int(m.get("count_refunds")) or 0 for m in by_months)

    now = datetime.now(UTC)
    current_month_turnover = 0.0
    current_month_income = 0.0
    current_month_payments = 0
    for m in by_months:
        if _to_int(m.get("year")) == now.year and _to_int(m.get("month")) == now.month:
            current_month_turnover = _to_float(m.get("total_turnover")) or 0.0
            current_month_income = _to_float(m.get("total_user_income")) or 0.0
            current_month_payments = _to_int(m.get("count_payments")) or 0

    months_data = []
    for m in sorted(by_months, key=lambda x: (_to_int(x.get("year")) or 0, _to_int(x.get("month")) or 0)):
        year = _to_int(m.get("year"))
        month_num = _to_int(m.get("month"))
        if year is None or month_num is None or not 1 <= month_num <= 12:
            logger.warning("  skipping benefit-by-month row with invalid year/month: %r", m)
            continue
        months_data.append(
            {
                "month": f"{MONTH_NAMES[month_num]} {year}",
                "year": year,
                "month_num": month_num,
                "turnover": _to_float(m.get("total_turnover")) or 0.0,
                "income": _to_float(m.get("total_user_income")) or 0.0,
                "refunds": _to_float(m.get("total_refunds")) or 0.0,
                "payments_count": _to_int(m.get("count_payments")) or 0,
                "refunds_count": _to_int(m.get("count_refunds")) or 0,
            }
        )

    # Все курсы автора попадают в снапшот, даже без единого платежа: страница
    # «Курсы» показывает их цену и нулевой доход, а не «—».
    course_stats: dict[int, dict] = {
        cid: _new_bucket(course_id=cid, title=cm.get("title") or f"Курс #{cid}", price=course_prices.get(cid))
        for cid, cm in course_map.items()
    }
    promo_stats: dict[str, dict] = {}
    utm_stats: dict[str, dict] = {}

    for b in benefits:
        cid = _to_int(b.get("course"))
        cs = course_stats.get(cid)
        if cs is None:
            cs = course_stats[cid] = _new_bucket(
                course_id=cid, title=f"Курс #{cid}", price=course_prices.get(cid)
            )
        _apply_benefit(cs, b)

        code = b.get("promo_code")
        if code:
            ps = promo_stats.setdefault(
                code, _new_bucket(promo_code=code, last_used=b.get("time", "") or "")
            )
            _apply_benefit(ps, b)
            ps["last_used"] = max(ps["last_used"], b.get("time", "") or "")

        last_utm = b.get("last_course_click_utm") or {}
        source = last_utm.get("utm_source") if isinstance(last_utm, dict) else None
        if source:
            label = UTM_SOURCE_LABELS.get(source, source)
            us = utm_stats.setdefault(
                label, _new_bucket(utm_source=label, last_used=b.get("time", "") or "")
            )
            _apply_benefit(us, b)
            us["last_used"] = max(us["last_used"], b.get("time", "") or "")

    recent_payments = []
    buyer_names = await _get_buyer_names(session)
    for b in sorted(benefits, key=lambda x: x.get("time", "") or "", reverse=True):
        last_utm = b.get("last_course_click_utm") or {}
        if not isinstance(last_utm, dict):
            last_utm = {}
        utm_source = last_utm.get("utm_source")
        if b.get("is_invoice_payment"):
            channel = "По счету"
        elif b.get("is_z_link_used"):
            channel = "А-ссылка"
        else:
            channel = "Stepik"
        buyer = _to_int(b.get("buyer"))
        student = buyer_names.get(buyer) if buyer is not None else None
        promo_code = b.get("promo_code")
        promo_is_author, promo_is_stepik_flag = _promo_flags(promo_code, promo_is_stepik)
        recent_payments.append(
            {
                "id": b.get("id"),
                "course": course_map.get(_to_int(b.get("course")), {}).get(
                    "title", f"Курс #{b.get('course')}"
                ),
                "amount": _to_float(b.get("amount")) or 0.0,
                "payment_amount": _to_float(b.get("payment_amount")) or 0.0,
                "status": b.get("status", ""),
                "time": b.get("time", ""),
                "buyer": buyer,
                "student": student,
                "promo_code": promo_code,
                "promo_is_author": promo_is_author,
                "promo_is_stepik": promo_is_stepik_flag,
                "currency": b.get("currency_code", "RUB"),
                "channel": channel,
                "is_gift": _as_bool(b.get("is_gift")) is True,
                "utm_source": utm_source,
                "utm_source_label": UTM_SOURCE_LABELS.get(utm_source, utm_source),
                "raw": b,
            }
        )

    snapshot_data = {
        "summary": {
            "total_turnover": total_turnover,
            "total_income": total_income,
            "total_refunds": total_refunds,
            "total_payments": total_payments,
            "total_refunds_count": total_refunds_count,
            "current_month_turnover": current_month_turnover,
            "current_month_income": current_month_income,
            "current_month_payments": current_month_payments,
        },
        "months": months_data,
        "courses": sorted(course_stats.values(), key=lambda x: x["turnover"], reverse=True),
        "promos": sorted(promo_stats.values(), key=lambda x: x["last_used"], reverse=True),
        "utms": sorted(utm_stats.values(), key=lambda x: x["last_used"], reverse=True),
        "recent_payments": recent_payments,
    }

    r = await session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
    prev_row = r.fetchone()
    if prev_row:
        prev_data = _ensure_json(prev_row[0])
        if isinstance(prev_data, dict) and prev_data.get("community"):
            snapshot_data["community"] = prev_data["community"]

    await session.execute(text("DELETE FROM financial_snapshots"))
    await session.execute(
        text("""
            INSERT INTO financial_snapshots (id, data, updated_at)
            VALUES (:id, :data, :now)
        """),
        {
            "id": str(uuid.uuid4()),
            "data": _serialize_data(snapshot_data),
            "now": datetime.now(UTC),
        },
    )

    logger.info(
        "  snapshot saved: %d months, %d courses, %d payments",
        len(months_data),
        len(course_stats),
        len(recent_payments),
    )
