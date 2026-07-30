"""Tests for transform service: raw → app table transformation."""
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import text

from app.models import User
from app.services.crypto import encrypt_token


def _make_user(session, stepik_id=12345):
    user = User(
        id=uuid.uuid4(), stepik_id=stepik_id,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(user)
    return user


async def _make_course(session, user_id, stepik_course_id=100, title="Test"):
    cid = str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO courses (id, user_id, stepik_course_id, title, status, created_at)
        VALUES (:id, :uid, :sid, :t, :s, :now)
    """), {
        "id": cid, "uid": str(user_id), "sid": stepik_course_id,
        "t": title, "s": "Published", "now": datetime.now(timezone.utc),
    })
    return cid


# ─── transform_courses ──────────────────────────────────────────────────

class TestTransformCourses:
    async def _populate_raw_courses(self, session, rows: list[dict]):
        for r in rows:
            await session.execute(text("""
                INSERT INTO raw_course (course_id, title, became_published_at, begin_date, is_public, _raw_json)
                VALUES (:cid, :title, :bpa, :bd, :is_public, :raw_json)
            """), {
                "cid": r.get("course_id"), "title": r.get("title"),
                "bpa": r.get("became_published_at"), "bd": r.get("begin_date"),
                "is_public": r.get("is_public"),
                "raw_json": json.dumps(r),
            })

    @pytest.mark.asyncio
    async def test_inserts_new_courses(self, db_session):
        from app.services.transform import transform_courses
        user = _make_user(db_session)
        await db_session.commit()

        await self._populate_raw_courses(db_session, [
            {"course_id": 101, "title": "New Course", "is_public": 1,
             "became_published_at": "2026-01-15T00:00:00Z", "begin_date": None},
        ])
        await db_session.commit()

        await transform_courses(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT stepik_course_id, title, status FROM courses"))
        rows = list(r)
        assert len(rows) == 1
        assert rows[0][0] == 101
        assert rows[0][1] == "New Course"
        assert rows[0][2] == "Published"

    @pytest.mark.asyncio
    async def test_updates_existing_courses(self, db_session):
        from app.services.transform import transform_courses
        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101, title="Old Title")
        await db_session.commit()

        await self._populate_raw_courses(db_session, [
            {"course_id": 101, "title": "Updated Title", "is_public": 0,
             "became_published_at": "2026-06-01T00:00:00Z", "begin_date": None},
        ])
        await db_session.commit()

        await transform_courses(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT stepik_course_id, title, status FROM courses"))
        rows = list(r)
        assert len(rows) == 1
        assert rows[0][1] == "Updated Title"
        assert rows[0][2] == "Draft"

    @pytest.mark.asyncio
    async def test_removes_deleted_courses(self, db_session):
        from app.services.transform import transform_courses
        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=999, title="To Delete")
        await db_session.commit()

        await self._populate_raw_courses(db_session, [])
        await db_session.commit()

        await transform_courses(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT id FROM courses"))
        assert len(list(r)) == 0


# ─── transform_enrollments ─────────────────────────────────────────────

class TestTransformEnrollments:
    @pytest.mark.asyncio
    async def test_creates_enrollments_from_grades(self, db_session):
        from app.services.transform import transform_enrollments
        user = _make_user(db_session)
        course = await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.commit()

        now_iso = datetime.now(timezone.utc)
        await db_session.execute(text("""
            INSERT INTO raw_course_grade ("user", course, score, last_viewed, first_viewed, _raw_json)
            VALUES (1001, 101, 85, :lv, :fj, '{}'),
                   (1002, 101, 0, NULL, :fj2, '{}')
        """), {
            "lv": (now_iso - timedelta(days=2)).isoformat(),
            "fj": (now_iso - timedelta(days=30)).isoformat(),
            "fj2": (now_iso - timedelta(days=100)).isoformat(),
        })
        await db_session.execute(text("""
            INSERT INTO raw_certificate (user_id, course, _raw_json)
            VALUES (1001, 101, '{}')
        """))
        await db_session.commit()

        await transform_enrollments(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT student_id, cohort_status, points_earned, certificate_issued, last_viewed_at FROM student_enrollments"))
        enrollments = list(r)
        assert len(enrollments) == 2

        e1 = next(e for e in enrollments if e[0] == 1001)
        assert e1[1] == "Active"
        assert e1[2] == 85
        assert e1[3] == 1
        assert e1[4] is not None

        e2 = next(e for e in enrollments if e[0] == 1002)
        assert e2[1] == "Sleeping"
        assert e2[2] == 0
        assert e2[3] == 0
        assert e2[4] is None

    @pytest.mark.asyncio
    async def test_replaces_enrollments_per_course(self, db_session):
        from app.services.transform import transform_enrollments
        user = _make_user(db_session)
        course_uuid = await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.commit()

        await db_session.execute(text(
            "INSERT INTO student_enrollments (id, course_id, student_id, cohort_status, points_earned, certificate_issued, created_at) VALUES (:id, :cid, :sid, :cs, :pe, 0, :now)"
        ), {"id": str(uuid.uuid4()), "cid": course_uuid, "sid": 999, "cs": "Active", "pe": 50, "now": datetime.now(timezone.utc)})
        await db_session.commit()

        now_iso = datetime.now(timezone.utc)
        await db_session.execute(text(
            "INSERT INTO raw_course_grade (\"user\", course, score, last_viewed, _raw_json) VALUES (:u, :c, :s, :lv, '{}')"
        ), {"u": 2001, "c": 101, "s": 90, "lv": (now_iso - timedelta(days=1)).isoformat()})
        await db_session.commit()

        await transform_enrollments(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT student_id FROM student_enrollments"))
        enrollments = list(r)
        assert len(enrollments) == 1
        assert enrollments[0][0] == 2001


# ─── transform_submissions ─────────────────────────────────────────────

class TestTransformSubmissions:
    @pytest.mark.asyncio
    async def test_upserts_submissions(self, db_session):
        from app.services.transform import transform_submissions
        from app.config import get_settings
        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.commit()

        # Mock stepik_user_id so is_author detection works
        with patch.object(get_settings(), "stepik_user_id", 12345):
            # Set up step→course mapping via raw entities
            await db_session.execute(text("""
                INSERT INTO raw_step (step_id, lesson, _raw_json)
                VALUES (500, 10, '{}')
            """))
            await db_session.execute(text("""
                INSERT INTO raw_unit (unit_id, lesson_id, section, _raw_json)
                VALUES (1, 10, 1, '{}')
            """))
            await db_session.execute(text("""
                INSERT INTO raw_section (section_id, course, units, _raw_json)
                VALUES (1, 101, '[1]', '{}')
            """))
            await db_session.execute(text("""
                INSERT INTO raw_submission (_raw_json)
                VALUES ('{"id": 1000, "step": 500, "status": "correct", "time": "2026-07-15T10:00:00Z", "score": 1.0, "reply": {"language": "python"}, "attempt": 10}'),
                       ('{"id": 1001, "step": 500, "status": "wrong", "time": "2026-07-16T10:00:00Z", "score": 0.0, "reply": {}, "attempt": 11}')
            """))
            await db_session.execute(text("""
                INSERT INTO raw_attempt (attempt_id, user_id, _raw_json)
                VALUES (10, 12345, '{}'),
                       (11, 67890, '{}')
            """))
            await db_session.commit()

            await transform_submissions(db_session)
            await db_session.commit()

        r = await db_session.execute(text("SELECT stepik_submission_id, status, language, is_author, stepik_step_id FROM submissions"))
        submissions = list(r)
        assert len(submissions) == 2
        s1 = next(s for s in submissions if s[0] == 1000)
        assert s1[1] == "correct"
        assert s1[2] == "python"
        assert s1[3] == 1  # True
        assert s1[4] == 500

        s2 = next(s for s in submissions if s[0] == 1001)
        assert s2[1] == "wrong"
        assert s2[3] == 0  # False


# ─── transform_financials ──────────────────────────────────────────────

class TestTransformFinancials:
    @pytest.mark.asyncio
    async def test_creates_snapshot(self, db_session):
        from app.services.transform import transform_financials
        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101, title="Python 101")
        await db_session.commit()

        now = datetime.now(timezone.utc)
        await db_session.execute(text("""
            INSERT INTO raw_course_benefit_by_month (year, month, total_turnover, total_user_income, total_refunds, count_payments, count_refunds, _raw_json)
            VALUES (:y1, :m1, '10000', '8000', '200', 10, 1, :j1),
                   (2025, 12, '5000', '4000', '100', 5, 0, :j2)
        """), {
            "y1": now.year, "m1": now.month,
            "j1": json.dumps({"year": now.year, "month": now.month, "total_turnover": 10000, "total_user_income": 8000, "total_refunds": 200, "count_payments": 10, "count_refunds": 1}),
            "j2": json.dumps({"year": 2025, "month": 12, "total_turnover": 5000, "total_user_income": 4000, "total_refunds": 100, "count_payments": 5, "count_refunds": 0}),
        })
        await db_session.execute(text("""
            INSERT INTO raw_course_benefit (course, amount, payment_amount, status, "time", buyer, promo_code, currency_code, _raw_json)
            VALUES (101, '1000', '1200', 'completed', '2026-07-01T10:00:00Z', 1001, NULL, 'RUB', :j1),
                   (101, '-200', '1200', 'refunded', '2026-07-05T10:00:00Z', 1002, 'DISCOUNT10', 'RUB', :j2)
        """), {
            "j1": json.dumps({"course": 101, "amount": 1000, "payment_amount": 1200, "status": "completed", "time": "2026-07-01T10:00:00Z", "buyer": 1001, "promo_code": None, "currency_code": "RUB"}),
            "j2": json.dumps({"course": 101, "amount": -200, "payment_amount": 1200, "status": "refunded", "time": "2026-07-05T10:00:00Z", "buyer": 1002, "promo_code": "DISCOUNT10", "currency_code": "RUB"}),
        })
        await db_session.commit()

        await transform_financials(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        row = r.fetchone()
        assert row is not None

        data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        s = data["summary"]
        assert s["total_turnover"] == 15000
        assert s["total_income"] == 12000
        assert s["total_refunds"] == 300
        assert s["total_payments"] == 15
        assert s["net_income"] == 11700

        assert len(data["months"]) == 2
        assert len(data["courses"]) == 1
        assert data["courses"][0]["title"] == "Python 101"

        assert len(data["promos"]) == 1
        assert data["promos"][0]["promo_code"] == "DISCOUNT10"

        assert len(data["recent_payments"]) == 2

    @pytest.mark.asyncio
    async def test_empty_financials(self, db_session):
        from app.services.transform import transform_financials
        _make_user(db_session)
        await db_session.commit()

        await transform_financials(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        row = r.fetchone()
        assert row is not None
        data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert data["summary"]["total_turnover"] == 0
        assert data["courses"] == []
        assert data["months"] == []


# ─── transform_community ───────────────────────────────────────────────

class TestTransformCommunity:
    @pytest.mark.asyncio
    async def test_community_data_added_to_snapshot(self, db_session):
        from app.services.transform import transform_community
        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.execute(text("""
            INSERT INTO financial_snapshots (id, data, updated_at)
            VALUES (:id, :data, :now)
        """), {"id": str(uuid.uuid4()), "data": json.dumps({"summary": {"total_turnover": 5000}, "months": [], "courses": [], "recent_payments": []}), "now": datetime.now(timezone.utc)})
        await db_session.commit()

        await db_session.execute(text("""
            INSERT INTO raw_course_review_summary (average, count, _raw_json)
            VALUES ('4.5', 100, '{"average": 4.5, "count": 100}')
        """))
        await db_session.execute(text("""
            INSERT INTO raw_comment ("user", target, "time", thread, _raw_json)
            VALUES (1, 101, '2026-07-10T10:00:00Z', '', :j1),
                   (2, 101, '2026-07-11T10:00:00Z', 'solutions', :j2)
        """), {
            "j1": json.dumps({"user": 1, "target": 101, "time": "2026-07-10T10:00:00Z", "thread": ""}),
            "j2": json.dumps({"user": 2, "target": 101, "time": "2026-07-11T10:00:00Z", "thread": "solutions"}),
        })
        await db_session.commit()

        await transform_community(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        row = r.fetchone()
        assert row is not None
        data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        community = data.get("community", {})
        assert community["total_reviews"] == 100
        assert community["average_rating"] == 4.5
        assert community["total_comments"] == 2
        assert community["comments_monthly"]["2026-07"] == 2
        assert community["total_solutions"] == 1
        assert community["solutions_monthly"]["2026-07"] == 1

        # Original data preserved
        assert data["summary"]["total_turnover"] == 5000

    @pytest.mark.asyncio
    async def test_no_existing_snapshot_creates_new(self, db_session):
        from app.services.transform import transform_community
        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.commit()
        await db_session.execute(text("DELETE FROM financial_snapshots"))
        await db_session.commit()

        await transform_community(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        row = r.fetchone()
        assert row is not None
        data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert data["community"]["total_comments"] == 0
