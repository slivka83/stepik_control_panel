import uuid
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy import select, text

from app.models import (
    User, Course, StudentEnrollment, Submission,
    FinancialSnapshot, StepSyncState,
)
from app.services.sync import (
    _paginated_get,
    sync_submissions,
    sync_community_stats,
    sync_financials,
    sync_all,
    can_sync,
    calculate_cohort_status,
    SYNC_COOLDOWN_SECONDS,
)


# ─── Helpers ────────────────────────────────────────────────────────────

def _make_user(session, user_id=None, token="test_token_123"):
    from app.services.crypto import encrypt_token
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


async def _flush(session):
    await session.flush()
    return session


async def _get_snapshot(session):
    result = await session.execute(select(FinancialSnapshot).limit(1))
    return result.scalar_one_or_none()


# ─── _paginated_get tests ───────────────────────────────────────────────

class TestPaginatedGet:
    async def test_single_page(self):
        mock_data = {
            "courses": [{"id": 1}, {"id": 2}],
            "meta": {"has_next": False}
        }
        with patch("app.services.sync._request", new_callable=AsyncMock, return_value=mock_data):
            result = await _paginated_get("/courses", "token", key="courses")
            assert len(result) == 2

    async def test_multiple_pages(self):
        page1 = {"courses": [{"id": 1}], "meta": {"has_next": True}}
        page2 = {"courses": [{"id": 2}], "meta": {"has_next": False}}
        with patch("app.services.sync._request", new_callable=AsyncMock, side_effect=[page1, page2]):
            result = await _paginated_get("/courses", "token", key="courses")
            assert len(result) == 2

    async def test_empty_page_stops(self):
        mock_data = {"courses": [], "meta": {"has_next": True}}
        with patch("app.services.sync._request", new_callable=AsyncMock, return_value=mock_data):
            result = await _paginated_get("/courses", "token", key="courses")
            assert len(result) == 0

    async def test_max_pages_limit(self):
        mock_data = {"courses": [{"id": 1}], "meta": {"has_next": True}}
        with patch("app.services.sync._request", new_callable=AsyncMock, return_value=mock_data):
            result = await _paginated_get("/courses", "token", key="courses", max_pages=3)
            assert len(result) == 3

    async def test_on_page_callback(self):
        page1 = {"courses": [{"id": 1}], "meta": {"has_next": True}}
        page2 = {"courses": [{"id": 2}], "meta": {"has_next": False}}
        callback = MagicMock()
        with patch("app.services.sync._request", new_callable=AsyncMock, side_effect=[page1, page2]):
            await _paginated_get("/courses", "token", key="courses", on_page=callback)
            assert callback.call_count == 2
            callback.assert_any_call(1, 1)
            callback.assert_any_call(2, 1)

    async def test_default_key_from_path(self):
        mock_data = {"submissions": [{"id": 1}], "meta": {"has_next": False}}
        with patch("app.services.sync._request", new_callable=AsyncMock, return_value=mock_data):
            result = await _paginated_get("/submissions", "token")
            assert len(result) == 1

    async def test_params_passed_through(self):
        mock_data = {"courses": [], "meta": {"has_next": False}}
        with patch("app.services.sync._request", new_callable=AsyncMock, return_value=mock_data) as mock_req:
            await _paginated_get("/courses", "token", params={"teacher": 123}, key="courses")
            call_args = mock_req.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "/courses"
            assert call_args[0][3]["teacher"] == 123
            assert call_args[0][3]["page"] == 1
            assert call_args[0][3]["page_size"] == 500


# ─── sync_submissions tests ─────────────────────────────────────────────

class TestSyncSubmissions:
    """sync_submissions uses raw SQL with UUID parameters (ON CONFLICT DO UPDATE).
    SQLite doesn't support UUID binding — these tests require PostgreSQL.
    We test the logic via integration tests in CI with a real PG database.
    """

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_code_steps_only(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_upsert_by_stepik_submission_id(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_upsert_updates_existing(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_is_author_marking(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_step_sync_state_saved(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_incremental_sync_uses_last_page(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_external_grader_step_included(self, db_session):
        pass

    @pytest.mark.skip(reason="Raw SQL UUID binding not supported in SQLite")
    async def test_choice_step_included(self, db_session):
        pass


# ─── sync_community_stats tests ─────────────────────────────────────────

class _AsyncSessionCtx:
    """Mock async context manager that replaces async_session and yields a real DB session."""
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, *args):
        pass


class TestSyncCommunityStats:
    async def test_no_users_skips(self, db_session):
        await sync_community_stats()

    async def test_reviews_written_to_snapshot(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1000)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        courses_api = [{"id": 1000, "review_summary": 42}]
        review_summaries = [{"average": 4.5, "count": 100}]

        with patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=courses_api), \
             patch("app.services.sync._request", new_callable=AsyncMock) as mock_req, \
             patch("app.services.sync.async_session", lambda: _AsyncSessionCtx(db_session)):
            mock_req.side_effect = [
                {"course-review-summaries": review_summaries},
                {"comments": [], "meta": {"has_next": False}},
            ]
            await sync_community_stats()

        snapshot2 = await _get_snapshot(db_session)
        community = snapshot2.data.get("community", {})
        assert community["total_reviews"] == 100
        assert community["average_rating"] == 4.5

    async def test_comments_per_page(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1100)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        courses_api = [{"id": 1100, "review_summary": None}]

        comment_page1 = {
            "comments": [
                {"update_date": "2026-07-15T10:00:00Z"},
                {"update_date": "2026-07-16T10:00:00Z"},
            ],
            "meta": {"has_next": True},
        }
        comment_page2 = {
            "comments": [{"update_date": "2026-07-20T10:00:00Z"}],
            "meta": {"has_next": False},
        }

        with patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=courses_api), \
             patch("app.services.sync._request", new_callable=AsyncMock) as mock_req, \
             patch("app.services.sync.async_session", lambda: _AsyncSessionCtx(db_session)):
            mock_req.side_effect = [
                comment_page1,
                comment_page2,
            ]
            await sync_community_stats()

        snapshot2 = await _get_snapshot(db_session)
        community = snapshot2.data.get("community", {})
        assert community["total_comments"] == 3
        assert community["comments_monthly"]["2026-07"] == 3

    async def test_comments_monthly_aggregation(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1200)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        courses_api = [{"id": 1200, "review_summary": None}]
        comment_page = {
            "comments": [
                {"update_date": "2026-06-01T10:00:00Z"},
                {"update_date": "2026-06-15T10:00:00Z"},
                {"update_date": "2026-07-01T10:00:00Z"},
            ],
            "meta": {"has_next": False},
        }

        with patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=courses_api), \
             patch("app.services.sync._request", new_callable=AsyncMock) as mock_req, \
             patch("app.services.sync.async_session", lambda: _AsyncSessionCtx(db_session)):
            mock_req.side_effect = [
                comment_page,
            ]
            await sync_community_stats()

        snapshot2 = await _get_snapshot(db_session)
        community = snapshot2.data.get("community", {})
        assert community["comments_monthly"]["2026-06"] == 2
        assert community["comments_monthly"]["2026-07"] == 1

    async def test_multiple_courses_comments(self, db_session):
        user = _make_user(db_session)
        course1 = _make_course(db_session, user.id, stepik_course_id=1300)
        course2 = _make_course(db_session, user.id, stepik_course_id=1400)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        courses_api = [
            {"id": 1300, "review_summary": None},
            {"id": 1400, "review_summary": None},
        ]

        comments1 = {
            "comments": [{"update_date": "2026-07-10T10:00:00Z"}],
            "meta": {"has_next": False},
        }
        comments2 = {
            "comments": [
                {"update_date": "2026-07-11T10:00:00Z"},
                {"update_date": "2026-07-12T10:00:00Z"},
            ],
            "meta": {"has_next": False},
        }

        with patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=courses_api), \
             patch("app.services.sync._request", new_callable=AsyncMock) as mock_req, \
             patch("app.services.sync.async_session", lambda: _AsyncSessionCtx(db_session)):
            mock_req.side_effect = [
                comments1,
                comments2,
            ]
            await sync_community_stats()

        snapshot2 = await _get_snapshot(db_session)
        community = snapshot2.data.get("community", {})
        assert community["total_comments"] == 3
        assert community["comments_monthly"]["2026-07"] == 3

    async def test_empty_snapshot_creates_community(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1500)

        courses_api = [{"id": 1500, "review_summary": None}]

        with patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=courses_api), \
             patch("app.services.sync._request", new_callable=AsyncMock) as mock_req, \
             patch("app.services.sync.async_session", lambda: _AsyncSessionCtx(db_session)):
            mock_req.side_effect = [
                {"course-review-summaries": []},
                {"comments": [], "meta": {"has_next": False}},
            ]
            await sync_community_stats()

    async def test_review_error_handled_gracefully(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=1600)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.commit()

        courses_api = [{"id": 1600, "review_summary": 99}]

        with patch("app.services.sync._paginated_get", new_callable=AsyncMock, return_value=courses_api), \
             patch("app.services.sync._request", new_callable=AsyncMock) as mock_req, \
             patch("app.services.sync.async_session", lambda: _AsyncSessionCtx(db_session)):
            mock_req.side_effect = [
                Exception("API error"),
                {"comments": [], "meta": {"has_next": False}},
            ]
            await sync_community_stats()

        snapshot2 = await _get_snapshot(db_session)
        community = snapshot2.data.get("community", {})
        assert community.get("total_reviews", 0) == 0


# ─── sync_financials tests ──────────────────────────────────────────────

class TestSyncFinancials:
    async def test_basic_sync(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2000)
        await db_session.commit()

        now = datetime.now(timezone.utc)
        by_months = [
            {"year": now.year, "month": now.month, "total_turnover": 10000,
             "total_user_income": 8000, "total_refunds": 500, "count_payments": 10, "count_refunds": 1},
            {"year": 2025, "month": 12, "total_turnover": 5000,
             "total_user_income": 4000, "total_refunds": 200, "count_payments": 5, "count_refunds": 0},
        ]
        benefits = [
            {"id": 1, "course": 2000, "amount": 1000, "payment_amount": 1200,
             "status": "completed", "time": "2026-07-01T10:00:00Z", "buyer": 100, "promo_code": None},
            {"id": 2, "course": 2000, "amount": -200, "payment_amount": 1200,
             "status": "refunded", "time": "2026-07-05T10:00:00Z", "buyer": 101, "promo_code": None},
        ]

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="finance_token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [by_months, benefits]
            await sync_financials()

        snapshot = await _get_snapshot(db_session)
        data = snapshot.data
        assert data["summary"]["total_turnover"] == 15000
        assert data["summary"]["total_income"] == 12000
        assert data["summary"]["total_payments"] == 15
        assert data["summary"]["net_income"] == 11300
        assert len(data["months"]) == 2
        assert len(data["courses"]) == 1
        assert len(data["recent_payments"]) == 2

    async def test_promo_code_aggregation(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2100)
        await db_session.commit()

        by_months = []
        benefits = [
            {"id": 1, "course": 2100, "amount": 500, "payment_amount": 600,
             "status": "completed", "time": "2026-07-01T10:00:00Z", "promo_code": "SAVE20"},
            {"id": 2, "course": 2100, "amount": 300, "payment_amount": 400,
             "status": "completed", "time": "2026-07-05T10:00:00Z", "promo_code": "SAVE20"},
            {"id": 3, "course": 2100, "amount": 700, "payment_amount": 800,
             "status": "completed", "time": "2026-07-10T10:00:00Z", "promo_code": "DISCOUNT50"},
        ]

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="finance_token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [by_months, benefits]
            await sync_financials()

        snapshot = await _get_snapshot(db_session)
        promos = snapshot.data["promos"]
        assert len(promos) == 2
        promo_map = {p["promo_code"]: p for p in promos}
        assert promo_map["SAVE20"]["payments"] == 2
        assert promo_map["SAVE20"]["income"] == 800
        assert promo_map["DISCOUNT50"]["payments"] == 1
        assert promo_map["DISCOUNT50"]["last_used"] == "2026-07-10T10:00:00Z"

    async def test_refund_in_course_stats(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2200)
        await db_session.commit()

        by_months = []
        benefits = [
            {"id": 1, "course": 2200, "amount": 1000, "payment_amount": 1200,
             "status": "completed", "time": "2026-07-01T10:00:00Z", "promo_code": None},
            {"id": 2, "course": 2200, "amount": -500, "payment_amount": 1200,
             "status": "refunded", "time": "2026-07-05T10:00:00Z", "promo_code": None},
        ]

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="finance_token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [by_months, benefits]
            await sync_financials()

        snapshot = await _get_snapshot(db_session)
        courses = snapshot.data["courses"]
        assert len(courses) == 1
        assert courses[0]["turnover"] == 0  # 1200 - 1200
        assert courses[0]["income"] == 1000
        assert courses[0]["refunds"] == -500

    async def test_replaces_existing_snapshot(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2300)
        await db_session.commit()

        old_snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {"total_turnover": 999}},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(old_snapshot)
        await db_session.commit()

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="finance_token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [[], []]
            await sync_financials()

        result = await db_session.execute(select(FinancialSnapshot))
        snapshots = result.scalars().all()
        assert len(snapshots) == 1
        assert snapshots[0].data["summary"]["total_turnover"] == 0

    async def test_recent_payments_limited_to_30(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=2400)
        await db_session.commit()

        by_months = []
        benefits = [
            {"id": i, "course": 2400, "amount": 100, "payment_amount": 120,
             "status": "completed", "time": f"2026-07-{i:02d}T10:00:00Z", "promo_code": None}
            for i in range(1, 40)
        ]

        with patch("app.services.sync.get_finance_token", new_callable=AsyncMock, return_value="finance_token"), \
             patch("app.services.sync._paginated_get", new_callable=AsyncMock) as mock_pg:
            mock_pg.side_effect = [by_months, benefits]
            await sync_financials()

        snapshot = await _get_snapshot(db_session)
        assert len(snapshot.data["recent_payments"]) == 30


# ─── sync_all orchestration tests ───────────────────────────────────────

class TestSyncAll:
    async def test_full_sync_success(self, db_session):
        user = _make_user(db_session)
        course = _make_course(db_session, user.id, stepik_course_id=3000)
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.commit()

        with patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock), \
             patch("app.services.sync.sync_submissions", new_callable=AsyncMock), \
             patch("app.services.sync.sync_financials", new_callable=AsyncMock), \
             patch("app.services.sync.sync_community_stats", new_callable=AsyncMock):
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

        with patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock), \
             patch("app.services.sync.sync_submissions", new_callable=AsyncMock), \
             patch("app.services.sync.sync_financials", new_callable=AsyncMock), \
             patch("app.services.sync.sync_community_stats", new_callable=AsyncMock):
            result = await sync_all(force=True)

        assert result["status"] == "ok"

    async def test_sync_all_exception_returns_error(self):
        import app.services.sync as sync_mod
        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0

        with patch("app.services.sync.sync_courses_and_enrollments", new_callable=AsyncMock, side_effect=Exception("DB error")):
            result = await sync_all(force=True)

        assert result["status"] == "error"
        assert "DB error" in result["detail"]

    async def test_sync_all_resets_progress_on_error(self):
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
