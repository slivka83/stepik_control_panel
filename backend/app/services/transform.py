import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

def _ensure_json(val):
    """Handle _raw_json which is a dict (PG jsonb) or str (SQLite)."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, (str, bytes, bytearray)):
        return json.loads(val)
    return val


def _serialize_data(val, session):
    """Serialize to JSON string. PG asyncpg expects string for jsonb codec."""
    return json.dumps(val, ensure_ascii=False)


logger = logging.getLogger(__name__)


def parse_dt(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    s = str(raw).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def calculate_cohort_status(last_viewed_at, date_joined=None):
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


def get_course_status(is_public):
    return "Published" if is_public else "Draft"


async def transform_courses(session: AsyncSession, user_id: str | None = None):
    logger.info("=== Courses ===")
    r = await session.execute(text("""
        SELECT course_id, title, became_published_at, is_public
        FROM raw_course ORDER BY course_id
    """))
    raw_courses = [dict(r._mapping) for r in r]
    uid_param = str(user_id) if user_id else None
    if uid_param:
        r = await session.execute(
            text("SELECT id, stepik_course_id FROM courses WHERE user_id = :uid"),
            {"uid": uid_param},
        )
    else:
        r = await session.execute(text("SELECT id, stepik_course_id FROM courses"))
    existing = {row[1]: str(row[0]) for row in r}

    if uid_param:
        r = await session.execute(
            text("SELECT id FROM users WHERE id = :uid LIMIT 1"),
            {"uid": uid_param},
        )
    else:
        r = await session.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = r.fetchone()
    if not user_row:
        logger.warning("No user found")
        return
    user_id_db = str(user_row[0])

    seen_ids = set()
    upserted = 0
    for rc in raw_courses:
        sid = rc["course_id"]
        if sid is None:
            continue
        sid = int(sid)
        seen_ids.add(sid)
        is_pub_raw = rc.get("is_public")
        if is_pub_raw is not None:
            if isinstance(is_pub_raw, bool):
                is_pub = is_pub_raw
            elif isinstance(is_pub_raw, (int, float)):
                is_pub = bool(is_pub_raw)
            else:
                is_pub = str(is_pub_raw).lower() in ("true", "1")
        else:
            is_pub = None
        pub_dt = None
        if is_pub:
            pub_raw = rc.get("became_published_at")
            pub_dt = parse_dt(pub_raw) if pub_raw else None
        status = get_course_status(is_pub) if is_pub is not None else "Draft"
        title = (rc.get("title") or "Untitled")[:255]

        if sid in existing:
            await session.execute(
                text("""
                    UPDATE courses SET title = :t, status = :s, published_at = :p
                    WHERE stepik_course_id = :sid
                """),
                {"t": title, "s": status, "p": pub_dt, "sid": sid},
            )
        else:
            await session.execute(
                text("""
                    INSERT INTO courses (id, user_id, stepik_course_id, title, status, published_at, created_at)
                    VALUES (:id, :uid, :sid, :t, :s, :p, :now)
                """),
                {
                    "id": str(uuid.uuid4()), "uid": user_id_db, "sid": sid,
                    "t": title, "s": status, "p": pub_dt,
            "now": datetime.utcnow(),
                },
            )
        upserted += 1

    deleted = 0
    for sid, cid_str in existing.items():
        if sid not in seen_ids:
            await session.execute(
                text("DELETE FROM courses WHERE id = :cid"),
                {"cid": cid_str},
            )
            deleted += 1

    logger.info("  %d upserted, %d deleted", upserted, deleted)


async def build_step_course_map(session: AsyncSession) -> dict[int, int]:
    r = await session.execute(text("""
        SELECT DISTINCT s.step_id, sec.course
        FROM raw_step s
        JOIN raw_unit u ON u.lesson_id = s.lesson
        JOIN raw_section sec ON sec.section_id = u.section_id
        WHERE s.step_id IS NOT NULL AND sec.course IS NOT NULL
    """))
    return {int(r[0]): int(r[1]) for r in r}


async def transform_enrollments(session: AsyncSession):
    logger.info("=== Enrollments ===")

    r = await session.execute(text("SELECT id, stepik_course_id FROM courses"))
    course_map = {int(row[1]): str(row[0]) for row in r}

    if not course_map:
        logger.warning("  no courses, skipping")
        return

    for stepik_cid, course_uuid in course_map.items():
        r = await session.execute(
            text("""
                SELECT user_id AS student_id, score, last_viewed, date_joined
                FROM raw_course_grade
                WHERE course_id = :cid
            """),
            {"cid": str(stepik_cid)},
        )
        grade_rows = [dict(r._mapping) for r in r]

        r = await session.execute(
            text("""
                SELECT DISTINCT user_id FROM raw_certificate
                WHERE course_id = :cid AND user_id IS NOT NULL
            """),
            {"cid": str(stepik_cid)},
        )
        cert_users = {int(r[0]) for r in r}

        enrollments = []
        for g in grade_rows:
            student_id = g.get("student_id")
            if student_id is None:
                continue
            student_id = int(student_id)
            lv = parse_dt(g.get("last_viewed"))
            dj = parse_dt(g.get("date_joined"))
            score = int(float(g.get("score") or 0))
            enrollments.append({
                "id": str(uuid.uuid4()),
                "course_id": course_uuid,
                "student_id": student_id,
                "cohort_status": calculate_cohort_status(lv, dj),
                "points_earned": score,
                "certificate_issued": student_id in cert_users,
                "last_viewed_at": lv.replace(tzinfo=None) if lv else None,
                "date_joined": dj,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            })

        await session.execute(
            text("DELETE FROM student_enrollments WHERE course_id = :cid"),
            {"cid": course_uuid},
        )
        if enrollments:
            col_names = ["id", "course_id", "student_id", "cohort_status",
                         "points_earned", "certificate_issued",
                         "last_viewed_at", "date_joined", "created_at"]
            placeholders = ", ".join(f":{c}" for c in col_names)
            cols_str = ", ".join(f'"{c}"' for c in col_names)
            await session.execute(
                text(f'INSERT INTO student_enrollments ({cols_str}) VALUES ({placeholders})'),
                enrollments,
            )

        logger.info("  course %d: %d enrollments", stepik_cid, len(enrollments))


async def transform_submissions(session: AsyncSession):
    logger.info("=== Submissions ===")

    step_course = await build_step_course_map(session)
    if not step_course:
        logger.warning("  no step→course mapping, skipping")
        return

    r = await session.execute(text("SELECT id, stepik_course_id FROM courses"))
    app_course_map = {int(row[1]): str(row[0]) for row in r}

    r = await session.execute(text("""
        SELECT _raw_json FROM raw_submission
    """))
    submission_rows = sorted((_ensure_json(r[0]) for r in r), key=lambda x: int(x.get("id", 0)))

    r = await session.execute(text("""
        SELECT attempt_id, "user" FROM raw_attempt
        WHERE "user" IS NOT NULL
    """))
    attempt_user = {int(row[0]): int(row[1]) for row in r}

    author_uid = get_settings().stepik_user_id

    total = 0
    batch = []
    BATCH_SIZE = 500

    for sub in submission_rows:
        sid = sub.get("id")
        step_id = sub.get("step")
        if not sid or not step_id:
            continue
        step_cid = step_course.get(int(step_id))
        if step_cid not in app_course_map:
            continue
        course_uuid = app_course_map[step_cid]
        status = sub.get("status", "")
        sub_time_raw = sub.get("time")
        sub_time = parse_dt(sub_time_raw)
        if not sub_time:
            continue
        reply = sub.get("reply") or {}
        attempt_id = sub.get("attempt")
        uid = attempt_user.get(attempt_id) if attempt_id else None
        sub_user = sub.get("user")
        if sub_user and int(sub_user) == author_uid:
            is_author = True
        else:
            is_author = (uid == author_uid) if uid else False
        score = float(sub.get("score") or 0)
        eta_val = int(sub.get("eta") or 0)

        batch.append({
            "id": str(uuid.uuid4()),
            "ssid": int(sid),
            "step_id": int(step_id),
            "cid": course_uuid,
            "status": status,
            "score": score,
            "lang": reply.get("language"),
            "attempt": attempt_id,
            "uid": uid,
            "eta": eta_val,
            "stime": sub_time,
            "author": is_author,
            "now": datetime.now(timezone.utc).replace(tzinfo=None),
        })

        if len(batch) >= BATCH_SIZE:
            await session.execute(
                text("""
                    INSERT INTO submissions
                        (id, stepik_submission_id, stepik_step_id, course_id,
                         status, score, language, attempt_id, user_id, eta,
                         submission_time, is_author, created_at)
                    VALUES
                        (:id, :ssid, :step_id, :cid,
                         :status, :score, :lang, :attempt, :uid, :eta,
                         :stime, :author, :now)
                    ON CONFLICT (stepik_submission_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        score = EXCLUDED.score,
                        language = EXCLUDED.language,
                        attempt_id = EXCLUDED.attempt_id,
                        user_id = EXCLUDED.user_id,
                        eta = EXCLUDED.eta,
                        is_author = EXCLUDED.is_author
                """),
                batch,
            )
            total += len(batch)
            logger.info("  ... %d submissions upserted", total)
            batch = []

    if batch:
        await session.execute(
            text("""
                INSERT INTO submissions
                    (id, stepik_submission_id, stepik_step_id, course_id,
                     status, score, language, attempt_id, user_id, eta,
                     submission_time, is_author, created_at)
                VALUES
                    (:id, :ssid, :step_id, :cid,
                     :status, :score, :lang, :attempt, :uid, :eta,
                     :stime, :author, :now)
                ON CONFLICT (stepik_submission_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    score = EXCLUDED.score,
                    language = EXCLUDED.language,
                    attempt_id = EXCLUDED.attempt_id,
                    user_id = EXCLUDED.user_id,
                    eta = EXCLUDED.eta,
                    is_author = EXCLUDED.is_author
            """),
            batch,
        )
        total += len(batch)

    logger.info("  %d submissions upserted", total)


MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


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
                    try:
                        course_prices[cid] = float(price_val)
                    except (ValueError, TypeError):
                        pass

    r = await session.execute(text("""
        SELECT _raw_json FROM raw_course_benefit_by_month
    """))
    by_months = [_ensure_json(r[0]) for r in r]

    r = await session.execute(text("""
        SELECT _raw_json FROM raw_course_benefit
    """))
    benefits = [_ensure_json(r[0]) for r in r]

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

    course_stats = {}
    for b in benefits:
        cid = b.get("course")
        if cid not in course_stats:
            cm = course_map.get(cid, {})
            course_stats[cid] = {
                "course_id": cid,
                "title": cm.get("title", f"Курс #{cid}"),
                "price": course_prices.get(cid),
                "turnover": 0, "income": 0, "refunds": 0, "payments": 0,
            }
        status = b.get("status", "")
        amount = float(b.get("amount", 0) or 0)
        payment_amount = float(b.get("payment_amount", 0) or 0)
        cs = course_stats[cid]
        cs["payments"] += 1
        if status == "refunded":
            cs["refunds"] += amount
            cs["turnover"] -= payment_amount
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

    recent_payments = []
    for b in sorted(benefits, key=lambda x: x.get("time", ""), reverse=True)[:30]:
        recent_payments.append({
            "id": b.get("id"),
            "course": course_map.get(b.get("course"), {}).get("title", f"Курс #{b.get('course')}"),
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
        "courses": sorted(course_stats.values(), key=lambda x: x["turnover"], reverse=True),
        "promos": sorted(promo_stats.values(), key=lambda x: x["last_used"], reverse=True),
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
            "now": datetime.now(timezone.utc).replace(tzinfo=None),
        },
    )

    logger.info("  snapshot saved: %d months, %d courses, %d payments",
                len(months_data), len(course_stats), len(recent_payments))


async def transform_community(session: AsyncSession):
    logger.info("=== Community ===")

    r = await session.execute(text("SELECT id, stepik_course_id FROM courses"))
    course_map = {int(row[1]): str(row[0]) for row in r}

    if not course_map:
        logger.warning("  no courses, skipping")
        return

    r = await session.execute(text("""
        SELECT _raw_json FROM raw_course_review_summary
    """))
    reviews = [_ensure_json(r[0]) for r in r]

    average_rating = 0.0
    total_reviews = 0
    per_course_rating = {}
    per_course_reviews_count = {}
    if reviews:
        for rv in reviews:
            cid = rv.get("course") or rv.get("id")
            avg = rv.get("average")
            cnt = int(rv.get("count", 0) or 0)
            total_reviews += cnt
            if cid and avg:
                try:
                    avg_f = float(avg)
                    if avg_f > 0:
                        per_course_rating[str(cid)] = round(avg_f, 2)
                        per_course_reviews_count[str(cid)] = cnt
                except (ValueError, TypeError):
                    pass
        if per_course_rating:
            average_rating = round(sum(per_course_rating.values()) / len(per_course_rating), 2)

    r = await session.execute(text("""
        SELECT _raw_json FROM raw_comment
    """))
    comments = sorted((_ensure_json(r[0]) for r in r), key=lambda x: x.get("time") or "")

    total_comments = 0
    comments_monthly = {}
    total_solutions = 0
    solutions_monthly = {}
    per_course_comments = {}

    step_course = await build_step_course_map(session)

    for cm in comments:
        time_raw = cm.get("time")
        if not time_raw:
            continue
        try:
            dt = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        key = f"{dt.year}-{dt.month:02d}"
        thread = cm.get("thread", "")
        is_solution = "solution" in thread if thread else False

        total_comments += 1
        comments_monthly[key] = comments_monthly.get(key, 0) + 1

        if is_solution:
            total_solutions += 1
            solutions_monthly[key] = solutions_monthly.get(key, 0) + 1

        target = cm.get("target")
        if target and step_course:
            step_cid = step_course.get(int(target))
            if step_cid:
                cid_str = str(step_cid)
                per_course_comments[cid_str] = per_course_comments.get(cid_str, 0) + 1

    per_course = {}
    for cid, _ in course_map.items():
        cid_str = str(cid)
        per_course[cid_str] = {
            "comments": per_course_comments.get(cid_str, 0),
            "reviews_count": per_course_reviews_count.get(cid_str, 0),
            "average_rating": per_course_rating.get(cid_str, 0),
        }

    community = {
        "average_rating": average_rating,
        "total_reviews": total_reviews,
        "total_comments": total_comments,
        "comments_monthly": comments_monthly,
        "total_solutions": total_solutions,
        "solutions_monthly": solutions_monthly,
        "per_course": per_course,
    }

    r = await session.execute(text("SELECT id, data FROM financial_snapshots LIMIT 1"))
    row = r.fetchone()
    if row:
        snap_id = row[0]
        data = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        data["community"] = community
        await session.execute(
            text("UPDATE financial_snapshots SET data = :data, updated_at = :now WHERE id = :id"),
            {"data": _serialize_data(data, session),
             "now": datetime.now(timezone.utc).replace(tzinfo=None),
             "id": snap_id},
        )
    else:
        await session.execute(
            text("INSERT INTO financial_snapshots (id, data, updated_at) VALUES (:id, :data, :now)"),
            {"id": str(uuid.uuid4()),
             "data": _serialize_data({"community": community}, session),
             "now": datetime.now(timezone.utc).replace(tzinfo=None)},
        )

    logger.info("  rating=%.2f reviews=%d comments=%d solutions=%d",
                average_rating, total_reviews, total_comments, total_solutions)
