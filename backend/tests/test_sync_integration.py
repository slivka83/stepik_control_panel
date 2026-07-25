"""Integration tests for sync flow: fetch from API → replace in DB."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models import User, Course, StudentEnrollment, Submission
from app.services.sync import sync_courses_and_enrollments, sync_submissions, calculate_cohort_status


@pytest.mark.asyncio
async def test_full_sync_flow(db_session):
    """Test complete sync flow: mock API → verify DB."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()

    mock_courses = [
        {"id": 100, "title": "Course A", "is_published": True},
        {"id": 200, "title": "Course B", "is_published": False},
    ]
    mock_grades = [
        {"user": 1001, "score": 50, "last_viewed": 1700000000},
        {"user": 1002, "score": 0, "last_viewed": None},
    ]
    mock_certs = [{"user": 1001}]

    async def fake_paginated_get(path, token, params=None, key=None):
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
                mock_settings.return_value.stepik_user_id = 123
                await sync_courses_and_enrollments(user_id=user.id)

    courses = (await db_session.execute(__import__("sqlalchemy").select(Course))).scalars().all()
    assert len(courses) == 2
    titles = {c.title for c in courses}
    assert titles == {"Course A", "Course B"}

    enrollments = (await db_session.execute(__import__("sqlalchemy").select(StudentEnrollment))).scalars().all()
    assert len(enrollments) == 2
    assert any(e.points_earned == 50 for e in enrollments)
    assert any(e.certificate_issued is True for e in enrollments)


@pytest.mark.asyncio
async def test_sync_preserves_data_on_api_failure(db_session):
    """If API fails, existing DB data should be preserved."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()

    course = Course(user_id=user.id, stepik_course_id=999, title="Existing Course")
    db_session.add(course)
    await db_session.commit()

    async def failing_paginated_get(*args, **kwargs):
        raise Exception("API is down")

    with patch("app.services.sync._paginated_get", side_effect=failing_paginated_get):
        with patch("app.services.sync.decrypt_token", return_value="raw_token"):
            with patch("app.config.get_settings") as mock_settings:
                mock_settings.return_value.stepik_user_id = 123
                try:
                    await sync_courses_and_enrollments(user_id=user.id)
                except Exception:
                    pass

    courses = (await db_session.execute(__import__("sqlalchemy").select(Course))).scalars().all()
    assert len(courses) == 1
    assert courses[0].title == "Existing Course"


@pytest.mark.asyncio
async def test_sync_empty_response_new_user(db_session):
    """Sync with empty API response should not crash."""
    user = User(
        stepik_id=123,
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()

    async def empty_paginated_get(*args, **kwargs):
        return []

    with patch("app.services.sync._paginated_get", side_effect=empty_paginated_get):
        with patch("app.services.sync.decrypt_token", return_value="raw_token"):
            with patch("app.config.get_settings") as mock_settings:
                mock_settings.return_value.stepik_user_id = 123
                await sync_courses_and_enrollments(user_id=user.id)

    courses = (await db_session.execute(__import__("sqlalchemy").select(Course))).scalars().all()
    assert len(courses) == 0


class TestCohortBoundaries:
    """Test cohort status boundaries: 7, 8, 30, 31, 90, 91 days."""

    def test_active_day_0(self):
        from datetime import timedelta
        last = datetime.now(timezone.utc) - timedelta(days=0)
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
