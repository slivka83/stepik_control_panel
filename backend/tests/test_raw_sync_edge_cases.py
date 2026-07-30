"""Edge case tests for raw_sync and transform services."""
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

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


# ─── paginated_fetch edge cases ────────────────────────────────────────


class TestPaginatedFetch:
    @pytest.mark.asyncio
    async def test_stops_when_empty(self, db_session):
        from app.services.raw_sync import _paginated_fetch
        async def empty_page(*args, **kwargs):
            return {"courses": [], "meta": {"has_next": False}}
        with patch("app.services.raw_sync._request", side_effect=empty_page):
            result = await _paginated_fetch("/courses", "tok", "courses")
            assert result == []

    @pytest.mark.asyncio
    async def test_handles_missing_meta(self, db_session):
        from app.services.raw_sync import _paginated_fetch
        empty = {"courses": []}
        with patch("app.services.raw_sync._request", return_value=empty):
            result = await _paginated_fetch("/courses", "tok", "courses")
            assert result == []


# ─── Transform: empty raw tables ──────────────────────────────────────

class TestTransformEdgeCases:
    @pytest.mark.asyncio
    async def test_courses_no_user_skips(self, db_session):
        from app.services.transform import transform_courses
        await transform_courses(db_session)

    @pytest.mark.asyncio
    async def test_courses_no_users_table_skips(self, db_session):
        from app.services.transform import transform_courses
        await transform_courses(db_session)

    @pytest.mark.asyncio
    async def test_enrollments_no_courses_skips(self, db_session):
        from app.services.transform import transform_enrollments
        await transform_enrollments(db_session)

    @pytest.mark.asyncio
    async def test_submissions_no_steps_skips(self, db_session):
        from app.services.transform import transform_submissions
        r = await db_session.execute(text("SELECT COUNT(*) FROM submissions"))
        before = r.scalar()
        await transform_submissions(db_session)
        r = await db_session.execute(text("SELECT COUNT(*) FROM submissions"))
        assert r.scalar() == before

    @pytest.mark.asyncio
    async def test_financials_only_user_no_courses_creates_empty(self, db_session):
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

    @pytest.mark.asyncio
    async def test_community_no_snapshot_creates_new(self, db_session):
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
        assert "community" in data
        assert data["community"]["total_comments"] == 0

    @pytest.mark.asyncio
    async def test_community_skips_no_courses(self, db_session):
        from app.services.transform import transform_community
        await transform_community(db_session)


# ─── Raw sync: API errors ─────────────────────────────────────────────

class TestRawSyncErrors:
    @pytest.mark.asyncio
    async def test_courses_api_empty_does_not_crash(self, db_session):
        from app.services.raw_sync import sync_courses_structure
        _make_user(db_session)
        await db_session.commit()
        def empty(*args, **kwargs):
            return {"courses": [], "meta": {"has_next": False}}
        with patch("app.services.raw_sync._request", side_effect=empty), \
             patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.stepik_user_id = 12345
            await sync_courses_structure(db_session, "tok")

    @pytest.mark.asyncio
    async def test_grades_and_certs_empty_courses(self, db_session):
        from app.services.raw_sync import sync_course_grades_and_certs
        await sync_course_grades_and_certs(db_session, "tok", [])

    @pytest.mark.asyncio
    async def test_grades_and_certs_unknown_course(self, db_session):
        from app.services.raw_sync import sync_course_grades_and_certs
        await sync_course_grades_and_certs(db_session, "tok", [99999])
