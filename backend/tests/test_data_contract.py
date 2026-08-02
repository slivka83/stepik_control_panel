"""Global data-contract tests.

Regression: the Courses page showed "—"/0 for Стоимость (price), Комментарии,
Отзывы и Рейтинг because the financial snapshot lacked `price` in course
entries and `community.per_course` entirely.

Instead of testing those four fields individually, these tests validate the
COMPLETE documented snapshot/API schema plus scan every field the frontend
reads, so no field — present or future — can silently disappear.
"""

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import User
from app.services.crypto import encrypt_token

ROOT = Path(__file__).resolve().parents[2]
PAGES_DIR = ROOT / "frontend" / "src" / "pages"

client = TestClient(app, raise_server_exceptions=False)

# ─── Documented snapshot schema (see AGENTS.md / docs/brd.md) ────────────

SNAPSHOT_TOP_KEYS = {"summary", "months", "courses", "recent_payments", "promos", "utms", "community"}

SUMMARY_KEYS = {
    "total_turnover",
    "total_income",
    "total_refunds",
    "total_payments",
    "total_refunds_count",
    "net_income",
    "current_month_turnover",
    "current_month_income",
    "current_month_payments",
}

COURSE_KEYS = {"course_id", "title", "price", "turnover", "income", "refunds", "payments"}

MONTH_KEYS = {"month", "year", "month_num", "turnover", "income", "refunds", "payments_count", "refunds_count"}

COMMUNITY_KEYS = {
    "average_rating",
    "total_reviews",
    "total_comments",
    "comments_monthly",
    "total_solutions",
    "solutions_monthly",
    "per_course",
}

PER_COURSE_KEYS = {"comments", "reviews_count", "average_rating"}

# Every field the Financials page reads from recent_payments (frontend/src/pages/Financials.jsx)
RECENT_PAYMENT_KEYS = {
    "id",
    "course",
    "amount",
    "payment_amount",
    "status",
    "time",
    "buyer",
    "student",
    "promo_code",
    "currency",
    "channel",
    "is_gift",
    "utm_source",
    "utm_source_label",
    "raw",
}

# Aggregated rows of the «По UTM» tab
UTM_STAT_KEYS = {"utm_source", "payments", "turnover", "income", "refunds", "last_used"}

# Every field the Courses page reads from /api/courses (frontend/src/pages/Courses.jsx)
COURSES_API_FIELDS = {
    "id",
    "stepik_course_id",
    "title",
    "status",
    "price",
    "income",
    "published_at",
    "enrollment_count",
    "submissions_total",
    "submissions_correct",
    "comments_count",
    "reviews_count",
    "average_rating",
}

# ─── Seed helpers ────────────────────────────────────────────────────────


async def _seed_user(session):
    user = User(
        id=uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_full_pipeline(session):
    """Seed raw tables with 2 courses (one without community data) and run all transforms."""
    now = datetime.now(UTC)
    user = await _seed_user(session)

    for cid, title, price in [(101, "Python 101", 2990), (102, "JS Basics", 1990)]:
        await session.execute(
            text("""
            INSERT INTO raw_course (course_id, title, became_published_at, begin_date, is_public, _raw_json)
            VALUES (:cid, :title, :bpa, NULL, 1, :raw)
        """),
            {
                "cid": cid,
                "title": title,
                "bpa": "2026-01-15T00:00:00Z",
                "raw": json.dumps(
                    {
                        "id": cid,
                        "course_id": cid,
                        "title": title,
                        "price": price,
                        "is_public": True,
                        "became_published_at": "2026-01-15T00:00:00Z",
                    }
                ),
            },
        )

    # step 500 → unit → section → course 101 (comment targets map to courses via steps)
    await session.execute(
        text("""
        INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES (500, 10, '{}')
    """)
    )
    await session.execute(
        text("""
        INSERT INTO raw_lesson (lesson_id, steps, _raw_json) VALUES (10, '[500]', '{}')
    """)
    )
    await session.execute(
        text("""
        INSERT INTO raw_unit (unit_id, lesson_id, section_id, _raw_json) VALUES (1, 10, 1, '{}')
    """)
    )
    await session.execute(
        text("""
        INSERT INTO raw_section (section_id, course, units, _raw_json) VALUES (1, 101, '[1]', '{}')
    """)
    )

    # enrollments for course 101
    now_iso = now.isoformat()
    await session.execute(
        text("""
        INSERT INTO raw_course_grade (user_id, course_id, score, last_viewed, date_joined, _raw_json)
        VALUES (1001, 101, 85, :lv, :dj, '{}'),
               (1002, 101, 60, :lv2, :dj2, '{}')
    """),
        {
            "lv": (now - timedelta(days=2)).isoformat(),
            "dj": (now - timedelta(days=30)).isoformat(),
            "lv2": (now - timedelta(days=10)).isoformat(),
            "dj2": (now - timedelta(days=40)).isoformat(),
        },
    )
    await session.execute(
        text("""
        INSERT INTO raw_certificate (user_id, course_id, _raw_json) VALUES (1001, 101, '{}')
    """)
    )

    # 2 submissions on step 500 by non-author students
    # Regression: API не возвращает "step" в объекте submission — шаг из колонки
    # raw_submission.step (пишется loader'ом из ?step=) либо из raw_attempt.step
    await session.execute(
        text("""
        INSERT INTO raw_submission (submission_id, step, _raw_json)
        VALUES (1000, 500, '{"id": 1000, "status": "correct", "time": "' || :t1 || '", "score": 1.0, "reply": {"language": "python"}, "attempt": 10}'),
               (1001, NULL, '{"id": 1001, "status": "wrong", "time": "' || :t2 || '", "score": 0.0, "reply": {}, "attempt": 11}')
    """),
        {
            "t1": (now - timedelta(days=1)).strftime("%Y-%m-%dT10:00:00Z"),
            "t2": (now - timedelta(days=2)).strftime("%Y-%m-%dT10:00:00Z"),
        },
    )
    await session.execute(
        text("""
        INSERT INTO raw_attempt (attempt_id, "user", step, _raw_json)
        VALUES (10, 67890, 500, '{}'), (11, 67891, 500, '{}')
    """)
    )

    # financials: current + previous month
    prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    await session.execute(
        text("""
        INSERT INTO raw_course_benefit_by_month (year, month, total_turnover, total_user_income, total_refunds, count_payments, count_refunds, _raw_json)
        VALUES (:y1, :m1, '10000', '8000', '200', 10, 1, :j1),
               (:y2, :m2, '5000', '4000', '100', 5, 0, :j2)
    """),
        {
            "y1": now.year,
            "m1": now.month,
            "j1": json.dumps(
                {
                    "year": now.year,
                    "month": now.month,
                    "total_turnover": 10000,
                    "total_user_income": 8000,
                    "total_refunds": 200,
                    "count_payments": 10,
                    "count_refunds": 1,
                }
            ),
            "y2": prev_year,
            "m2": prev_month,
            "j2": json.dumps(
                {
                    "year": prev_year,
                    "month": prev_month,
                    "total_turnover": 5000,
                    "total_user_income": 4000,
                    "total_refunds": 100,
                    "count_payments": 5,
                    "count_refunds": 0,
                }
            ),
        },
    )

    # benefits: 101 has completed + refunded, 102 only completed
    await session.execute(
        text("""
        INSERT INTO raw_course_benefit (course, amount, payment_amount, status, "time", buyer, promo_code, currency_code, _raw_json)
        VALUES (101, '1000', '1200', 'completed', :t1, 1001, NULL, 'RUB', :j1),
               (101, '-200', '1200', 'refunded', :t2, 1002, 'DISCOUNT10', 'RUB', :j2),
               (102, '1500', '1500', 'completed', :t3, 1003, NULL, 'RUB', :j3)
    """),
        {
            "t1": (now - timedelta(days=3)).strftime("%Y-%m-%dT10:00:00Z"),
            "t2": (now - timedelta(days=4)).strftime("%Y-%m-%dT10:00:00Z"),
            "t3": (now - timedelta(days=5)).strftime("%Y-%m-%dT10:00:00Z"),
            "j1": json.dumps(
                {
                    "course": 101,
                    "amount": 1000,
                    "payment_amount": 1200,
                    "status": "completed",
                    "time": (now - timedelta(days=3)).isoformat(),
                    "buyer": 1001,
                    "promo_code": None,
                    "currency_code": "RUB",
                    "last_course_click_utm": {
                        "utm_source": "yandex_stpk",
                        "utm_medium": "cpc",
                        "utm_campaign": "rsya_yad_feed_stepik_rus",
                    },
                }
            ),
            "j2": json.dumps(
                {
                    "course": 101,
                    "amount": -200,
                    "payment_amount": 1200,
                    "status": "refunded",
                    "time": (now - timedelta(days=4)).isoformat(),
                    "buyer": 1002,
                    "promo_code": "DISCOUNT10",
                    "currency_code": "RUB",
                }
            ),
            "j3": json.dumps(
                {
                    "course": 102,
                    "amount": 1500,
                    "payment_amount": 1500,
                    "status": "completed",
                    "time": (now - timedelta(days=5)).isoformat(),
                    "buyer": 1003,
                    "promo_code": None,
                    "currency_code": "RUB",
                }
            ),
        },
    )

    # reviews only for course 101; comments (1 solution) on step 500 → course 101
    await session.execute(
        text("""
        INSERT INTO raw_course_review_summary (average, count, _raw_json)
        VALUES ('4.5', 100, '{"course": 101, "average": 4.5, "count": 100}')
    """)
    )

    # user profile for buyer 1001 → student name in recent_payments
    await session.execute(
        text("""
        INSERT INTO raw_user (user_id, first_name, last_name, _raw_json)
        VALUES ('1001', 'Иван', 'Петров', '{"id": 1001, "first_name": "Иван", "last_name": "Петров"}')
    """)
    )
    await session.execute(
        text("""
        INSERT INTO raw_comment ("user", target, "time", thread, _raw_json)
        VALUES (1, 500, :t1, '', :j1),
               (2, 500, :t2, 'solutions', :j2)
    """),
        {
            "t1": (now - timedelta(days=6)).strftime("%Y-%m-%dT10:00:00Z"),
            "t2": (now - timedelta(days=7)).strftime("%Y-%m-%dT10:00:00Z"),
            "j1": json.dumps({"user": 1, "target": 500, "time": (now - timedelta(days=6)).isoformat(), "thread": ""}),
            "j2": json.dumps(
                {"user": 2, "target": 500, "time": (now - timedelta(days=7)).isoformat(), "thread": "solutions"}
            ),
        },
    )
    await session.commit()

    from app.config import get_settings
    from app.services.transform import (
        transform_community,
        transform_courses,
        transform_enrollments,
        transform_financials,
        transform_students,
        transform_submissions,
    )

    with patch.object(get_settings(), "stepik_user_id", 12345):
        await transform_courses(session)
        await transform_enrollments(session)
        await transform_submissions(session)
        await transform_financials(session)
        await transform_community(session)
        await transform_students(session)

    # SQLite: transforms write str(uuid4) WITH hyphens via raw SQL, but the ORM
    # binds UUIDs as CHAR(32) WITHOUT hyphens → API joins/counts would miss rows.
    # Normalize to the ORM's canonical form (PG stores native UUIDs, no issue there).
    await session.execute(
        text("""
        UPDATE courses SET id = replace(id, '-', ''),
                           user_id = replace(user_id, '-', '')
    """)
    )
    await session.execute(text("UPDATE student_enrollments SET course_id = replace(course_id, '-', '')"))
    await session.execute(text("UPDATE submissions SET course_id = replace(course_id, '-', '')"))
    await session.commit()
    return user


async def _get_snapshot(session) -> dict:
    r = await session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
    row = r.fetchone()
    assert row is not None, "no financial snapshot"
    data = row[0]
    return json.loads(data) if isinstance(data, str) else data


def _setup_api_overrides(session, user):
    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


# ─── Global schema tests (any missing field anywhere → fail) ─────────────


@pytest.mark.asyncio
async def test_snapshot_schema_is_complete(db_session):
    """Regression: snapshot must always contain the full documented schema."""
    await _seed_full_pipeline(db_session)
    data = await _get_snapshot(db_session)

    assert set(data) >= SNAPSHOT_TOP_KEYS, f"missing top-level keys: {SNAPSHOT_TOP_KEYS - set(data)}"
    assert set(data["summary"]) >= SUMMARY_KEYS, f"missing summary keys: {SUMMARY_KEYS - set(data['summary'])}"
    assert set(data["community"]) >= COMMUNITY_KEYS, (
        f"missing community keys: {COMMUNITY_KEYS - set(data['community'])}"
    )

    assert len(data["courses"]) == 2
    for c in data["courses"]:
        assert set(c) >= COURSE_KEYS, f"missing course keys: {COURSE_KEYS - set(c)}"
    for m in data["months"]:
        assert set(m) >= MONTH_KEYS, f"missing month keys: {MONTH_KEYS - set(m)}"
    for cid_str, pc in data["community"]["per_course"].items():
        assert set(pc) >= PER_COURSE_KEYS, f"per_course[{cid_str}] missing keys: {PER_COURSE_KEYS - set(pc)}"

    assert data["recent_payments"], "seed must produce recent payments"
    for p in data["recent_payments"]:
        assert set(p) >= RECENT_PAYMENT_KEYS, f"recent payment missing keys: {RECENT_PAYMENT_KEYS - set(p)}"
    assert len(data["utms"]) == 1, "seed must produce a utm aggregation row"
    for u in data["utms"]:
        assert set(u) >= UTM_STAT_KEYS, f"utm stat missing keys: {UTM_STAT_KEYS - set(u)}"
    assert data["utms"][0]["utm_source"] == "Я.Директ"
    assert data["recent_payments"][0]["student"] == "Иван Петров"


@pytest.mark.asyncio
async def test_every_course_has_price_and_per_course_entry(db_session):
    """Regression: no course may lack `price` or a `community.per_course` row."""
    await _seed_full_pipeline(db_session)
    data = await _get_snapshot(db_session)
    per_course = data["community"]["per_course"]

    by_id = {c["course_id"]: c for c in data["courses"]}
    assert set(by_id) == {101, 102}

    for cid, course in by_id.items():
        assert course["price"] is not None, f"course {cid} has no price"
        pc = per_course.get(str(cid))
        assert pc is not None, f"course {cid} has no community.per_course entry"
        assert set(pc) >= PER_COURSE_KEYS, f"course {cid} per_course incomplete: {pc}"

    # course 102 has no reviews/comments — must still get a zeros row
    assert per_course["102"] == {"comments": 0, "reviews_count": 0, "average_rating": 0}
    # course 101 has data
    assert per_course["101"]["comments"] == 2
    assert per_course["101"]["reviews_count"] == 100
    assert per_course["101"]["average_rating"] == 4.5

    assert by_id[101]["price"] == 2990
    assert by_id[102]["price"] == 1990


@pytest.mark.asyncio
async def test_rerun_pipeline_keeps_full_schema(db_session):
    """Regression: a repeated sync must not drop columns from the snapshot."""
    await _seed_full_pipeline(db_session)

    from app.services.transform import transform_community, transform_financials

    await transform_financials(db_session)
    await transform_community(db_session)
    await db_session.commit()

    data = await _get_snapshot(db_session)
    assert set(data) >= SNAPSHOT_TOP_KEYS
    assert set(data["summary"]) >= SUMMARY_KEYS
    assert set(data["community"]) >= COMMUNITY_KEYS
    for c in data["courses"]:
        assert set(c) >= COURSE_KEYS
        assert c["price"] is not None
        assert data["community"]["per_course"].get(str(c["course_id"])) is not None
    for p in data["recent_payments"]:
        assert set(p) >= RECENT_PAYMENT_KEYS, f"recent payment missing keys: {RECENT_PAYMENT_KEYS - set(p)}"
    for u in data["utms"]:
        assert set(u) >= UTM_STAT_KEYS, f"utm stat missing keys: {UTM_STAT_KEYS - set(u)}"


# ─── API contract tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_courses_api_returns_every_frontend_field(db_session):
    """Regression: /api/courses must return every field the Courses page reads."""
    user = await _seed_full_pipeline(db_session)
    _setup_api_overrides(db_session, user)
    try:
        response = client.get("/api/courses")
        assert response.status_code == 200
        courses = response.json()["courses"]
        assert len(courses) == 2
        for c in courses:
            assert set(c) >= COURSES_API_FIELDS, f"missing API fields: {COURSES_API_FIELDS - set(c)}"

        py = next(c for c in courses if c["title"] == "Python 101")
        assert py["price"] == 2990
        assert py["income"] == 1000
        assert py["comments_count"] == 2
        assert py["reviews_count"] == 100
        assert py["average_rating"] == 4.5
        assert py["enrollment_count"] == 2
        assert py["submissions_total"] == 2
        assert py["submissions_correct"] == 1

        js = next(c for c in courses if c["title"] == "JS Basics")
        assert js["price"] == 1990
        assert js["income"] == 1500
        assert js["comments_count"] == 0
        assert js["reviews_count"] == 0
        assert js["average_rating"] == 0
    finally:
        app.dependency_overrides.clear()


# ─── Global frontend field scan (all pages, all fields) ─────────────────

FIELD_RE = re.compile(r"\b(course|kpi|s|submissions|financials)\??\.([A-Za-z_][A-Za-z0-9_]*)")

# page file → {variable name → API payload key}
PAGE_VAR_TO_PAYLOAD = {
    "Courses.jsx": {"course": "courses", "kpi": "kpi"},
    "Dashboard.jsx": {"kpi": "kpi"},
    "Students.jsx": {"s": "students"},
    "Solutions.jsx": {"s": "steps", "submissions": "submissions"},
    "Financials.jsx": {"financials": "financials"},
}


@pytest.mark.asyncio
async def test_frontend_field_references_exist_in_api(db_session):
    """Global scan: every field the frontend reads must exist in the API payload."""
    user = await _seed_full_pipeline(db_session)
    _setup_api_overrides(db_session, user)
    try:
        courses = client.get("/api/courses").json()["courses"]
        kpi = client.get("/api/dashboard/kpi").json()
        students = client.get("/api/dashboard/students").json()["students"]
        steps = client.get("/api/dashboard/hardest-steps?min_submissions=1").json()["steps"]
        submissions = client.get("/api/dashboard/submissions").json()
        financials = client.get("/api/financials").json()
        assert courses, "seed must produce courses"
        assert students, "seed must produce students"
        assert steps, "seed must produce hardest steps"
        assert submissions["months"], "seed must produce submission months"

        payloads = {
            "courses": courses[0],
            "kpi": kpi,
            "students": students[0],
            "steps": steps[0],
            "submissions": submissions,
            "financials": financials,
        }

        missing = []
        for page in PAGES_DIR.glob("*.jsx"):
            if page.name not in PAGE_VAR_TO_PAYLOAD:
                continue
            src = page.read_text()
            for var, payload_key in PAGE_VAR_TO_PAYLOAD[page.name].items():
                for m in FIELD_RE.finditer(src):
                    if m.group(1) != var:
                        continue
                    field = m.group(2)
                    if field not in payloads[payload_key]:
                        missing.append(f"{page.name}: {var}.{field} not in /api payload {payload_key!r}")

        assert not missing, "frontend references fields missing from API:\n" + "\n".join(missing)
    finally:
        app.dependency_overrides.clear()
