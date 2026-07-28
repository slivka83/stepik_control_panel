"""Edge case tests for sync module: course deletion, no user, STEPIK_USER_ID unset."""
import uuid
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest

from app.models import User, Course, StudentEnrollment, FinancialSnapshot
from app.services.sync import (
    sync_courses_and_enrollments, sync_submissions, sync_financials,
    sync_community_stats, sync_all, calculate_cohort_status, can_sync,
    SYNC_COOLDOWN_SECONDS, MONTH_NAMES,
)
from app.services.crypto import encrypt_token


def _make_user(session, user_id=None, token="test_token_123"):
    import uuid
    user = User(
        id=user_id or uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token(token),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(user)
    return user


def _make_course(session, user_id, stepik_course_id=100, title="Python Course"):
    course = Course(
        id=uuid.uuid4(),
        user_id=user_id,
        stepik_course_id=stepik_course_id,
        title=title,
        status="Published",
        health_score=100.0,
    )
    session.add(course)
    return course


class TestSyncCoursesEdgeCases:
    @pytest.mark.asyncio
    async def test_course_deleted_from_api(self, db_session):
        """Course that existed in DB but not in API response should be removed."""
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=999, title="Old Course")
        await db_session.commit()

        async def fake_paginated_get(path, token, params=None, key=None, on_page=None, max_pages=500):
            if "courses" in path:
                return [{"id": 100, "title": "New Course", "is_public": True}]
            if "course-grades" in path:
                return []
            if "certificates" in path:
                return []
            return []

        with patch("app.services.sync._paginated_get", side_effect=fake_paginated_get):
            with patch("app.services.sync.decrypt_token", return_value="raw_token"):
                with patch("app.config.get_settings") as mock_settings:
                    mock_settings.return_value.stepik_user_id = 12345
                    await sync_courses_and_enrollments(user_id=user.id)

        from sqlalchemy import select
        courses = (await db_session.execute(select(Course))).scalars().all()
        assert len(courses) == 1
        assert courses[0].stepik_course_id == 100
        assert courses[0].title == "New Course"

    @pytest.mark.asyncio
    async def test_no_user_found_skips(self, db_session):
        """No user in DB => sync should log warning and return."""
        with patch("app.services.sync.decrypt_token", return_value="raw_token"):
            await sync_courses_and_enrollments(user_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_stepik_user_id_not_set(self, db_session):
        """STEPIK_USER_ID not configured => sync should return early."""
        user = _make_user(db_session)
        await db_session.commit()

        with patch("app.services.sync.decrypt_token", return_value="raw_token"):
            with patch("app.config.get_settings") as mock_settings:
                mock_settings.return_value.stepik_user_id = None
                await sync_courses_and_enrollments(user_id=user.id)

    @pytest.mark.asyncio
    async def test_enrollments_with_various_cohorts(self, db_session):
        """Enrollments with different last_viewed dates produce correct cohort statuses."""
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=200)
        await db_session.commit()

        mock_courses = [{"id": 200, "title": "Test", "is_public": True}]
        now = int(datetime.now(timezone.utc).timestamp())
        mock_grades = [
            {"user": 1, "score": 90, "last_viewed": now - 86400 * 3},
            {"user": 2, "score": 80, "last_viewed": now - 86400 * 15},
            {"user": 3, "score": 70, "last_viewed": now - 86400 * 60},
            {"user": 4, "score": 60, "last_viewed": now - 86400 * 200},
        ]
        mock_certs = []

        async def fake_paginated_get(path, token, params=None, key=None, on_page=None, max_pages=500):
            if "courses" in path:
                return mock_courses
            if "course-grades" in path:
                return mock_grades
            if "certificates" in path:
                return mock_certs
            return []

        with patch("app.services.sync._paginated_get", side_effect=fake_paginated_get):
            with patch("app.services.sync.decrypt_token", return_value="raw_token"):
                with patch("app.config.get_settings") as mock_settings:
                    mock_settings.return_value.stepik_user_id = 12345
                    await sync_courses_and_enrollments(user_id=user.id)

        from sqlalchemy import select
        enrollments = (await db_session.execute(select(StudentEnrollment))).scalars().all()
        assert len(enrollments) == 4
        statuses = {e.cohort_status for e in enrollments}
        assert "Active" in statuses
        assert "Passive" in statuses
        assert "Fading" in statuses
        assert "Sleeping" in statuses

    @pytest.mark.asyncio
    async def test_grades_with_none_last_viewed(self, db_session):
        """Grades with None last_viewed should be Sleeping."""
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=300)
        await db_session.commit()

        mock_courses = [{"id": 300, "title": "Test", "is_public": True}]
        mock_grades = [
            {"user": 1, "score": 50, "last_viewed": None},
        ]
        mock_certs = []

        async def fake_paginated_get(path, token, params=None, key=None, on_page=None, max_pages=500):
            if "courses" in path:
                return mock_courses
            if "course-grades" in path:
                return mock_grades
            if "certificates" in path:
                return mock_certs
            return []

        with patch("app.services.sync._paginated_get", side_effect=fake_paginated_get):
            with patch("app.services.sync.decrypt_token", return_value="raw_token"):
                with patch("app.config.get_settings") as mock_settings:
                    mock_settings.return_value.stepik_user_id = 12345
                    await sync_courses_and_enrollments(user_id=user.id)

        from sqlalchemy import select
        enrollments = (await db_session.execute(select(StudentEnrollment))).scalars().all()
        assert enrollments[0].cohort_status == "Sleeping"
        assert enrollments[0].last_viewed_at is None

    @pytest.mark.asyncio
    async def test_grades_api_failure_returns_empty(self, db_session):
        """If grades API fails, sync should continue with empty enrollments."""
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=400)
        await db_session.commit()

        mock_courses = [{"id": 400, "title": "Test", "is_public": True}]

        async def fake_paginated_get(path, token, params=None, key=None, on_page=None, max_pages=500):
            if "courses" in path:
                return mock_courses
            if "course-grades" in path:
                raise Exception("API timeout")
            if "certificates" in path:
                return []
            return []

        with patch("app.services.sync._paginated_get", side_effect=fake_paginated_get):
            with patch("app.services.sync.decrypt_token", return_value="raw_token"):
                with patch("app.config.get_settings") as mock_settings:
                    mock_settings.return_value.stepik_user_id = 12345
                    await sync_courses_and_enrollments(user_id=user.id)

        from sqlalchemy import select
        enrollments = (await db_session.execute(select(StudentEnrollment))).scalars().all()
        assert len(enrollments) == 0


class TestCalculateCohortStatusEdgeCases:
    def test_none_date_joined_returns_sleeping(self):
        result = calculate_cohort_status(datetime.now(timezone.utc) - timedelta(days=200), None)
        assert result == "Sleeping"

    def test_zombie_none_date_joined_none_last_viewed(self):
        assert calculate_cohort_status(None, None) == "Sleeping"

    def test_zombie_none_last_viewed_with_date_joined(self):
        assert calculate_cohort_status(None, datetime.now(timezone.utc)) == "Sleeping"

    def test_zombie_naive_datetime(self, monkeypatch):
        from datetime import datetime as dt_mod
        now = dt_mod.now(timezone.utc)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=2)
        assert calculate_cohort_status(old.replace(tzinfo=None), joined.replace(tzinfo=None)) == "Zombie"

    def test_zombie_within_3_days_boundary(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=3)
        assert calculate_cohort_status(old, joined) == "Zombie"

    def test_sleeping_after_3_days_boundary(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=4)
        assert calculate_cohort_status(old, joined) == "Sleeping"


class TestCanSyncEdgeCases:
    def test_can_sync_after_reset(self):
        import app.services.sync as sync_mod
        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0
        assert can_sync() is True

    def test_can_sync_exact_cooldown_boundary(self):
        import app.services.sync as sync_mod
        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = time.time() - SYNC_COOLDOWN_SECONDS
        assert can_sync() is True

    def test_cannnot_sync_just_before_cooldown(self):
        import app.services.sync as sync_mod
        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = time.time() - SYNC_COOLDOWN_SECONDS + 0.5
        assert can_sync() is False


class TestSyncFinancialsEdgeCases:
    @pytest.mark.asyncio
    async def test_no_courses_still_creates_snapshot(self, db_session):
        user = _make_user(db_session)
        await db_session.commit()

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [[], []]
            await sync_financials()

        from sqlalchemy import select
        result = await db_session.execute(select(FinancialSnapshot))
        snapshot = result.scalar_one_or_none()
        assert snapshot is not None
        assert snapshot.data["summary"]["total_turnover"] == 0
        assert snapshot.data["courses"] == []

    @pytest.mark.asyncio
    async def test_finance_token_failure_skips(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id)
        await db_session.commit()

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, side_effect=Exception("no token")):
            await sync_financials()

        from sqlalchemy import select
        result = await db_session.execute(select(FinancialSnapshot))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_empty_by_months_and_benefits(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id)
        await db_session.commit()

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=[]):
            await sync_financials()

        from sqlalchemy import select
        result = await db_session.execute(select(FinancialSnapshot))
        snapshot = result.scalar_one_or_none()
        assert snapshot is not None
        assert snapshot.data["months"] == []
        assert snapshot.data["promos"] == []

    @pytest.mark.asyncio
    async def test_current_month_detection(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id)
        await db_session.commit()

        now = datetime.now(timezone.utc)
        by_months = [
            {"year": now.year, "month": now.month, "total_turnover": 5000,
             "total_user_income": 4000, "total_refunds": 100, "count_payments": 10, "count_refunds": 1},
        ]

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [by_months, []]
            await sync_financials()

        from sqlalchemy import select
        snapshot = (await db_session.execute(select(FinancialSnapshot))).scalar_one_or_none()
        assert snapshot.data["summary"]["current_month_turnover"] == 5000
        assert snapshot.data["summary"]["current_month_income"] == 4000
        assert snapshot.data["summary"]["current_month_payments"] == 10


class TestMonthNames:
    def test_all_months_present(self):
        assert len(MONTH_NAMES) == 12

    def test_month_names_russian(self):
        assert MONTH_NAMES[1] == "Январь"
        assert MONTH_NAMES[12] == "Декабрь"


class TestSyncProgressReset:
    @pytest.mark.asyncio
    async def test_sync_all_resets_progress_via_error(self):
        import app.services.sync as sync_mod
        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0
        sync_mod._sync_progress = 50
        sync_mod._sync_step = "test"

        with patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock, side_effect=Exception("fail")):
            await sync_all(force=True)

        assert sync_mod._sync_progress == 0
        assert sync_mod._sync_step == ""
        assert sync_mod._sync_in_progress is False
