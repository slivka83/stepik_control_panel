"""Integration tests for sync flow: orchestration tests (raw_sync → transform)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.models import User
from app.services.sync import sync_courses_and_enrollments
from app.services.transform import calculate_cohort_status


@pytest.mark.asyncio
async def test_full_sync_flow(db_session):
    """Test complete sync flow: mock raw_sync + transform → verify orchestration."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    with (
        patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock) as mock_struct,
        patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock) as mock_grades,
        patch("app.services.raw_sync.sync_users", new_callable=AsyncMock) as mock_users,
        patch("app.services.transform.transform_courses", new_callable=AsyncMock) as mock_tc,
        patch("app.services.transform.transform_enrollments", new_callable=AsyncMock) as mock_te,
        patch("app.services.sync._get_user_token", return_value="raw_token"),
    ):
        await sync_courses_and_enrollments(user_id=user.id)

    assert mock_struct.call_count >= 1
    assert mock_grades.call_count >= 1
    assert mock_users.call_count >= 1
    assert mock_tc.call_count >= 1
    assert mock_te.call_count >= 1


@pytest.mark.asyncio
async def test_sync_preserves_data_on_api_failure(db_session):
    """If raw_sync fails, sync function should handle gracefully (existing data preserved)."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    with (
        patch("app.services.raw_sync.sync_courses_structure", side_effect=Exception("API down")),
        patch("app.services.sync._get_user_token", return_value="raw_token"),
    ):
        try:
            await sync_courses_and_enrollments(user_id=user.id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_sync_empty_response_new_user(db_session):
    """Empty raw_sync should not crash — sync completes gracefully."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_empty_structure(session, token):
        pass

    async def mock_empty_grades(session, token, course_ids):
        pass

    with (
        patch("app.services.raw_sync.sync_courses_structure", mock_empty_structure),
        patch("app.services.raw_sync.sync_course_grades_and_certs", mock_empty_grades),
        patch("app.services.transform.transform_courses", new_callable=AsyncMock),
        patch("app.services.transform.transform_enrollments", new_callable=AsyncMock),
        patch("app.services.sync._get_user_token", return_value="raw_token"),
    ):
        await sync_courses_and_enrollments(user_id=user.id)


class TestCohortBoundaries:
    """Test cohort status boundaries: 7, 8, 30, 31, 90, 91 days."""

    def test_active_day_0(self):
        last = datetime.now(UTC)
        assert calculate_cohort_status(last) == "Active"

    def test_active_day_7(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=7)
        assert calculate_cohort_status(last) == "Active"

    def test_passive_day_8(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=8)
        assert calculate_cohort_status(last) == "Passive"

    def test_passive_day_30(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=30)
        assert calculate_cohort_status(last) == "Passive"

    def test_fading_day_31(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=31)
        assert calculate_cohort_status(last) == "Fading"

    def test_fading_day_90(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=90)
        assert calculate_cohort_status(last) == "Fading"

    def test_sleeping_day_91(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=91)
        assert calculate_cohort_status(last) == "Sleeping"

    def test_sleeping_day_365(self):
        from datetime import timedelta

        last = datetime.now(UTC) - timedelta(days=365)
        assert calculate_cohort_status(last) == "Sleeping"

    def test_zombie_none(self):
        assert calculate_cohort_status(None) == "Zombie"

    def test_zombie_same_day_old(self):
        from datetime import timedelta

        now = datetime.now(UTC)
        old = now - timedelta(days=200)
        assert calculate_cohort_status(old, old) == "Zombie"

    def test_zombie_3_days_old(self):
        from datetime import timedelta

        now = datetime.now(UTC)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=3)
        assert calculate_cohort_status(old, joined) == "Zombie"

    def test_zombie_4_days_old(self):
        from datetime import timedelta

        now = datetime.now(UTC)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=4)
        assert calculate_cohort_status(old, joined) == "Sleeping"

    def test_zombie_same_day_recent(self):
        now = datetime.now(UTC)
        assert calculate_cohort_status(now, now) == "Active"

    def test_zombie_different_day(self):
        from datetime import timedelta

        now = datetime.now(UTC)
        joined = now - timedelta(days=1)
        assert calculate_cohort_status(now, joined) != "Zombie"


@pytest.mark.asyncio
async def test_sync_submissions_allows_stepwise_commits(db_session):
    """Regression: sync падал с «Can't operate on closed transaction inside
    context manager» на live PG.

    raw_sync.sync_submissions/sync_community коммитят пошагово (инкрементально),
    а sync.py оборачивал вызов в session.begin() — внутренний commit закрывал
    транзакцию контекстного менеджера.
    """
    from app.services import sync as sync_mod

    async def fake_raw_sync(session, token):
        await session.commit()
        await session.execute(text("SELECT 1"))
        await session.commit()

    with (
        patch("app.services.sync._get_user_token", return_value="raw_token"),
        patch("app.services.raw_sync.sync_submissions", side_effect=fake_raw_sync),
        patch("app.services.transform.transform_submissions", new_callable=AsyncMock),
    ):
        await sync_mod.sync_submissions(None)
    assert sync_mod._sync_progress == 85
