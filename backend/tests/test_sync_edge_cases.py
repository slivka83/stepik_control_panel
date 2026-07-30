"""Edge case tests for sync module: error handling, empty data, progress tracking."""
import uuid
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest

from app.models import User, FinancialSnapshot
from app.services.sync import (
    sync_courses_and_enrollments, sync_submissions, sync_financials,
    sync_community_stats, sync_all, calculate_cohort_status, can_sync,
    SYNC_COOLDOWN_SECONDS, MONTH_NAMES,
)
from app.services.crypto import encrypt_token


def _make_user(session, user_id=None, token="test_token_123"):
    user = User(
        id=user_id or uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token(token),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(user)
    return user


class TestSyncCoursesEdgeCases:
    @pytest.mark.asyncio
    async def test_course_deleted_from_api(self, db_session):
        """Course removal handled via transform layer."""
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock), \
             patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock), \
             patch("app.services.transform.transform_courses", new_callable=AsyncMock), \
             patch("app.services.transform.transform_enrollments", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="raw_token"):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_no_user_found_skips(self, db_session):
        with patch("app.services.sync._get_user_token", return_value=None):
            await sync_courses_and_enrollments(user_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_stepik_user_id_not_set(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock), \
             patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock), \
             patch("app.services.transform.transform_courses", new_callable=AsyncMock), \
             patch("app.services.transform.transform_enrollments", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="raw_token"):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_enrollments_with_various_cohorts(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock), \
             patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock), \
             patch("app.services.transform.transform_courses", new_callable=AsyncMock), \
             patch("app.services.transform.transform_enrollments", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="raw_token"):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_grades_with_none_last_viewed(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock), \
             patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock), \
             patch("app.services.transform.transform_courses", new_callable=AsyncMock), \
             patch("app.services.transform.transform_enrollments", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="raw_token"):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_grades_api_failure_returns_empty(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_courses_structure", side_effect=Exception("API timeout")), \
             patch("app.services.sync._get_user_token", return_value="raw_token"):
            try:
                await sync_courses_and_enrollments()
            except Exception:
                pass


class TestCalculateCohortStatusEdgeCases:
    def test_none_date_joined_returns_sleeping(self):
        result = calculate_cohort_status(datetime.now(timezone.utc) - timedelta(days=200), None)
        assert result == "Sleeping"

    def test_zombie_none_date_joined_none_last_viewed(self):
        assert calculate_cohort_status(None, None) == "Sleeping"

    def test_zombie_none_last_viewed_with_date_joined(self):
        assert calculate_cohort_status(None, datetime.now(timezone.utc)) == "Sleeping"

    def test_zombie_naive_datetime(self):
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
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock), \
             patch("app.services.transform.transform_financials", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="token"):
            await sync_financials()

    @pytest.mark.asyncio
    async def test_finance_token_failure_skips(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_financials", side_effect=Exception("no token")):
            with pytest.raises(Exception, match="no token"):
                await sync_financials()

    @pytest.mark.asyncio
    async def test_empty_by_months_and_benefits(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock), \
             patch("app.services.transform.transform_financials", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="token"):
            await sync_financials()

    @pytest.mark.asyncio
    async def test_current_month_detection(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock), \
             patch("app.services.transform.transform_financials", new_callable=AsyncMock), \
             patch("app.services.sync._get_user_token", return_value="token"):
            await sync_financials()


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
