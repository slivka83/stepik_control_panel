"""Финансы: raw_course_benefit_by_month + raw_course_benefit → financial_snapshots."""

import contextlib
import json
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
)

logger = logging.getLogger(__name__)


async def transform_financials(session: AsyncSession):
    logger.info("=== Financials ===")

    r = await session.execute(text("SELECT id, stepik_course_id, title FROM courses"))
    course_map = {int(row[1]): {"id": str(row[0]), "title": row[2]} for row in r}

    course_prices = {}
    if course_map:
        r = await session.execute(text("SELECT _raw_json FROM raw_course"))
        for (raw_json,) in r:
            rc = _ensure_json(raw_json)
            cid = rc.get("id")
            if cid in course_map:
                price_val = rc.get("price")
                if price_val is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        course_prices[cid] = float(price_val)

    r = await session.execute(
        text("""
        SELECT _raw_json FROM raw_course_benefit_by_month
    """)
    )
    by_months = [_ensure_json(r[0]) for r in r]

    r = await session.execute(
        text("""
        SELECT _raw_json FROM raw_course_benefit
    """)
    )
    benefits = [_ensure_json(r[0]) for r in r]

    total_turnover = sum(float(m.get("total_turnover", 0) or 0) for m in by_months)
    total_income = sum(float(m.get("total_user_income", 0) or 0) for m in by_months)
    total_refunds = sum(float(m.get("total_refunds", 0) or 0) for m in by_months)
    total_payments = sum(int(m.get("count_payments", 0) or 0) for m in by_months)
    total_refunds_count = sum(int(m.get("count_refunds", 0) or 0) for m in by_months)

    now = datetime.now(UTC)
    current_month_turnover = 0.0
    current_month_income = 0.0
    current_month_payments = 0
    for m in by_months:
        if m.get("year") == now.year and m.get("month") == now.month:
            current_month_turnover = float(m.get("total_turnover", 0) or 0)
            current_month_income = float(m.get("total_user_income", 0) or 0)
            current_month_payments = int(m.get("count_payments", 0) or 0)

    months_data = []
    for m in sorted(by_months, key=lambda x: (x.get("year", 0), x.get("month", 0))):
        year = m.get("year", 0)
        month_num = m.get("month", 0)
        months_data.append(
            {
                "month": f"{MONTH_NAMES.get(month_num, str(month_num))} {year}",
                "year": year,
                "month_num": month_num,
                "turnover": float(m.get("total_turnover", 0) or 0),
                "income": float(m.get("total_user_income", 0) or 0),
                "refunds": float(m.get("total_refunds", 0) or 0),
                "payments_count": int(m.get("count_payments", 0) or 0),
                "refunds_count": int(m.get("count_refunds", 0) or 0),
            }
        )

    course_stats = {}
    for b in benefits:
        cid = b.get("course")
        if cid not in course_stats:
            cm = course_map.get(cid, {})
            course_stats[cid] = {
                "course_id": cid,
                "title": cm.get("title", f"Курс #{cid}"),
                "price": course_prices.get(cid),
                "turnover": 0,
                "income": 0,
                "refunds": 0,
                "payments": 0,
            }
        status = b.get("status", "")
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        cs = course_stats[cid]
        cs["payments"] += 1
        if status == "refunded":
            cs["refunds"] += abs(amount)
            cs["turnover"] -= payment_amount
            cs["income"] += amount
        else:
            cs["turnover"] += payment_amount
            cs["income"] += amount

    promo_stats = {}
    for b in benefits:
        code = b.get("promo_code")
        if code is None:
            continue
        if code not in promo_stats:
            promo_stats[code] = {
                "promo_code": code,
                "payments": 0,
                "turnover": 0,
                "income": 0,
                "refunds": 0,
                "last_used": b.get("time", ""),
            }
        ps = promo_stats[code]
        ps["payments"] += 1
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        if b.get("status") == "refunded":
            ps["refunds"] += abs(amount)
            ps["turnover"] -= payment_amount
            ps["income"] += amount
        else:
            ps["turnover"] += payment_amount
            ps["income"] += amount
        if b.get("time", "") > ps["last_used"]:
            ps["last_used"] = b.get("time", "")

    utm_stats = {}
    for b in benefits:
        last_utm = b.get("last_course_click_utm") or {}
        source = last_utm.get("utm_source")
        if not source:
            continue
        label = UTM_SOURCE_LABELS.get(source, source)
        if label not in utm_stats:
            utm_stats[label] = {
                "utm_source": label,
                "payments": 0,
                "turnover": 0,
                "income": 0,
                "refunds": 0,
                "last_used": b.get("time", ""),
            }
        us = utm_stats[label]
        us["payments"] += 1
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        if b.get("status") == "refunded":
            us["refunds"] += abs(amount)
            us["turnover"] -= payment_amount
            us["income"] += amount
        else:
            us["turnover"] += payment_amount
            us["income"] += amount
        if b.get("time", "") > us["last_used"]:
            us["last_used"] = b.get("time", "")

    recent_payments = []
    buyer_names = await _get_buyer_names(session)
    for b in sorted(benefits, key=lambda x: x.get("time", ""), reverse=True):
        last_utm = b.get("last_course_click_utm") or {}
        utm_source = last_utm.get("utm_source")
        if b.get("is_invoice_payment"):
            channel = "По счету"
        elif b.get("is_z_link_used"):
            channel = "А-ссылка"
        else:
            channel = "Stepik"
        buyer = b.get("buyer")
        try:
            student = buyer_names.get(int(buyer))
        except (TypeError, ValueError):
            student = None
        recent_payments.append(
            {
                "id": b.get("id"),
                "course": course_map.get(b.get("course"), {}).get("title", f"Курс #{b.get('course')}"),
                "amount": float(b.get("amount", 0) or 0),
                "payment_amount": float(b.get("payment_amount", 0) or 0),
                "status": b.get("status", ""),
                "time": b.get("time", ""),
                "buyer": buyer,
                "student": student,
                "promo_code": b.get("promo_code"),
                "currency": b.get("currency_code", "RUB"),
                "channel": channel,
                "is_gift": bool(b.get("is_gift")),
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
        prev_data = prev_row[0] if isinstance(prev_row[0], dict) else json.loads(prev_row[0])
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
            "data": _serialize_data(snapshot_data, session),
                "now": datetime.now(UTC),
        },
    )

    logger.info(
        "  snapshot saved: %d months, %d courses, %d payments",
        len(months_data),
        len(course_stats),
        len(recent_payments),
    )
