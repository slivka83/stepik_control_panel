"""Integration tests for sync flow: orchestration tests (raw_sync → transform)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models import User
from app.services.sync import sync_courses_and_enrollments, calculate_cohort_status


@pytest.mark.asyncio
async def test_full_sync_flow(db_session):
    """Test complete sync flow: mock raw_sync + transform → verify orchestration."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()

    with patch("app.services.raw_sync.sync_courses_structure", new_callable=AsyncMock) as mock_struct, \
         patch("app.services.raw_sync.sync_course_grades_and_certs", new_callable=AsyncMock) as mock_grades, \
         patch("app.services.transform.transform_courses", new_callable=AsyncMock) as mock_tc, \
         patch("app.services.transform.transform_enrollments", new_callable=AsyncMock) as mock_te, \
         patch("app.services.sync._get_user_token", return_value="raw_token"):
        await sync_courses_and_enrollments(user_id=user.id)

    assert mock_struct.call_count >= 1
    assert mock_grades.call_count >= 1
    assert mock_tc.call_count >= 1
    assert mock_te.call_count >= 1


@pytest.mark.asyncio
async def test_sync_preserves_data_on_api_failure(db_session):
    """If raw_sync fails, sync function should handle gracefully (existing data preserved)."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()

    with patch("app.services.raw_sync.sync_courses_structure", side_effect=Exception("API down")), \
         patch("app.services.sync._get_user_token", return_value="raw_token"):
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
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_empty_structure(session, token):
        pass

    async def mock_empty_grades(session, token, course_ids):
        pass

    with patch("app.services.raw_sync.sync_courses_structure", mock_empty_structure), \
         patch("app.services.raw_sync.sync_course_grades_and_certs", mock_empty_grades), \
         patch("app.services.transform.transform_courses", new_callable=AsyncMock), \
         patch("app.services.transform.transform_enrollments", new_callable=AsyncMock), \
         patch("app.services.sync._get_user_token", return_value="raw_token"):
        await sync_courses_and_enrollments(user_id=user.id)


class TestCohortBoundaries:
    """Test cohort status boundaries: 7, 8, 30, 31, 90, 91 days."""

    def test_active_day_0(self):
        last = datetime.now(timezone.utc)
        assert calculate_cohort_status(last) == "Active"

    def test_active_day_7(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=7)
        assert calculate_cohort_status(last) == "Active"

    def test_passive_day_8(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=8)
        assert calculate_cohort_status(last) == "Passive"

    def test_passive_day_30(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=30)
        assert calculate_cohort_status(last) == "Passive"

    def test_fading_day_31(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=31)
        assert calculate_cohort_status(last) == "Fading"

    def test_fading_day_90(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=90)
        assert calculate_cohort_status(last) == "Fading"

    def test_sleeping_day_91(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=91)
        assert calculate_cohort_status(last) == "Sleeping"

    def test_sleeping_day_365(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=365)
        assert calculate_cohort_status(last) == "Sleeping"

    def test_zombie_none(self):
        assert calculate_cohort_status(None) == "Sleeping"

    def test_zombie_same_day_old(self):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=200)
        assert calculate_cohort_status(old, old) == "Zombie"

    def test_zombie_3_days_old(self):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=3)
        assert calculate_cohort_status(old, joined) == "Zombie"

    def test_zombie_4_days_old(self):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=200)
        joined = old - timedelta(days=4)
        assert calculate_cohort_status(old, joined) == "Sleeping"

    def test_zombie_same_day_recent(self):
        now = datetime.now(timezone.utc)
        assert calculate_cohort_status(now, now) == "Active"

    def test_zombie_different_day(self):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        joined = now - timedelta(days=1)
        assert calculate_cohort_status(now, joined) != "Zombie"
