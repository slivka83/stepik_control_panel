import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import text

from app.models import (
    Course,
    FinancialSnapshot,
    User,
)
from app.services.sync import (
    SYNC_COOLDOWN_SECONDS,
    can_sync,
    sync_all,
    sync_community_stats,
    sync_financials,
)


def _make_user(session, user_id=None, token="test_token_123"):
    from app.services.crypto import encrypt_token

    user = User(
        id=user_id or uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token(token),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
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
    )
    session.add(course)
    return course


# ─── sync_community_stats tests ─────────────────────────────────────────


class TestSyncCommunityStats:
    async def test_no_users_skips(self, db_session):
        await sync_community_stats()

    async def test_reviews_written_to_snapshot(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1000)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(UTC),
        )
        db_session.add(snapshot)
        await db_session.flush()

        with (
            patch("app.services.raw_sync.sync_community", new_callable=AsyncMock),
            patch("app.services.transform.transform_community", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_community_stats()

    async def test_community_stage_rebuilds_student_mart(self, db_session):
        """Витрина студентов пересобирается в конце синка (этап сообщества)."""
        from app.models import Course, StudentEnrollment

        user = _make_user(db_session)
        course = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=1000, title="Python", status="Published")
        db_session.add(course)
        await db_session.flush()
        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=course.id,
                student_id=7,
                last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                cohort_status="Active",
            )
        )
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_community", new_callable=AsyncMock),
            patch("app.services.transform.transform_community", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_community_stats()

        r = await db_session.execute(text("SELECT student_id, courses_count FROM student_marts"))
        row = r.fetchone()
        assert row is not None
        assert row[0] == 7
        assert row[1] == 1

    async def test_comments_per_page(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1100)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(UTC),
        )
        db_session.add(snapshot)
        await db_session.flush()

        with (
            patch("app.services.raw_sync.sync_community", new_callable=AsyncMock),
            patch("app.services.transform.transform_community", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_community_stats()

    async def test_comments_monthly_aggregation(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1200)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(UTC),
        )
        db_session.add(snapshot)
        await db_session.flush()

        with (
            patch("app.services.raw_sync.sync_community", new_callable=AsyncMock),
            patch("app.services.transform.transform_community", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_community_stats()

    async def test_multiple_courses_comments(self, db_session):
        user = _make_user(db_session)
        course1 = _make_course(db_session, user.id, stepik_course_id=1300)
        course2 = _make_course(db_session, user.id, stepik_course_id=1400)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(UTC),
        )
        db_session.add(snapshot)
        await db_session.flush()

        with (
            patch("app.services.raw_sync.sync_community", new_callable=AsyncMock),
            patch("app.services.transform.transform_community", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_community_stats()

    async def test_empty_snapshot_creates_community(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1500)

        with (
            patch("app.services.raw_sync.sync_community", new_callable=AsyncMock),
            patch("app.services.transform.transform_community", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_community_stats()


# ─── sync_financials tests ──────────────────────────────────────────────


class TestSyncFinancials:
    async def test_basic_sync(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2000)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_financials()

    async def test_promo_code_aggregation(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2100)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_financials()

    async def test_refund_in_course_stats(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2200)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_financials()

    async def test_replaces_existing_snapshot(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2300)
        await db_session.commit()

        old_snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {"total_turnover": 999}},
            updated_at=datetime.now(UTC),
        )
        db_session.add(old_snapshot)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_financials()

    async def test_sync_financials_pipeline_runs(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2400)
        await db_session.commit()

        with (
            patch("app.services.raw_sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.transform.transform_financials", new_callable=AsyncMock),
            patch("app.services.sync._get_user_token", return_value="token"),
        ):
            await sync_financials()


# ─── sync_all orchestration tests ───────────────────────────────────────


class TestSyncAll:
    async def test_full_sync_success(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=3000)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(UTC),
        )
        db_session.add(snapshot)
        await db_session.commit()

        with (
            patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock),
            patch("app.services.sync.sync_submissions", new_callable=AsyncMock),
            patch("app.services.sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.sync.sync_community_stats", new_callable=AsyncMock),
        ):
            result = await sync_all(force=True)

        assert result["status"] == "ok"

    async def test_sync_all_skip_cooldown(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = time.time()

        result = await sync_all(force=False)
        assert result["status"] == "skipped"
        assert result["reason"] == "cooldown"

    async def test_sync_all_force_bypasses_cooldown(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = time.time()

        with (
            patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock),
            patch("app.services.sync.sync_submissions", new_callable=AsyncMock),
            patch("app.services.sync.sync_financials", new_callable=AsyncMock),
            patch("app.services.sync.sync_community_stats", new_callable=AsyncMock),
        ):
            result = await sync_all(force=True)

        assert result["status"] == "ok"

    async def test_sync_all_exception_returns_error(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0

        with patch(
            "app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock, side_effect=Exception("DB error")
        ):
            result = await sync_all(force=True)

        assert result["status"] == "error"
        assert "DB error" in result["detail"]

    async def test_sync_all_resets_progress_on_error(self):
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


# ─── can_sync tests ─────────────────────────────────────────────────────


class TestCanSync:
    def test_can_sync_initial(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0
        assert can_sync() is True

    def test_can_sync_after_cooldown(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = time.time() - SYNC_COOLDOWN_SECONDS - 1
        assert can_sync() is True

    def test_cannot_sync_during_cooldown(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = time.time()
        assert can_sync() is False

    def test_cannot_sync_when_in_progress(self):
        import app.services.sync as sync_mod

        sync_mod._sync_in_progress = True
        sync_mod._last_sync_completed_at = 0
        assert can_sync() is False
        sync_mod._sync_in_progress = False
