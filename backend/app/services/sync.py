import logging
import uuid
import time
import asyncio
import threading
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker as _sessionmaker

from app.config import get_settings
import app.database as _db
from app.models import (
    Course, StudentEnrollment, FinancialSnapshot, User, StepSyncState,
)
from app.services.stepik_api import _request, get_finance_token
from app.services.crypto import decrypt_token

logger = logging.getLogger(__name__)

# Local reference to the default DB session (can be overridden by sync_all_sync in a thread)
async_session = _db.async_session

_sync_lock = threading.Lock()
_sync_in_progress = False
_sync_progress: int = 0
_sync_step: str = ""
_last_sync_completed_at: float = 0

MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

SYNC_COOLDOWN_SECONDS = 60  # 1 minute


async def _paginated_get(path: str, token: str, params: dict | None = None, key: str | None = None, max_pages: int = 500, on_page=None) -> list:
    all_items = []
    page = 1
    while True:
        p = {**(params or {}), "page": page, "page_size": 500}
        data = await _request("GET", path, token, p)
        items_key = key or path.lstrip("/")
        items = data.get(items_key, [])
        all_items.extend(items)
        if on_page:
            on_page(page, len(items))
        meta = data.get("meta", {})
        if not meta.get("has_next", False) or not items:
            break
        page += 1
        if page > max_pages:
            logger.warning("Pagination safety limit reached (%d pages) for %s", max_pages, path)
            break
    return all_items



def calculate_cohort_status(last_viewed_at: datetime | None, date_joined: datetime | None = None) -> str:
    if last_viewed_at is None:
        return "Sleeping"
    if last_viewed_at.tzinfo is None:
        last_viewed_at = last_viewed_at.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - last_viewed_at).days
    if days <= 7:
        return "Active"
    if days <= 30:
        return "Passive"
    if days <= 90:
        return "Fading"
    if date_joined is not None:
        if date_joined.tzinfo is None:
            date_joined = date_joined.replace(tzinfo=timezone.utc)
        days_after_join = (last_viewed_at.date() - date_joined.date()).days
        if 0 <= days_after_join <= 3:
            return "Zombie"
    return "Sleeping"


def can_sync() -> bool:
    with _sync_lock:
        if _sync_in_progress:
            return False
        if _last_sync_completed_at == 0:
            return True
        return (time.time() - _last_sync_completed_at) >= SYNC_COOLDOWN_SECONDS


async def sync_courses_and_enrollments(user_id=None):
    """Fetch from API first, then atomically replace DB data (fetch-then-replace)."""
    global _sync_progress, _sync_step
    async with async_session() as session:
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
        else:
            result = await session.execute(select(User))
        users = result.scalars().all()
        if not users:
            logger.warning("No user found, skipping course sync")
            return
        user_db = users[0]
        token = decrypt_token(user_db.access_token)
        user_id_db = user_db.id

    settings = get_settings()
    stepik_user_id = settings.stepik_user_id
    if not stepik_user_id:
        logger.warning("STEPIK_USER_ID not set")
        return

    _sync_step = "курсы: список"
    logger.info("Syncing courses for user %s...", stepik_user_id)
    _sync_progress = 5

    courses_data = await _paginated_get("/courses", token, {"teacher": stepik_user_id}, "courses")
    _sync_progress = 10
    logger.info("Found %d courses", len(courses_data))

    now = datetime.now(timezone.utc)

    async with async_session() as session:
        async with session.begin():
            existing = (await session.execute(
                select(Course).where(Course.user_id == user_id_db)
            )).scalars().all()
            existing_map = {c.stepik_course_id: c for c in existing}

            seen_ids = set()
            course_map = {}
            for c in courses_data:
                sid = c["id"]
                seen_ids.add(sid)
                pub_raw = c.get("time") or c.get("update_date") or c.get("course_publish") or c.get("start_date")
                pub_dt = None
                if pub_raw:
                    if isinstance(pub_raw, (int, float)):
                        pub_dt = datetime.fromtimestamp(int(pub_raw), tz=timezone.utc)
                    else:
                        try:
                            pub_dt = datetime.fromisoformat(str(pub_raw).replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            pub_dt = None
                if not pub_dt:
                    pub_dt = datetime.now(timezone.utc)
                if sid in existing_map:
                    course = existing_map[sid]
                    course.title = c.get("title", "Untitled")
                    course.status = "Published" if c.get("is_public", False) else "Draft"
                    course.published_at = pub_dt
                else:
                    course = Course(
                        id=uuid.uuid4(),
                        user_id=user_id_db,
                        stepik_course_id=sid,
                        title=c.get("title", "Untitled"),
                        status="Published" if c.get("is_public", False) else "Draft",
                        published_at=pub_dt,
                    )
                    session.add(course)
                await session.flush()
                course_map[sid] = course

            for sid, course in existing_map.items():
                if sid not in seen_ids:
                    await session.delete(course)

    num_courses = len(courses_data)
    for ci, c in enumerate(courses_data):
        sid = c["id"]

        base = 10 + int(30 * ci / num_courses)
        top = 10 + int(30 * (ci + 1) / num_courses)

        def _on_page(page, n, _base=base, _top=top):
            global _sync_progress, _sync_step
            _sync_step = f"курсы: оценки {ci + 1}/{num_courses} (стр. {page})"
            frac = min(page / 350, 1)
            _sync_progress = _base + int((_top - _base) * frac)

        _sync_step = f"курсы: оценки {ci + 1}/{num_courses}"
        logger.info("  [%d] %s...", sid, c.get("title", "?")[:50])

        try:
            grades = await _paginated_get(
                "/course-grades", token,
                {"course": sid, "is_assistant": "true"}, "course-grades",
                on_page=_on_page,
            )
        except Exception as e:
            logger.warning("  grades error: %s", e)
            grades = []

        _sync_step = f"курсы: сертификаты {ci + 1}/{num_courses}"
        try:
            certs = await _paginated_get("/certificates", token, {"course": sid}, "certificates")
            cert_users = {cert["user"] for cert in certs}
        except Exception:
            cert_users = set()

        _sync_progress = top

        enrollments_to_insert = []
        for grade in grades:
            student_id = grade.get("user")
            if not student_id:
                continue

            score = grade.get("score", 0) or 0
            is_passed = student_id in cert_users

            last_viewed_ts = grade.get("last_viewed")
            if last_viewed_ts:
                if isinstance(last_viewed_ts, (int, float)):
                    last_viewed = datetime.fromtimestamp(int(last_viewed_ts), tz=timezone.utc)
                else:
                    last_viewed = datetime.fromisoformat(
                        str(last_viewed_ts).replace("Z", "+00:00")
                    )
            else:
                last_viewed = None

            date_joined_ts = grade.get("date_joined")
            if date_joined_ts:
                if isinstance(date_joined_ts, (int, float)):
                    date_joined = datetime.fromtimestamp(int(date_joined_ts), tz=timezone.utc)
                else:
                    date_joined = datetime.fromisoformat(
                        str(date_joined_ts).replace("Z", "+00:00")
                    )
            else:
                date_joined = None

            enrollments_to_insert.append({
                "student_id": student_id,
                "cohort_status": calculate_cohort_status(last_viewed, date_joined),
                "points_earned": int(score),
                "certificate_issued": is_passed,
                "last_viewed_at": last_viewed,
                "date_joined": date_joined,
            })

        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    text("DELETE FROM student_enrollments WHERE course_id = "
                         "(SELECT id FROM courses WHERE stepik_course_id = :sid)"),
                    {"sid": sid},
                )

                total_enrollments = 0
                for e in enrollments_to_insert:
                    local_course = course_map.get(sid)
                    if not local_course:
                        continue
                    enrollment = StudentEnrollment(
                        id=uuid.uuid4(),
                        course_id=local_course.id,
                        student_id=e["student_id"],
                        cohort_status=e["cohort_status"],
                        points_earned=e["points_earned"],
                        certificate_issued=e["certificate_issued"],
                        last_viewed_at=e["last_viewed_at"],
                        date_joined=e["date_joined"],
                    )
                    session.add(enrollment)
                    total_enrollments += 1

                logger.info("  [%d] synced %d enrollments", sid, total_enrollments)

    logger.info("Synced: %d courses", len(courses_data))


async def sync_submissions(user_id=None):
    """Fetch submissions for code steps only, with incremental pagination.

    Traverses course structure: sections → units → lessons → steps,
    filters to code-type steps only (block.name in code/external-grader/choice),
    then fetches submissions per step with pagination state tracking.
    Last page is re-downloaded on each sync to catch appended submissions.
    Upserts by stepik_submission_id to avoid duplicates.
    """
    global _sync_progress, _sync_step

    CODE_STEP_TYPES = {"code", "external-grader", "choice"}

    async with async_session() as session:
        if user_id:
            courses = (await session.execute(select(Course).where(Course.user_id == user_id))).scalars().all()
        else:
            courses = (await session.execute(select(Course))).scalars().all()
        if not courses:
            logger.warning("No courses found, skipping submissions sync")
            return
        course_map = {c.stepik_course_id: c.id for c in courses}

    async with async_session() as session:
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
        else:
            result = await session.execute(select(User))
        users = result.scalars().all()
        if not users:
            return
        user_db = users[0]
        token = decrypt_token(user_db.access_token)

    _sync_step = "решения: построение структуры курсов"
    _sync_progress = 42

    total_upserted = 0
    total_skipped = 0
    num_courses = len(course_map)

    for i, stepik_course_id in enumerate(course_map):
        _sync_step = f"решения: курс {i + 1}/{num_courses} (структура)"
        try:
            courses_api = await _paginated_get(
                "/courses", token,
                {"ids[]": [stepik_course_id]}, "courses"
            )
            if not courses_api:
                continue
            section_ids = courses_api[0].get("sections", [])
            if not section_ids:
                logger.info("  course %d: no sections, skipping", stepik_course_id)
                continue

            sections = await _paginated_get(
                "/sections", token, {"ids[]": section_ids}, "sections"
            )
            unit_ids = []
            for sec in sections:
                unit_ids.extend(sec.get("units", []))

            all_step_ids = []
            for batch_start in range(0, len(unit_ids), 300):
                batch = unit_ids[batch_start:batch_start + 300]
                units = await _paginated_get(
                    "/units", token, {"ids[]": batch}, "units"
                )
                lesson_ids = list(set(u["lesson"] for u in units if u.get("lesson")))
                if lesson_ids:
                    lessons = await _paginated_get(
                        "/lessons", token, {"ids[]": lesson_ids}, "lessons"
                    )
                    for l in lessons:
                        all_step_ids.extend(l.get("steps", []))

            code_step_ids = []
            for batch_start in range(0, len(all_step_ids), 300):
                batch = all_step_ids[batch_start:batch_start + 300]
                steps_detail = await _paginated_get(
                    "/steps", token, {"ids[]": batch}, "steps"
                )
                for s in steps_detail:
                    block_name = s.get("block", {}).get("name", "")
                    if block_name in CODE_STEP_TYPES:
                        code_step_ids.append(s["id"])

            skipped = len(all_step_ids) - len(code_step_ids)
            logger.info("  course %d: %d steps total, %d code steps (%d skipped)",
                        stepik_course_id, len(all_step_ids), len(code_step_ids), skipped)

            if not code_step_ids:
                continue

            _sync_step = f"решения: курс {i + 1}/{num_courses} ({len(code_step_ids)} шагов)"

            author_sub_ids = set()
            try:
                author_subs = await _paginated_get(
                    "/submissions", token,
                    {"course": stepik_course_id}, "submissions"
                )
                author_sub_ids = {s["id"] for s in author_subs if s.get("id")}
                logger.info("  course %d: %d author submissions", stepik_course_id, len(author_sub_ids))
            except Exception as e:
                logger.warning("  author submissions error for course %d: %s", stepik_course_id, e)

            async with async_session() as session:
                result = await session.execute(
                    select(StepSyncState.step_id, StepSyncState.last_page)
                    .where(StepSyncState.step_id.in_(code_step_ids))
                )
                page_state = dict(result.all())

            course_upserted = 0
            for si, step_id in enumerate(code_step_ids):
                start_page = page_state.get(step_id, 0)
                if start_page == 0:
                    start_page = 1

                base = 42 + int(43 * si / len(code_step_ids))
                top = 42 + int(43 * (si + 1) / len(code_step_ids))

                try:
                    page = start_page
                    while True:
                        data = await _request(
                            "GET", "/submissions", token,
                            {"step": step_id, "page": page, "page_size": 500}
                        )
                        subs = data.get("submissions", [])
                        meta = data.get("meta", {})
                        has_next = meta.get("has_next", False)

                        _sync_step = f"решения: курс {i + 1}/{num_courses}, шаг {si + 1}/{len(code_step_ids)} (стр. {page})"
                        _sync_progress = base + int((top - base) * min(page / 20, 1))

                        values = []
                        for s in subs:
                            sub_id = s.get("id")
                            if not sub_id:
                                continue
                            status = s.get("status", "")
                            sub_time = s.get("time")
                            if not status or not sub_time:
                                continue
                            if isinstance(sub_time, (int, float)):
                                submission_time = datetime.fromtimestamp(int(sub_time), tz=timezone.utc)
                            else:
                                submission_time = datetime.fromisoformat(
                                    str(sub_time).replace("Z", "+00:00")
                                )
                            reply = s.get("reply") or {}
                            values.append({
                                "stepik_submission_id": sub_id,
                                "stepik_step_id": step_id,
                                "course_id": course_map[stepik_course_id],
                                "status": status,
                                "score": s.get("score", 0.0) or 0.0,
                                "language": reply.get("language"),
                                "attempt_id": s.get("attempt"),
                                "eta": s.get("eta", 0) or 0,
                                "submission_time": submission_time,
                                "is_author": sub_id in author_sub_ids,
                            })

                        if values:
                            async with async_session() as session:
                                async with session.begin():
                                    await session.execute(
                                        text("""
                                            INSERT INTO submissions
                                                (stepik_submission_id, stepik_step_id, course_id, status, score, language, attempt_id, eta, submission_time, is_author)
                                            VALUES
                                                (:stepik_submission_id, :stepik_step_id, :course_id, :status, :score, :language, :attempt_id, :eta, :submission_time, :is_author)
                                            ON CONFLICT (stepik_submission_id) DO UPDATE SET
                                                status = EXCLUDED.status,
                                                score = EXCLUDED.score,
                                                language = EXCLUDED.language,
                                                attempt_id = EXCLUDED.attempt_id,
                                                eta = EXCLUDED.eta,
                                                is_author = EXCLUDED.is_author
                                        """), values
                                    )
                                course_upserted += len(values)

                        has_next = meta.get("has_next", False)
                        if not has_next:
                            async with async_session() as session:
                                async with session.begin():
                                    await session.execute(
                                        text("""
                                            INSERT INTO step_sync_state (step_id, last_page)
                                            VALUES (:step_id, :last_page)
                                            ON CONFLICT (step_id) DO UPDATE SET last_page = EXCLUDED.last_page
                                        """), {"step_id": step_id, "last_page": page}
                                    )
                            break
                        page += 1

                except Exception as e:
                    logger.warning("  submissions error step %d: %s", step_id, e)

                if (si + 1) % 20 == 0:
                    logger.info("  course %d: %d/%d code steps, %d submissions so far",
                                stepik_course_id, si + 1, len(code_step_ids), course_upserted)

            total_upserted += course_upserted
            logger.info("  course %d: %d submissions upserted", stepik_course_id, course_upserted)
            _sync_progress = 42 + int(43 * (i + 1) / num_courses)
        except Exception as e:
            logger.warning("  submissions error for course %d: %s", stepik_course_id, e)

    logger.info("Synced: %d submissions total", total_upserted)

    _sync_step = "решения: привязка пользователей (attempts)"
    _sync_progress = 85

    try:
        async with async_session() as session:
            result = await session.execute(
                text("SELECT DISTINCT attempt_id FROM submissions WHERE attempt_id IS NOT NULL AND user_id IS NULL")
            )
            attempt_ids = [row[0] for row in result.all()]
    except Exception as e:
        logger.warning("  error querying attempt_ids: %s", e)
        attempt_ids = []

    if attempt_ids:
        attempt_to_user = {}
        for batch_start in range(0, len(attempt_ids), 300):
            batch = attempt_ids[batch_start:batch_start + 300]
            try:
                attempts = await _paginated_get("/attempts", token, {"ids[]": batch}, "attempts")
                for a in attempts:
                    uid = a.get("user")
                    if uid:
                        attempt_to_user[a["id"]] = uid
            except Exception as e:
                logger.warning("  error fetching attempts batch: %s", e)

        if attempt_to_user:
            async with async_session() as session:
                async with session.begin():
                    for aid, uid in attempt_to_user.items():
                        await session.execute(
                            text("UPDATE submissions SET user_id = :uid WHERE attempt_id = :aid AND user_id IS NULL"),
                            {"uid": uid, "aid": aid},
                        )
            logger.info("  %d attempts → user_id applied", len(attempt_to_user))


async def sync_financials(user_id=None):
    """Sync financial data from Stepik API to FinancialSnapshot (fetch-then-replace)."""
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
        if user_id:
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        else:
            user = (await session.execute(select(User))).scalar_one_or_none()
        if not user:
            logger.warning("No user found, skipping financial sync")
            return
        courses = (
            await session.execute(select(Course).where(Course.user_id == user.id))
        ).scalars().all()
        course_map = {c.stepik_course_id: c.title for c in courses}

    # fetch course prices from Stepik API
    try:
        stepik_user_id = get_settings().stepik_user_id
        user_token = decrypt_token(user.access_token)
        courses_api = await _paginated_get("/courses", user_token, {"teacher": stepik_user_id}, "courses")
        course_price_map = {}
        for c in courses_api:
            cprice = c.get("price")
            if cprice is not None:
                course_price_map[c["id"]] = float(cprice)
    except Exception as e:
        logger.warning("Failed to fetch course prices: %s", e)
        course_price_map = {}

    total_turnover = sum(float(m.get("total_turnover", 0) or 0) for m in by_months)
    total_income = sum(float(m.get("total_user_income", 0) or 0) for m in by_months)
    total_refunds = sum(float(m.get("total_refunds", 0) or 0) for m in by_months)
    total_payments = sum(int(m.get("count_payments", 0) or 0) for m in by_months)
    total_refunds_count = sum(int(m.get("count_refunds", 0) or 0) for m in by_months)

    now = datetime.now(timezone.utc)
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
                "price": course_price_map.get(cid),
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

    promo_stats: dict[str, dict] = {}
    for b in benefits:
        code = b.get("promo_code") or None
        if code is None:
            continue
        if code not in promo_stats:
            promo_stats[code] = {
                "promo_code": code,
                "payments": 0, "turnover": 0, "income": 0, "refunds": 0,
                "last_used": b.get("time", ""),
            }
        ps = promo_stats[code]
        ps["payments"] += 1
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        if b.get("status") == "refunded":
            ps["refunds"] += amount
        else:
            ps["turnover"] += payment_amount
            ps["income"] += amount
        if b.get("time", "") > ps["last_used"]:
            ps["last_used"] = b.get("time", "")
    promos_list = sorted(promo_stats.values(), key=lambda x: x["last_used"], reverse=True)

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
            "total_refunds_count": total_refunds_count,
            "net_income": total_income - total_refunds,
            "current_month_turnover": current_month_turnover,
            "current_month_income": current_month_income,
            "current_month_payments": current_month_payments,
        },
        "months": months_data,
        "courses": course_list,
        "promos": promos_list,
        "recent_payments": recent_payments,
    }

    async with async_session() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM financial_snapshots"))
            snapshot = FinancialSnapshot(
                id=uuid.uuid4(),
                data=snapshot_data,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(snapshot)

    logger.info("Financial snapshot saved: %d months, %d courses, %d payments",
               len(months_data), len(course_list), len(recent_payments))


async def sync_community_stats(user_id=None):
    """Fetch reviews, ratings and comments from Stepik API, writing to DB after each page."""
    global _sync_progress, _sync_step

    async with async_session() as session:
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
        else:
            result = await session.execute(select(User))
        users = result.scalars().all()
        if not users:
            return
        user_db = users[0]
        token = decrypt_token(user_db.access_token)

    courses_data = await _paginated_get("/courses", token, {"teacher": get_settings().stepik_user_id}, "courses")
    course_ids_api = [c["id"] for c in courses_data]

    _sync_step = "рейтинги"
    _sync_progress = 96

    rating_sum = 0.0
    rating_count = 0
    reviews_count = 0
    per_course_ratings: dict[int, dict] = {}
    course_review_map = {}
    for c in courses_data:
        rid = c.get("review_summary")
        if rid:
            course_review_map[rid] = c["id"]

    review_ids = list(course_review_map.keys())
    if review_ids:
        try:
            ids_param = "&".join(f"ids[]={rid}" for rid in review_ids)
            linked_data = await _request("GET", f"/course-review-summaries?{ids_param}", token)
            summaries = linked_data.get("course-review-summaries", [])
            for rs in summaries:
                avg = rs.get("average")
                cnt = rs.get("count", 0)
                sid = course_review_map.get(rs.get("id"))
                if avg is not None and cnt > 0:
                    rating_sum += float(avg)
                    rating_count += 1
                    if sid:
                        per_course_ratings[sid] = {
                            "average_rating": float(avg),
                            "reviews_count": int(cnt or 0),
                        }
                reviews_count += int(cnt or 0)
        except Exception as e:
            logger.warning("Failed to fetch review summaries: %s", e)

    avg_rating = round(rating_sum / rating_count, 2) if rating_count > 0 else 0

    async with async_session() as session:
        result = await session.execute(select(FinancialSnapshot).limit(1))
        snapshot = result.scalar_one_or_none()
        if snapshot:
            prev = snapshot.data.get("community", {})
            snapshot.data = {**snapshot.data, "community": {
                **prev,
                "total_reviews": reviews_count,
                "average_rating": avg_rating,
            }}
            await session.commit()

    _sync_step = "комментарии"

    async with async_session() as session:
        result = await session.execute(select(FinancialSnapshot).limit(1))
        snapshot = result.scalar_one_or_none()
        prev_community = snapshot.data.get("community", {}) if snapshot else {}
        comments_total = prev_community.get("total_comments", 0)
        comments_monthly: dict[str, int] = dict(prev_community.get("comments_monthly", {}))
        last_comment_time = prev_community.get("last_comment_time", "")
        solutions_total = prev_community.get("total_solutions", 0)
        solutions_monthly: dict[str, int] = dict(prev_community.get("solutions_monthly", {}))
        last_solution_time = prev_community.get("last_solution_time", "")

    new_total = 0
    new_monthly: dict[str, int] = {}
    max_time = last_comment_time
    new_solutions = 0
    new_solutions_monthly: dict[str, int] = {}
    max_solution_time = last_solution_time

    per_course_comments: dict[int, int] = {}
    per_course_comments_monthly: dict[int, dict] = {}
    per_course_solutions: dict[int, int] = {}

    for cid in course_ids_api:
        page = 1
        pc_comments = 0
        pc_solutions = 0
        while True:
            data = await _request("GET", "/comments", token,
                                  {"course": cid, "page": page, "page_size": 20})
            items = data.get("comments", [])
            if not items:
                break

            for c in items:
                ts = c.get("time", "") or c.get("update_date", "")
                if ts and ts > last_comment_time:
                    new_total += 1
                    pc_comments += 1
                    if len(ts) >= 7:
                        key = f"{ts[:4]}-{ts[5:7]}"
                        new_monthly[key] = new_monthly.get(key, 0) + 1
                        pc_key = key
                        if cid not in per_course_comments_monthly:
                            per_course_comments_monthly[cid] = {}
                        per_course_comments_monthly[cid][pc_key] = per_course_comments_monthly[cid].get(pc_key, 0) + 1
                    if ts > max_time:
                        max_time = ts

                if c.get("thread") == "solutions":
                    if ts and ts > last_solution_time:
                        new_solutions += 1
                        pc_solutions += 1
                        if len(ts) >= 7:
                            key = f"{ts[:4]}-{ts[5:7]}"
                            new_solutions_monthly[key] = new_solutions_monthly.get(key, 0) + 1
                        if ts > max_solution_time:
                            max_solution_time = ts

            if not data.get("meta", {}).get("has_next", False):
                break
            page += 1

        if pc_comments > 0:
            per_course_comments[cid] = pc_comments
        if pc_solutions > 0:
            per_course_solutions[cid] = pc_solutions

    if new_total > 0:
        comments_total += new_total
        for k, v in new_monthly.items():
            comments_monthly[k] = comments_monthly.get(k, 0) + v
        last_comment_time = max_time

    if new_solutions > 0:
        solutions_total += new_solutions
        for k, v in new_solutions_monthly.items():
            solutions_monthly[k] = solutions_monthly.get(k, 0) + v
        last_solution_time = max_solution_time

    per_course_data: dict[int, dict] = {}
    for cid in course_ids_api:
        entry = {}
        if cid in per_course_comments:
            entry["comments"] = per_course_comments[cid]
        if cid in per_course_comments_monthly:
            entry["comments_monthly"] = per_course_comments_monthly[cid]
        if cid in per_course_solutions:
            entry["solutions"] = per_course_solutions[cid]
        if cid in per_course_ratings:
            entry.update(per_course_ratings[cid])
        if entry:
            per_course_data[str(cid)] = entry

    async with async_session() as session:
        result = await session.execute(select(FinancialSnapshot).limit(1))
        snapshot = result.scalar_one_or_none()
        if snapshot:
            prev = snapshot.data.get("community", {})
            snapshot.data = {**snapshot.data, "community": {
                **prev,
                "total_comments": comments_total,
                "comments_monthly": comments_monthly,
                "last_comment_time": last_comment_time,
                "total_solutions": solutions_total,
                "solutions_monthly": solutions_monthly,
                "last_solution_time": last_solution_time,
                "per_course": per_course_data,
            }}
            await session.commit()

    logger.info("Community stats: %d reviews, avg rating %.2f, %d comments",
                reviews_count, avg_rating, comments_total)


async def sync_all(force: bool = False, user_id=None):
    """Run all sync jobs. Skips if cooldown hasn't passed (unless force=True).

    If user_id is provided, sync only that user's data; otherwise sync all users.
    """
    global _sync_in_progress, _sync_progress, _sync_step, _last_sync_completed_at

    with _sync_lock:
        if _sync_in_progress:
            logger.info("Sync already in progress, skipping")
            return {"status": "skipped", "reason": "already_in_progress"}
        if not force and _last_sync_completed_at > 0:
            remaining = SYNC_COOLDOWN_SECONDS - (time.time() - _last_sync_completed_at)
            if remaining > 0:
                logger.info("Sync skipped, cooldown remaining: %ds", int(remaining))
                return {"status": "skipped", "reason": "cooldown", "remaining_seconds": int(remaining)}
        _sync_in_progress = True
        _sync_progress = 0
        _sync_step = "курсы"

    logger.info("=== Full sync started ===")
    try:
        _sync_step = "курсы и студенты"
        await sync_courses_and_enrollments(user_id)
        with _sync_lock:
            _sync_progress = 40
        _sync_step = "отправленные решения"
        await sync_submissions(user_id)
        with _sync_lock:
            _sync_progress = 85
        _sync_step = "финансы"
        await sync_financials(user_id)
        with _sync_lock:
            _sync_progress = 95
        _sync_step = "рейтинги"
        await sync_community_stats(user_id)
        with _sync_lock:
            _sync_progress = 100
        _sync_step = "готово"
        with _sync_lock:
            _last_sync_completed_at = time.time()
        logger.info("=== Full sync completed ===")
        return {"status": "ok"}
    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        return {"status": "error", "detail": str(e)}
    finally:
        with _sync_lock:
            _sync_in_progress = False
            _sync_progress = 0
            _sync_step = ""


def sync_all_sync(force: bool = False, user_id=None) -> dict:
    """Synchronous wrapper for sync_all, runs in its own event loop in a thread.
    Creates a separate DB engine to avoid "attached to a different loop" errors.
    Skips Redis rate limiter (sync thread uses its own loop, Redis client is bound to main loop).
    """
    global async_session

    from app.services import rate_limiter

    rate_limiter._sync_thread_local.skip_rate_limit = True

    engine = create_async_engine(get_settings().database_url, pool_size=5, max_overflow=2)
    thread_session = _sessionmaker(engine, expire_on_commit=False)

    old_session = async_session
    async_session = thread_session

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(sync_all(force=force, user_id=user_id))
    finally:
        async_session = old_session
        rate_limiter._sync_thread_local.skip_rate_limit = False
        engine.dispose()
        loop.close()
