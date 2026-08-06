"""Tests for transform service: raw → app table transformation."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.models import User
from app.services.crypto import encrypt_token


def _make_user(session, stepik_id=12345):
    user = User(
        id=uuid.uuid4(),
        stepik_id=stepik_id,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(user)
    return user


async def _make_course(session, user_id, stepik_course_id=100, title="Test"):
    cid = str(uuid.uuid4())
    await session.execute(
        text("""
        INSERT INTO courses (id, user_id, stepik_course_id, title, status, created_at)
        VALUES (:id, :uid, :sid, :t, :s, :now)
    """),
        {
            "id": cid,
            "uid": str(user_id),
            "sid": stepik_course_id,
            "t": title,
            "s": "Published",
            "now": datetime.now(UTC),
        },
    )
    return cid


# ─── transform_courses ──────────────────────────────────────────────────


class TestTransformCourses:
    async def _populate_raw_courses(self, session, rows: list[dict]):
        for r in rows:
            await session.execute(
                text("""
                INSERT INTO raw_course (course_id, title, became_published_at, begin_date, is_public, _raw_json)
                VALUES (:cid, :title, :bpa, :bd, :is_public, :raw_json)
            """),
                {
                    "cid": r.get("course_id"),
                    "title": r.get("title"),
                    "bpa": r.get("became_published_at"),
                    "bd": r.get("begin_date"),
                    "is_public": r.get("is_public"),
                    "raw_json": json.dumps(r),
                },
            )

    @pytest.mark.asyncio
    async def test_inserts_new_courses(self, db_session):
        from app.services.transform import transform_courses

        user = _make_user(db_session)
        await db_session.commit()

        await self._populate_raw_courses(
            db_session,
            [
                {
                    "course_id": 101,
                    "title": "New Course",
                    "is_public": 1,
                    "became_published_at": "2026-01-15T00:00:00Z",
                    "begin_date": None,
                },
            ],
        )
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

        await self._populate_raw_courses(
            db_session,
            [
                {
                    "course_id": 101,
                    "title": "Updated Title",
                    "is_public": 0,
                    "became_published_at": "2026-06-01T00:00:00Z",
                    "begin_date": None,
                },
            ],
        )
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

        now_iso = datetime.now(UTC)
        await db_session.execute(
            text("""
            INSERT INTO raw_course_grade (user_id, course_id, score, last_viewed, date_joined, _raw_json)
            VALUES (1001, 101, 85, :lv, :fj, '{}'),
                   (1002, 101, 0, NULL, :fj2, '{}')
        """),
            {
                "lv": (now_iso - timedelta(days=2)).isoformat(),
                "fj": (now_iso - timedelta(days=30)).isoformat(),
                "fj2": (now_iso - timedelta(days=100)).isoformat(),
            },
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_certificate (user_id, course_id, _raw_json)
            VALUES (1001, 101, '{}')
        """)
        )
        await db_session.commit()

        await transform_enrollments(db_session)
        await db_session.commit()

        r = await db_session.execute(
            text(
                "SELECT student_id, cohort_status, points_earned, certificate_issued, last_viewed_at FROM student_enrollments"
            )
        )
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

        await db_session.execute(
            text(
                "INSERT INTO student_enrollments (id, course_id, student_id, cohort_status, points_earned, certificate_issued, created_at) VALUES (:id, :cid, :sid, :cs, :pe, 0, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "cid": course_uuid,
                "sid": 999,
                "cs": "Active",
                "pe": 50,
                "now": datetime.now(UTC),
            },
        )
        await db_session.commit()

        now_iso = datetime.now(UTC)
        await db_session.execute(
            text(
                "INSERT INTO raw_course_grade (user_id, course_id, score, last_viewed, _raw_json) VALUES (:u, :c, :s, :lv, '{}')"
            ),
            {"u": 2001, "c": 101, "s": 90, "lv": (now_iso - timedelta(days=1)).isoformat()},
        )
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
        """Regression: API не возвращает step в объекте submission — шаг
        определяется через attempt (raw_attempt.step) либо из инжектированного
        при загрузке поля step."""
        from app.config import get_settings
        from app.services.transform import transform_submissions

        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.commit()

        # Mock stepik_user_id so is_author detection works
        with patch.object(get_settings(), "stepik_user_id", 12345):
            # Set up step→course mapping via raw entities
            await db_session.execute(
                text("""
                INSERT INTO raw_step (step_id, lesson, _raw_json)
                VALUES (500, 10, '{}')
            """)
            )
            await db_session.execute(
                text("""
                INSERT INTO raw_unit (unit_id, lesson_id, section_id, _raw_json)
                VALUES (1, 10, 1, '{}')
            """)
            )
            await db_session.execute(
                text("""
                INSERT INTO raw_section (section_id, course, units, _raw_json)
                VALUES (1, 101, '[1]', '{}')
            """)
            )
            # no "step" in submission raw (как в реальном API), шаг из attempts
            await db_session.execute(
                text("""
                INSERT INTO raw_submission (submission_id, step, _raw_json)
                VALUES (1000, 500, '{"id": 1000, "status": "correct", "time": "2026-07-15T10:00:00Z", "score": 1.0, "reply": {"language": "python"}, "attempt": 10}'),
                       (1001, NULL, '{"id": 1001, "status": "wrong", "time": "2026-07-16T10:00:00Z", "score": 0.0, "reply": {}, "attempt": 11}'),
                       (1002, 500, '{"id": 1002, "status": "correct", "time": "2026-07-17T10:00:00Z", "score": 1.0, "reply": {}, "attempt": 12}')
            """)
            )
            await db_session.execute(
                text("""
                INSERT INTO raw_attempt (attempt_id, "user", step, _raw_json)
                VALUES (10, 12345, 500, '{}'),
                       (11, 67890, 500, '{}')
            """)
            )
            await db_session.commit()

            await transform_submissions(db_session)
            await db_session.commit()

        r = await db_session.execute(
            text("SELECT stepik_submission_id, status, language, is_author, stepik_step_id FROM submissions")
        )
        submissions = list(r)
        assert len(submissions) == 3
        s1 = next(s for s in submissions if s[0] == 1000)
        assert s1[1] == "correct"
        assert s1[2] == "python"
        assert s1[3] == 1  # True
        assert s1[4] == 500

        s2 = next(s for s in submissions if s[0] == 1001)
        assert s2[1] == "wrong"
        assert s2[3] == 0  # False
        assert s2[4] == 500

        s3 = next(s for s in submissions if s[0] == 1002)
        assert s3[4] == 500


# ─── transform_financials ──────────────────────────────────────────────


class TestTransformFinancials:
    @pytest.mark.asyncio
    async def test_creates_snapshot(self, db_session):
        from app.services.transform import transform_financials

        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101, title="Python 101")
        await db_session.commit()

        now = datetime.now(UTC)
        await db_session.execute(
            text("""
            INSERT INTO raw_course_benefit_by_month (year, month, total_turnover, total_user_income, total_refunds, count_payments, count_refunds, _raw_json)
            VALUES (:y1, :m1, '10000', '8000', '200', 10, 1, :j1),
                   (2025, 12, '5000', '4000', '100', 5, 0, :j2)
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
                "j2": json.dumps(
                    {
                        "year": 2025,
                        "month": 12,
                        "total_turnover": 5000,
                        "total_user_income": 4000,
                        "total_refunds": 100,
                        "count_payments": 5,
                        "count_refunds": 0,
                    }
                ),
            },
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_course_benefit (course, amount, payment_amount, status, "time", buyer, promo_code, currency_code, _raw_json)
            VALUES (101, '1000', '1200', 'completed', '2026-07-01T10:00:00Z', 1001, NULL, 'RUB', :j1),
                   (101, '-200', '1200', 'refunded', '2026-07-05T10:00:00Z', 1002, 'DISCOUNT10', 'RUB', :j2)
        """),
            {
                "j1": json.dumps(
                    {
                        "course": 101,
                        "amount": 1000,
                        "payment_amount": 1200,
                        "status": "completed",
                        "time": "2026-07-01T10:00:00Z",
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
                        "time": "2026-07-05T10:00:00Z",
                        "buyer": 1002,
                        "promo_code": "DISCOUNT10",
                        "currency_code": "RUB",
                    }
                ),
            },
        )
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
        assert data["courses"][0]["refunds"] == 200

        assert len(data["promos"]) == 1
        assert data["promos"][0]["promo_code"] == "DISCOUNT10"
        assert data["promos"][0]["refunds"] == 200

        assert len(data["utms"]) == 1
        u = data["utms"][0]
        assert u["utm_source"] == "Я.Директ"
        assert u["payments"] == 1
        assert u["turnover"] == 1200
        assert u["income"] == 1000
        assert u["refunds"] == 0
        assert u["last_used"] == "2026-07-01T10:00:00Z"

        assert len(data["recent_payments"]) == 2
        assert data["recent_payments"][0]["promo_code"] == "DISCOUNT10"
        assert data["recent_payments"][0]["utm_source"] is None
        assert data["recent_payments"][0]["utm_source_label"] is None
        assert data["recent_payments"][1]["utm_source"] == "yandex_stpk"
        assert data["recent_payments"][1]["utm_source_label"] == "Я.Директ"
        assert data["recent_payments"][1]["channel"] == "Stepik"
        assert data["recent_payments"][1]["is_gift"] is False
        assert data["recent_payments"][1]["raw"]["last_course_click_utm"]["utm_campaign"] == "rsya_yad_feed_stepik_rus"

    @pytest.mark.asyncio
    async def test_recent_payments_returns_all(self, db_session):
        """Regression: recent_payments обрезался [:30] — «Последние операции»
        показывали максимум 3 страницы, хотя в raw-слое больше платежей."""
        from app.services.transform import transform_financials

        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101, title="Python 101")
        await db_session.commit()

        for i in range(1, 36):
            await db_session.execute(
                text("""
                INSERT INTO raw_course_benefit (course, amount, payment_amount, status, "time", _raw_json)
                VALUES (:course, '1000', '1200', 'completed', :time, :j)
            """),
                {
                    "course": 101,
                    "time": f"2026-07-{i:02d}T10:00:00Z",
                    "j": json.dumps(
                        {
                            "course": 101,
                            "amount": 1000,
                            "payment_amount": 1200,
                            "status": "completed",
                            "time": f"2026-07-{i:02d}T10:00:00Z",
                        }
                    ),
                },
            )
        await db_session.commit()

        await transform_financials(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        data = json.loads(r.fetchone()[0])
        assert len(data["recent_payments"]) == 35
        assert data["utms"] == []

    @pytest.mark.asyncio
    async def test_channel_and_gift_flags(self, db_session):
        """Канал платежа: is_invoice_payment → «По счету»,
        is_z_link_used → «А-ссылка», иначе → «Stepik».
        Подарок: is_gift → true."""
        from app.services.transform import transform_financials

        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101, title="Python 101")
        await db_session.commit()

        seeds = [
            ("2026-07-03T10:00:00Z", {"is_invoice_payment": True}),
            ("2026-07-02T10:00:00Z", {"is_z_link_used": True}),
            ("2026-07-01T10:00:00Z", {"is_gift": True}),
        ]
        for time, flags in seeds:
            row = {
                "course": 101,
                "amount": 1000,
                "payment_amount": 1200,
                "status": "completed",
                "time": time,
                **flags,
            }
            await db_session.execute(
                text("""
                INSERT INTO raw_course_benefit (course, amount, payment_amount, status, "time", _raw_json)
                VALUES (:course, '1000', '1200', 'completed', :time, :j)
            """),
                {"course": 101, "time": time, "j": json.dumps(row)},
            )
        await db_session.commit()

        await transform_financials(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        data = json.loads(r.fetchone()[0])
        by_time = {p["time"]: p for p in data["recent_payments"]}
        assert by_time["2026-07-03T10:00:00Z"]["channel"] == "По счету"
        assert by_time["2026-07-02T10:00:00Z"]["channel"] == "А-ссылка"
        assert by_time["2026-07-01T10:00:00Z"]["channel"] == "Stepik"
        assert by_time["2026-07-01T10:00:00Z"]["is_gift"] is True
        assert by_time["2026-07-03T10:00:00Z"]["is_gift"] is False

    @pytest.mark.asyncio
    async def test_recent_payment_student_name(self, db_session):
        """Regression: в «Последних операциях» нет имени студента-покупателя.

        Имя берётся из raw_user по buyer id, как и в витрине студентов.
        """
        from app.services.transform import transform_financials

        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101, title="Python 101")
        await db_session.execute(
            text("""
            INSERT INTO raw_user (user_id, first_name, last_name, _raw_json)
            VALUES ('777', 'Иван', 'Петров', :j)
        """),
            {"j": json.dumps({"id": 777, "first_name": "Иван", "last_name": "Петров"})},
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_course_benefit (course, amount, payment_amount, status, "time", buyer, _raw_json)
            VALUES (101, '1000', '1200', 'completed', '2026-07-01T10:00:00Z', 777, :j),
                   (101, '2000', '2400', 'completed', '2026-07-02T10:00:00Z', NULL, :j2)
        """),
            {
                "j": json.dumps(
                    {
                        "course": 101,
                        "amount": 1000,
                        "payment_amount": 1200,
                        "status": "completed",
                        "time": "2026-07-01T10:00:00Z",
                        "buyer": 777,
                    }
                ),
                "j2": json.dumps(
                    {
                        "course": 101,
                        "amount": 2000,
                        "payment_amount": 2400,
                        "status": "completed",
                        "time": "2026-07-02T10:00:00Z",
                        "buyer": None,
                    }
                ),
            },
        )
        await db_session.commit()

        await transform_financials(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        data = json.loads(r.fetchone()[0])
        by_time = {p["time"]: p for p in data["recent_payments"]}
        assert by_time["2026-07-01T10:00:00Z"]["student"] == "Иван Петров"
        assert by_time["2026-07-02T10:00:00Z"]["student"] is None

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

    @pytest.mark.asyncio
    async def test_preserves_community_block(self, db_session):
        """Regression: transform_financials (DELETE+INSERT) терял community-блок.

        Если community-этап после финансов падал, снапшот оставался без
        community — плашки Отзывы/Комментарии/Средний рейтинг обнулялись.
        """
        from app.services.transform import transform_financials

        _make_user(db_session)
        await db_session.commit()

        await db_session.execute(
            text("""
            INSERT INTO financial_snapshots (id, data, updated_at)
            VALUES (:id, :data, :now)
        """),
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "data": json.dumps({"community": {"total_comments": 1561, "total_reviews": 20}}),
                "now": datetime.now(UTC).replace(tzinfo=None),
            },
        )
        await db_session.commit()

        await transform_financials(db_session)
        await db_session.commit()

        r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
        row = r.fetchone()
        data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert data["community"]["total_comments"] == 1561
        assert data["community"]["total_reviews"] == 20


# ─── transform_community ───────────────────────────────────────────────


class TestTransformCommunity:
    @pytest.mark.asyncio
    async def test_community_data_added_to_snapshot(self, db_session):
        from app.services.transform import transform_community

        user = _make_user(db_session)
        await _make_course(db_session, user.id, stepik_course_id=101)
        await db_session.execute(
            text("""
            INSERT INTO financial_snapshots (id, data, updated_at)
            VALUES (:id, :data, :now)
        """),
            {
                "id": str(uuid.uuid4()),
                "data": json.dumps(
                    {"summary": {"total_turnover": 5000}, "months": [], "courses": [], "recent_payments": []}
                ),
                "now": datetime.now(UTC),
            },
        )
        await db_session.commit()

        await db_session.execute(
            text("""
            INSERT INTO raw_course_review_summary (average, count, _raw_json)
            VALUES ('4.5', 100, '{"average": 4.5, "count": 100, "course": 101}')
        """)
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_comment ("user", target, "time", thread, _raw_json)
            VALUES (1, 101, '2026-07-10T10:00:00Z', '', :j1),
                   (2, 101, '2026-07-11T10:00:00Z', 'solutions', :j2)
        """),
            {
                "j1": json.dumps({"user": 1, "target": 101, "time": "2026-07-10T10:00:00Z", "thread": ""}),
                "j2": json.dumps({"user": 2, "target": 101, "time": "2026-07-11T10:00:00Z", "thread": "solutions"}),
            },
        )
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


# ─── Schema validation: transform queries match raw table columns ──────


COLS_BY_RAW_TABLE = {
    "raw_course": {"course_id", "title", "became_published_at", "is_public"},
    "raw_step": {"step_id", "lesson"},
    "raw_unit": {"lesson_id", "section_id"},
    "raw_section": {"section_id", "course"},
    "raw_course_grade": {"user_id", "course_id", "score", "last_viewed", "date_joined"},
    "raw_certificate": {"user_id", "course_id"},
    "raw_attempt": {"attempt_id", "step", "user"},
}


async def _get_raw_table_columns(session, table: str) -> set[str]:
    """Return set of column names for a raw_* table via PRAGMA."""
    r = await session.execute(text(f"SELECT name FROM pragma_table_info('{table}')"))
    return {row[0].lower() for row in r}


@pytest.mark.asyncio
async def test_transform_queries_match_raw_columns(db_session):
    """Regression: each transform SQL query references only columns that exist in its raw_* table."""
    for table, expected_cols in COLS_BY_RAW_TABLE.items():
        actual_cols = await _get_raw_table_columns(db_session, table)
        missing = expected_cols - actual_cols
        assert not missing, f"{table}: missing columns expected by transform: {missing}"


# ─── transform_students ─────────────────────────────────────────────────


class TestTransformStudents:
    async def test_builds_student_marts(self, db_session):
        from app.models import Course, StudentEnrollment, Submission
        from app.services.transform import transform_students

        user = _make_user(db_session)
        c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=101, title="JS", status="Published")
        db_session.add_all([c1, c2])
        await db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        db_session.add_all(
            [
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    student_id=7,
                    last_viewed_at=now,
                    cohort_status="Active",
                    certificate_issued=True,
                ),
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c2.id,
                    student_id=7,
                    last_viewed_at=now,
                    cohort_status="Passive",
                    certificate_issued=False,
                ),
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    student_id=9,
                    last_viewed_at=now,
                    cohort_status="Active",
                    certificate_issued=True,
                ),
            ]
        )
        for i, status in [(0, "correct"), (1, "correct"), (2, "wrong")]:
            db_session.add(
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=2000 + i,
                    stepik_step_id=10,
                    course_id=c1.id,
                    status=status,
                    score=1.0,
                    submission_time=now,
                    user_id=7,
                    is_author=False,
                )
            )
        db_session.add(
            Submission(
                id=uuid.uuid4(),
                stepik_submission_id=2100,
                stepik_step_id=10,
                course_id=c1.id,
                status="correct",
                score=1.0,
                submission_time=now,
                user_id=7,
                is_author=True,
            )
        )
        for cid, uid, thread in [(1, 7, "solutions"), (2, 7, "step-10-1"), (3, 8, "solutions")]:
            await db_session.execute(
                text("INSERT INTO raw_comment (comment_id, \"user\", _raw_json) VALUES (:c, 'x', :j)"),
                {"c": cid, "j": json.dumps({"user": uid, "thread": thread})},
            )
        await db_session.execute(
            text("INSERT INTO raw_user (user_id, first_name, last_name) VALUES (7, 'Иван', 'Петров')")
        )
        await db_session.commit()

        await transform_students(db_session)

        r = await db_session.execute(
            text(
                "SELECT student_id, name, cohort_status, courses_count, certificates, submissions_count, submissions_successful, comments_count, published_solutions, last_activity FROM student_marts ORDER BY student_id"
            )
        )
        rows = [dict(row._mapping) for row in r]
        assert len(rows) == 2
        by_id = {row["student_id"]: row for row in rows}

        s7 = by_id[7]
        assert s7["name"] == "Иван Петров"
        assert s7["cohort_status"] == "Active"
        assert s7["courses_count"] == 2
        assert s7["certificates"] == 1
        assert s7["submissions_count"] == 3
        assert s7["submissions_successful"] == 2
        assert s7["comments_count"] == 2
        assert s7["published_solutions"] == 1
        assert s7["last_activity"] is not None

        s9 = by_id[9]
        assert s9["name"] is None
        assert s9["courses_count"] == 1
        assert s9["certificates"] == 1

    async def test_rebuilds_mart_from_scratch(self, db_session):
        from app.models import Course, StudentEnrollment
        from app.services.transform import transform_students

        user = _make_user(db_session)
        course = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        db_session.add(course)
        await db_session.flush()
        now = datetime.now(UTC).replace(tzinfo=None)
        db_session.add(StudentEnrollment(id=uuid.uuid4(), course_id=course.id, student_id=7, last_viewed_at=now))
        await db_session.commit()

        await transform_students(db_session)

        # Student 7 удалён из зачислений — витрина обязана пересобраться без него
        await db_session.execute(text("DELETE FROM student_enrollments"))
        await db_session.commit()
        await transform_students(db_session)

        r = await db_session.execute(text("SELECT COUNT(*) FROM student_marts"))
        assert r.scalar() == 0
