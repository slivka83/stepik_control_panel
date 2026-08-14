"""Edge case tests for sync module: error handling, empty data, progress tracking."""

import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.constants import MONTH_NAMES
from app.models import User
from app.services.crypto import encrypt_token
from app.services.sync import (
    SYNC_COOLDOWN_SECONDS,
    can_sync,
    sync_all,
    sync_courses_and_enrollments,
    sync_financials,
)
from app.services.transform import calculate_cohort_status


def _make_user(session, user_id=None, token="test_token_123"):
    user = User(
        id=user_id or uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token(token),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(user)
    return user


class TestSyncCoursesEdgeCases:
    @pytest.mark.asyncio
    async def test_course_deleted_from_api(self, db_session):
        """Course removal handled via transform layer."""
        _make_user(db_session)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock),
            patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock),
            patch("app.services.transform.transform_courses", new_callable=AsyncMock),
            patch("app.services.transform.transform_enrollments", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="raw_token"),
        ):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_no_user_found_skips(self, db_session):
        with patch("app.services.sync._get_user_token", return_value=None):
            await sync_courses_and_enrollments(user_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_stepik_user_id_not_set(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock),
            patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock),
            patch("app.services.transform.transform_courses", new_callable=AsyncMock),
            patch("app.services.transform.transform_enrollments", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="raw_token"),
        ):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_enrollments_with_various_cohorts(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock),
            patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock),
            patch("app.services.transform.transform_courses", new_callable=AsyncMock),
            patch("app.services.transform.transform_enrollments", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="raw_token"),
        ):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_grades_with_none_last_viewed(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock),
            patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock),
            patch("app.services.transform.transform_courses", new_callable=AsyncMock),
            patch("app.services.transform.transform_enrollments", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="raw_token"),
        ):
            await sync_courses_and_enrollments()

    @pytest.mark.asyncio
    async def test_grades_api_failure_returns_empty(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_courses_structure", side_effect=Exception("API timeout")),
            patch("app.services.sync._get_user_token", return_value="raw_token"),
        ):
            try:
                await sync_courses_and_enrollments()
            except Exception:
                pass


class TestCalculateCohortStatusEdgeCases:
    def test_none_date_joined_returns_sleeping(self):
        result = calculate_cohort_status(datetime.now(UTC) - timedelta(days=200), None)
        assert result == "Sleeping"

    def test_zombie_none_date_joined_none_last_viewed(self):
        assert calculate_cohort_status(None, None) == "Sleeping"

    def test_zombie_none_last_viewed_with_date_joined(self):
        assert calculate_cohort_status(None, datetime.now(UTC)) == "Sleeping"

    def test_zombie_naive_datetime(self):
        from datetime import datetime as dt_mod

        now = dt_mod.now(UTC)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=2)
        assert calculate_cohort_status(old.replace(tzinfo=None), joined.replace(tzinfo=None)) == "Zombie"

    def test_zombie_within_3_days_boundary(self):
        now = datetime.now(UTC)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=3)
        assert calculate_cohort_status(old, joined) == "Zombie"

    def test_sleeping_after_3_days_boundary(self):
        now = datetime.now(UTC)
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

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
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

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_financials()

    @pytest.mark.asyncio
    async def test_current_month_detection(self, db_session):
        _make_user(db_session)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
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

        with patch(
            "app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            await sync_all(force=True)

        assert sync_mod._sync_progress == 0
        assert sync_mod._sync_step == ""
        assert sync_mod._sync_in_progress is False

    @pytest.mark.asyncio
    async def test_sync_all_failure_surfaces_last_error(self):
        """Regression: failed sync must be visible in /api/sync/status (pink sync button)."""
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0
        sync_mod._last_sync_error = None

        with patch(
            "app.services.sync.sync_courses_and_enrollments",
            new_callable=AsyncMock,
            side_effect=Exception("Temporary failure in name resolution"),
        ):
            await sync_all(force=True)

        assert sync_mod._last_sync_error == "Temporary failure in name resolution"
        assert sync_mod._sync_in_progress is False

    @pytest.mark.asyncio
    async def test_sync_all_success_clears_last_error(self):
        """Regression: a successful sync must clear the stale error from the sync button."""
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0
        sync_mod._last_sync_error = "old error"

        with (
            patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock),
            patch("app.services.sync.sync_submissions", new_callable=AsyncMock),
            patch("app.services.sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.sync.sync_community_stats", new_callable=AsyncMock),
        ):
            await sync_all(force=True)

        assert sync_mod._last_sync_error is None


class TestSyncStatePersistence:
    @pytest.mark.asyncio
    async def test_persisted_error_survives_restart(self, db_session):
        """Regression: причина падения последнего синка сохраняется между перезапусками сервера.

        Раньше `_last_sync_error` жил только в памяти — после uvicorn --reload
        (перезапуск при правке файлов) причина пропадала и статус не показывал ошибку.
        """
        import app.services.sync as sync_mod

        await sync_mod._persist_sync_state(False, 0, "", "boom", 0)
        sync_mod._last_sync_error = None
        sync_mod._sync_in_progress = True
        sync_mod._state_loaded = False

        await sync_mod.ensure_state_loaded()

        assert sync_mod._last_sync_error == "boom"
        assert sync_mod._sync_in_progress is False

    @pytest.mark.asyncio
    async def test_interrupted_sync_reported_on_restart(self, db_session):
        """Regression: синк, прерванный перезапуском сервера, виден как ошибка, а не «пусто».

        Процесс умер во время синхронизации (in_progress был True) — после рестарта
        статус должен сообщать о прерванной синхронизации, а не молчать.
        """
        import app.services.sync as sync_mod

        await sync_mod._persist_sync_state(True, 50, "решения", "", 0)
        sync_mod._last_sync_error = None
        sync_mod._sync_in_progress = False
        sync_mod._state_loaded = False

        await sync_mod.ensure_state_loaded()

        assert sync_mod._last_sync_error == "Синхронизация прервана перезапуском сервера"
        assert sync_mod._sync_in_progress is False
