import logging
import uuid
import time
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.config import get_settings
from app.database import async_session
from app.models.models import (
    Course, StudentEnrollment, FinancialSnapshot, User,
)
from app.services.stepik_api import _request, get_finance_token
from app.services.crypto import decrypt_token

logger = logging.getLogger(__name__)

_sync_in_progress = False
_last_sync_completed_at: float = 0

MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

SYNC_COOLDOWN_SECONDS = 3600  # 1 hour


async def _paginated_get(path: str, token: str, params: dict | None = None, key: str | None = None) -> list:
    all_items = []
    page = 1
    while True:
        p = {**(params or {}), "page": page, "page_size": 50}
        data = await _request("GET", path, token, p)
        items_key = key or path.lstrip("/")
        items = data.get(items_key, [])
        all_items.extend(items)
        meta = data.get("meta", {})
        if not meta.get("has_next", False) or not items:
            break
        page += 1
    return all_items


def can_sync() -> bool:
    if _sync_in_progress:
        return False
    if _last_sync_completed_at == 0:
        return True
    return (time.time() - _last_sync_completed_at) >= SYNC_COOLDOWN_SECONDS


async def sync_courses_and_enrollments():
    """Fetch from API first, then atomically replace DB data."""
    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        user_db = result.scalar_one_or_none()
        if not user_db:
            logger.warning("No user found, skipping course sync")
            return
        token = decrypt_token(user_db.access_token)
        user_id_db = user_db.id

    settings = get_settings()
    stepik_user_id = settings.stepik_user_id
    if not stepik_user_id:
        logger.warning("STEPIK_USER_ID not set")
        return

    logger.info("Syncing courses for user %s...", stepik_user_id)

    courses_data = await _paginated_get("/courses", token, {"teacher": stepik_user_id}, "courses")
    logger.info("Found %d courses", len(courses_data))

    all_grades: dict[int, list] = {}
    all_certs: dict[int, set] = {}

    for c in courses_data:
        sid = c["id"]
        logger.info("  [%d] %s...", sid, c.get("title", "?")[:50])

        try:
            grades = await _paginated_get(
                "/course-grades", token,
                {"course": sid, "is_assistant": "true"}, "course-grades"
            )
            all_grades[sid] = grades
        except Exception as e:
            logger.warning("  grades error: %s", e)
            all_grades[sid] = []

        try:
            certs = await _paginated_get("/certificates", token, {"course": sid}, "certificates")
            all_certs[sid] = {cert["user"] for cert in certs}
        except Exception:
            all_certs[sid] = set()

    async with async_session() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM student_enrollments"))
            await session.execute(text("DELETE FROM courses"))

            course_map = {}
            for c in courses_data:
                course = Course(
                    id=uuid.uuid4(),
                    user_id=user_id_db,
                    stepik_course_id=c["id"],
                    title=c.get("title", "Untitled"),
                    status="Published" if c.get("is_published", True) else "Draft",
                    health_score=100.0,
                )
                session.add(course)
                await session.flush()
                course_map[c["id"]] = course

            total_enrollments = 0
            total_certs = 0
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            for sid, grades in all_grades.items():
                local_course = course_map.get(sid)
                if not local_course:
                    continue
                cert_users = all_certs.get(sid, set())

                for grade in grades:
                    student_id = grade.get("user")
                    if not student_id:
                        continue

                    score = grade.get("score", 0) or 0
                    is_passed = student_id in cert_users

                    last_viewed_ts = grade.get("last_viewed")
                    if last_viewed_ts:
                        if isinstance(last_viewed_ts, (int, float)):
                            last_viewed = datetime.fromtimestamp(int(last_viewed_ts), tz=timezone.utc).replace(tzinfo=None)
                        else:
                            last_viewed = datetime.fromisoformat(
                                str(last_viewed_ts).replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                    else:
                        last_viewed = now

                    enrollment = StudentEnrollment(
                        id=uuid.uuid4(),
                        course_id=local_course.id,
                        student_id=student_id,
                        cohort_status="Active" if score > 0 else "Passive",
                        points_earned=int(score),
                        certificate_issued=is_passed,
                        last_viewed_at=last_viewed,
                    )
                    session.add(enrollment)
                    total_enrollments += 1

                total_certs += len(cert_users)

            logger.info("Synced: %d courses, %d enrollments, %d certificates",
                       len(courses_data), total_enrollments, total_certs)


async def sync_financials():
    """Sync financial data from Stepik API to FinancialSnapshot."""
    settings = get_settings()
    try:
        token = await get_finance_token(
            settings.stepik_finance_client_id,
            settings.stepik_finance_client_secret,
        )
    except Exception as e:
        logger.error("Failed to get finance token: %s", e)
        return

    try:
        by_months = await _paginated_get("/course-benefit-by-months", token)
        benefits = await _paginated_get("/course-benefits", token)
    except Exception as e:
        logger.error("Failed to fetch financial data: %s", e)
        return

    async with async_session() as session:
        courses = (await session.execute(select(Course))).scalars().all()
        course_map = {c.stepik_course_id: c.title for c in courses}

    total_turnover = sum(float(m.get("total_turnover", 0) or 0) for m in by_months)
    total_income = sum(float(m.get("total_user_income", 0) or 0) for m in by_months)
    total_refunds = sum(float(m.get("total_refunds", 0) or 0) for m in by_months)
    total_payments = sum(int(m.get("count_payments", 0) or 0) for m in by_months)

    now = datetime.now(timezone.utc)
    current_month_turnover = 0.0
    current_month_income = 0.0
    for m in by_months:
        if m.get("year") == now.year and m.get("month") == now.month:
            current_month_turnover = float(m.get("total_turnover", 0) or 0)
            current_month_income = float(m.get("total_user_income", 0) or 0)

    months_data = []
    for m in sorted(by_months, key=lambda x: (x.get("year", 0), x.get("month", 0))):
        year = m.get("year", 0)
        month_num = m.get("month", 0)
        months_data.append({
            "month": f"{MONTH_NAMES.get(month_num, str(month_num))} {year}",
            "year": year,
            "month_num": month_num,
            "turnover": float(m.get("total_turnover", 0) or 0),
            "income": float(m.get("total_user_income", 0) or 0),
            "refunds": float(m.get("total_refunds", 0) or 0),
            "payments_count": int(m.get("count_payments", 0) or 0),
            "refunds_count": int(m.get("count_refunds", 0) or 0),
        })

    course_stats: dict[int, dict] = {}
    for b in benefits:
        cid = b.get("course")
        if cid not in course_stats:
            course_stats[cid] = {
                "course_id": cid,
                "title": course_map.get(cid, f"Курс #{cid}"),
                "turnover": 0, "income": 0, "refunds": 0, "payments": 0,
            }
        status = b.get("status", "")
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        course_stats[cid]["payments"] += 1
        if status == "refunded":
            course_stats[cid]["refunds"] += amount
            course_stats[cid]["turnover"] -= payment_amount
        else:
            course_stats[cid]["turnover"] += payment_amount
            course_stats[cid]["income"] += amount

    course_list = sorted(course_stats.values(), key=lambda x: x["turnover"], reverse=True)

    recent_payments = []
    for b in sorted(benefits, key=lambda x: x.get("time", ""), reverse=True)[:30]:
        recent_payments.append({
            "id": b.get("id"),
            "course": course_map.get(b.get("course"), f"Курс #{b.get('course')}"),
            "amount": float(b.get("amount", 0) or 0),
            "payment_amount": float(b.get("payment_amount", 0) or 0),
            "status": b.get("status", ""),
            "time": b.get("time", ""),
            "buyer": b.get("buyer"),
            "promo_code": b.get("promo_code"),
            "currency": b.get("currency_code", "RUB"),
        })

    snapshot_data = {
        "summary": {
            "total_turnover": total_turnover,
            "total_income": total_income,
            "total_refunds": total_refunds,
            "total_payments": total_payments,
            "net_income": total_income - total_refunds,
            "current_month_turnover": current_month_turnover,
            "current_month_income": current_month_income,
        },
        "months": months_data,
        "courses": course_list,
        "recent_payments": recent_payments,
    }

    async with async_session() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM financial_snapshots"))
            snapshot = FinancialSnapshot(
                id=uuid.uuid4(),
                data=snapshot_data,
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(snapshot)

    logger.info("Financial snapshot saved: %d months, %d courses, %d payments",
               len(months_data), len(course_list), len(recent_payments))


async def sync_all(force: bool = False):
    """Run all sync jobs. Skips if cooldown hasn't passed (unless force=True)."""
    global _sync_in_progress, _last_sync_completed_at

    if _sync_in_progress:
        logger.info("Sync already in progress, skipping")
        return {"status": "skipped", "reason": "already_in_progress"}

    if not force and not can_sync():
        remaining = int(SYNC_COOLDOWN_SECONDS - (time.time() - _last_sync_completed_at))
        logger.info("Sync skipped, cooldown remaining: %ds", remaining)
        return {"status": "skipped", "reason": "cooldown", "remaining_seconds": remaining}

    _sync_in_progress = True
    logger.info("=== Full sync started ===")
    try:
        await sync_courses_and_enrollments()
        await sync_financials()
        _last_sync_completed_at = time.time()
        logger.info("=== Full sync completed ===")
        return {"status": "ok"}
    except Exception as e:
        logger.error("Sync failed: %s", e)
        return {"status": "error", "detail": str(e)}
    finally:
        _sync_in_progress = False
