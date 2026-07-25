import logging
import uuid
import time
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.config import get_settings
from app.database import async_session
from app.models import (
    Course, StudentEnrollment, Submission, FinancialSnapshot, User, StepSyncState,
)
from app.services.stepik_api import _request, get_finance_token
from app.services.crypto import decrypt_token

logger = logging.getLogger(__name__)

_sync_in_progress = False
_sync_progress: int = 0
_sync_step: str = ""
_last_sync_completed_at: float = 0
_community_cache: dict = {"reviews_count": 0, "average_rating": 0}

MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

SYNC_COOLDOWN_SECONDS = 60  # 1 minute


async def _paginated_get(path: str, token: str, params: dict | None = None, key: str | None = None) -> list:
    all_items = []
    page = 1
    while True:
        p = {**(params or {}), "page": page, "page_size": 500}
        data = await _request("GET", path, token, p)
        items_key = key or path.lstrip("/")
        items = data.get(items_key, [])
        all_items.extend(items)
        meta = data.get("meta", {})
        if not meta.get("has_next", False) or not items:
            break
        page += 1
    return all_items


async def _count_comments(course_ids: list[int], token: str) -> int:
    total = 0
    for cid in course_ids:
        page = 1
        while True:
            data = await _request("GET", "/comments", token,
                                  {"course": cid, "page": page, "page_size": 20})
            items = data.get("comments", [])
            total += len(items)
            logger.info("Comments course=%d page=%d got=%d total_so_far=%d", cid, page, len(items), total)
            if not data.get("meta", {}).get("has_next", False) or not items:
                break
            page += 1
    return total


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

    all_grades: dict[int, list] = {}
    all_certs: dict[int, set] = {}

    num_courses = len(courses_data)
    for ci, c in enumerate(courses_data):
        sid = c["id"]
        _sync_step = f"курсы: оценки {ci + 1}/{num_courses}"
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

        _sync_step = f"курсы: сертификаты {ci + 1}/{num_courses}"
        try:
            certs = await _paginated_get("/certificates", token, {"course": sid}, "certificates")
            all_certs[sid] = {cert["user"] for cert in certs}
        except Exception:
            all_certs[sid] = set()

        _sync_progress = 10 + int(30 * (ci + 1) / num_courses)

    now = datetime.now(timezone.utc)
    enrollments_to_insert = []

    for sid, grades in all_grades.items():
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
                "stepik_course_id": sid,
                "student_id": student_id,
                "cohort_status": calculate_cohort_status(last_viewed, date_joined),
                "points_earned": int(score),
                "certificate_issued": is_passed,
                "last_viewed_at": last_viewed,
                "date_joined": date_joined,
            })

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
                    status="Published" if c.get("is_public", False) else "Draft",
                    health_score=100.0,
                )
                session.add(course)
                await session.flush()
                course_map[c["id"]] = course

            total_enrollments = 0
            for e in enrollments_to_insert:
                local_course = course_map.get(e["stepik_course_id"])
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

            logger.info("Synced: %d courses, %d enrollments",
                       len(courses_data), total_enrollments)

    rating_sum = 0.0
    rating_count = 0
    reviews_count = 0

    review_ids = [c.get("review_summary") for c in courses_data if c.get("review_summary")]
    if review_ids:
        try:
            ids_param = "&".join(f"ids[]={rid}" for rid in review_ids)
            linked_data = await _request("GET", f"/course-review-summaries?{ids_param}", token)
            summaries = linked_data.get("course-review-summaries", [])
            logger.info("Got %d review summaries from Stepik", len(summaries))
            for rs in summaries:
                avg = rs.get("average")
                cnt = rs.get("count", 0)
                logger.info("Review summary ID %s: average=%s count=%s", rs.get("id"), avg, cnt)
                if avg is not None and cnt > 0:
                    rating_sum += float(avg)
                    rating_count += 1
                reviews_count += int(cnt or 0)
        except Exception as e:
            logger.warning("Failed to fetch review summaries: %s", e)

    logger.info("Found review_summary on %d/%d courses, total reviews: %d",
                rating_count, len(courses_data), reviews_count)

    course_ids = [c["id"] for c in courses_data]
    comments_count = 0
    try:
        comments_count = await _count_comments(course_ids, token)
    except Exception as e:
        logger.warning("Failed to count comments: %s", e)
    logger.info("Total comments across %d courses: %d", len(course_ids), comments_count)

    global _community_cache
    _community_cache = {
        "reviews_count": reviews_count,
        "average_rating": round(rating_sum / rating_count, 2) if rating_count > 0 else 0,
        "comments_count": comments_count,
    }


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
            for batch_start in range(0, len(unit_ids), 50):
                batch = unit_ids[batch_start:batch_start + 50]
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
            for batch_start in range(0, len(all_step_ids), 50):
                batch = all_step_ids[batch_start:batch_start + 50]
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
                            })

                        if values:
                            async with async_session() as session:
                                async with session.begin():
                                    await session.execute(
                                        text("""
                                            INSERT INTO submissions
                                                (stepik_submission_id, stepik_step_id, course_id, status, score, language, attempt_id, eta, submission_time)
                                            VALUES
                                                (:stepik_submission_id, :stepik_step_id, :course_id, :status, :score, :language, :attempt_id, :eta, :submission_time)
                                            ON CONFLICT (stepik_submission_id) DO UPDATE SET
                                                status = EXCLUDED.status,
                                                score = EXCLUDED.score,
                                                language = EXCLUDED.language,
                                                attempt_id = EXCLUDED.attempt_id,
                                                eta = EXCLUDED.eta
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
            courses = (await session.execute(select(Course).where(Course.user_id == user_id))).scalars().all()
        else:
            courses = (await session.execute(select(Course))).scalars().all()
        course_map = {c.stepik_course_id: c.title for c in courses}

    total_turnover = sum(float(m.get("total_turnover", 0) or 0) for m in by_months)
    total_income = sum(float(m.get("total_user_income", 0) or 0) for m in by_months)
    total_refunds = sum(float(m.get("total_refunds", 0) or 0) for m in by_months)
    total_payments = sum(int(m.get("count_payments", 0) or 0) for m in by_months)
    total_refunds_count = sum(int(m.get("count_refunds", 0) or 0) for m in by_months)

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
            "total_refunds_count": total_refunds_count,
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
                updated_at=datetime.now(timezone.utc),
            )
            session.add(snapshot)

    logger.info("Financial snapshot saved: %d months, %d courses, %d payments",
               len(months_data), len(course_list), len(recent_payments))


async def sync_community_stats(user_id=None):
    """Write cached review/rating data to FinancialSnapshot.

    Reviews and ratings are extracted from courses data in sync_courses_and_enrollments.
    No extra API calls needed - data comes from DB.
    """
    global _community_cache

    async with async_session() as session:
        result = await session.execute(select(FinancialSnapshot).limit(1))
        snapshot = result.scalar_one_or_none()
        if snapshot:
            snapshot.data = {
                **snapshot.data,
                "community": {
                    "total_comments": _community_cache.get("comments_count", 0),
                    "total_reviews": _community_cache.get("reviews_count", 0),
                    "average_rating": _community_cache.get("average_rating", 0),
                },
            }
            await session.commit()

    logger.info("Community stats: %d reviews, avg rating %.2f, %d comments",
                _community_cache.get("reviews_count", 0),
                _community_cache.get("average_rating", 0),
                _community_cache.get("comments_count", 0))


async def sync_all(force: bool = False, user_id=None):
    """Run all sync jobs. Skips if cooldown hasn't passed (unless force=True).

    If user_id is provided, sync only that user's data; otherwise sync all users.
    """
    global _sync_in_progress, _sync_progress, _sync_step, _last_sync_completed_at

    if _sync_in_progress:
        logger.info("Sync already in progress, skipping")
        return {"status": "skipped", "reason": "already_in_progress"}

    if not force and not can_sync():
        remaining = int(SYNC_COOLDOWN_SECONDS - (time.time() - _last_sync_completed_at))
        logger.info("Sync skipped, cooldown remaining: %ds", remaining)
        return {"status": "skipped", "reason": "cooldown", "remaining_seconds": remaining}

    _sync_in_progress = True
    _sync_progress = 0
    _sync_step = "курсы"
    logger.info("=== Full sync started ===")
    try:
        _sync_step = "курсы и студенты"
        await sync_courses_and_enrollments(user_id)
        _sync_progress = 40
        _sync_step = "отправленные решения"
        await sync_submissions(user_id)
        _sync_progress = 85
        _sync_step = "финансы"
        await sync_financials(user_id)
        _sync_progress = 95
        _sync_step = "рейтинги"
        await sync_community_stats(user_id)
        _sync_progress = 100
        _sync_step = "готово"
        _last_sync_completed_at = time.time()
        logger.info("=== Full sync completed ===")
        return {"status": "ok"}
    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        return {"status": "error", "detail": str(e)}
    finally:
        _sync_in_progress = False
        _sync_progress = 0
        _sync_step = ""
        _sync_progress = 0
