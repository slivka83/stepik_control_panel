"""Tests for raw_sync service: API → raw table syncing."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.models import User
from app.services.crypto import encrypt_token


def _make_user(session, stepik_id=12345):
    import uuid
    from datetime import timedelta
    user = User(
        id=uuid.uuid4(), stepik_id=stepik_id,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(user)
    return user


async def _count_rows(session, table: str):
    r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return r.scalar()


def _fake_response(data: list, has_next=False):
    endpoint = "courses"
    if data:
        api_key = "courses"
    else:
        api_key = "courses"
    return {api_key: data, "meta": {"has_next": has_next}}


def _side_effect(pages: list[list[dict]]):
    """Create a side_effect for _request mock that returns pages of data."""
    results = []
    for page_data in pages:
        # Guess the endpoint key from the path
        results.append({"courses": page_data, "course-grades": page_data,
                        "certificates": page_data, "sections": page_data,
                        "units": page_data, "lessons": page_data,
                        "steps": page_data, "submissions": page_data,
                        "attempts": page_data, "course-benefit-by-months": page_data,
                        "course-benefits": page_data,
                        "course-review-summaries": page_data,
                        "comments": page_data,
                        "meta": {"has_next": False}})
    return results


# ─── sync_courses_structure ────────────────────────────────────────────

class TestSyncCoursesStructure:
    @pytest.mark.asyncio
    async def test_writes_to_raw_tables(self, db_session):
        from app.services.raw_sync import sync_courses_structure
        _make_user(db_session)
        await db_session.commit()

        fake_courses = [{"id": 101, "title": "Course 1", "sections": [1], "owner_user_id": 12345}]
        fake_sections = [{"id": 1, "course": 101, "units": [10], "section_id": 1}]
        fake_units = [{"id": 10, "lesson": 100, "section": 1, "unit_id": 10}]
        fake_lessons = [{"id": 100, "steps": [500], "lesson_id": 100}]
        fake_steps = [{"id": 500, "lesson": 100, "step_id": 500}]

        def request_side_effect(method, path, token, params=None):
            if "courses" in path and "teacher" in str(params):
                return {"courses": fake_courses, "meta": {"has_next": False}}
            if "sections" in path and "ids[]" in str(params):
                return {"sections": fake_sections, "meta": {"has_next": False}}
            if "units" in path and "ids[]" in str(params):
                return {"units": fake_units, "meta": {"has_next": False}}
            if "lessons" in path and "ids[]" in str(params):
                return {"lessons": fake_lessons, "meta": {"has_next": False}}
            if "steps" in path and "ids[]" in str(params):
                return {"steps": fake_steps, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect), \
             patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.stepik_user_id = 12345
            await sync_courses_structure(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_course") == 1
        assert await _count_rows(db_session, "raw_section") == 1
        assert await _count_rows(db_session, "raw_unit") == 1
        assert await _count_rows(db_session, "raw_lesson") == 1
        assert await _count_rows(db_session, "raw_step") == 1


# ─── sync_course_grades_and_certs ──────────────────────────────────────

class TestSyncCourseGradesAndCerts:
    @pytest.mark.asyncio
    async def test_writes_grades_and_certs(self, db_session):
        from app.services.raw_sync import sync_course_grades_and_certs
        _make_user(db_session)
        await db_session.commit()

        fake_grades = [
            {"user": 1001, "course": 101, "score": 85, "last_viewed": 1700000000},
        ]
        fake_certs = [{"user_id": 1001, "course": 101}]

        def request_side_effect(method, path, token, params=None):
            if "course-grades" in path:
                return {"course-grades": fake_grades, "meta": {"has_next": False}}
            if "certificates" in path:
                return {"certificates": fake_certs, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_course_grades_and_certs(db_session, "fake_token", [101])

        assert await _count_rows(db_session, "raw_course_grade") == 1
        assert await _count_rows(db_session, "raw_certificate") == 1


# ─── sync_submissions ──────────────────────────────────────────────────

class TestSyncSubmissions:
    @pytest.mark.asyncio
    async def test_writes_submissions_and_attempts(self, db_session):
        from app.services.raw_sync import sync_submissions
        _make_user(db_session)
        await db_session.commit()

        # Need steps to exist in raw_step for submission sync
        await db_session.execute(text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (500, 10, '{}')
        """))
        await db_session.commit()

        fake_subs = [
            {"id": 1000, "step": 500, "status": "correct", "time": "2026-07-15T10:00:00Z",
             "score": 1.0, "reply": {}, "attempt": 10},
        ]
        fake_attempts = [{"id": 10, "user": 12345, "step": 500}]

        def request_side_effect(method, path, token, params=None):
            if "submissions" in path and "step" in str(params):
                return {"submissions": fake_subs, "meta": {"has_next": False}}
            if "submissions" in path and "course" in str(params):
                return {"submissions": [], "meta": {"has_next": False}}
            if "attempts" in path:
                return {"attempts": fake_attempts, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_submissions(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_submission") == 1
        assert await _count_rows(db_session, "raw_attempt") == 1


# ─── sync_financials ───────────────────────────────────────────────────

class TestSyncFinancials:
    @pytest.mark.asyncio
    async def test_writes_financial_tables(self, db_session):
        from app.services.raw_sync import sync_financials
        _make_user(db_session)
        await db_session.commit()

        fake_by_months = [
            {"year": 2026, "month": 7, "total_turnover": 10000, "total_user_income": 8000,
             "total_refunds": 200, "count_payments": 10, "count_refunds": 1},
        ]
        fake_benefits = [
            {"id": 1, "course": 101, "amount": 1000, "payment_amount": 1200,
             "status": "completed", "time": "2026-07-01T10:00:00Z", "buyer": 1001,
             "promo_code": None, "currency_code": "RUB"},
        ]

        def request_side_effect(method, path, token, params=None):
            if "course-benefit-by-months" in path:
                return {"course-benefit-by-months": fake_by_months, "meta": {"has_next": False}}
            if "course-benefits" in path:
                return {"course-benefits": fake_benefits, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync.get_finance_token", return_value="finance_token"), \
             patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_financials(db_session)

        assert await _count_rows(db_session, "raw_course_benefit_by_month") == 1
        assert await _count_rows(db_session, "raw_course_benefit") == 1

    @pytest.mark.asyncio
    async def test_skips_without_token(self, db_session):
        from app.services.raw_sync import sync_financials
        with patch("app.services.raw_sync.get_finance_token", return_value=None):
            await sync_financials(db_session)


# ─── sync_community ────────────────────────────────────────────────────

class TestSyncCommunity:
    @pytest.mark.asyncio
    async def test_writes_reviews_and_comments(self, db_session):
        from app.services.raw_sync import sync_community
        _make_user(db_session)
        await db_session.commit()

        await db_session.execute(text("""
            INSERT INTO raw_course (course_id, review_summary_json, _raw_json)
            VALUES (101, '[42]', '{"id": 101, "review_summary": 42}')
        """))
        await db_session.commit()

        fake_reviews = [{"id": 42, "average": 4.5, "count": 100}]
        fake_comments = [{"id": 1, "user": 1001, "target": 101, "time": "2026-07-15T10:00:00Z", "thread": ""}]

        def request_side_effect(method, path, token, params=None):
            if "course-review-summaries" in path:
                return {"course-review-summaries": fake_reviews, "meta": {"has_next": False}}
            if "comments" in path:
                return {"comments": fake_comments, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_community(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_course_review_summary") == 1
        assert await _count_rows(db_session, "raw_comment") == 1
