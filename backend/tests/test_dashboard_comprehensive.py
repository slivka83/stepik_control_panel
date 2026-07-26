import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, Course, StudentEnrollment, Submission, FinancialSnapshot
from app.api.auth import get_user
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


def _make_user_in_db(session, user_id=None, stepik_id=12345):
    user = User(
        id=user_id or uuid.uuid4(),
        stepik_id=stepik_id,
        access_token=encrypt_token("test_token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(user)
    return user


def _make_course_in_db(session, user_id, stepik_course_id=100, title="Test Course", status="Published"):
    course = Course(
        id=uuid.uuid4(),
        user_id=user_id,
        stepik_course_id=stepik_course_id,
        title=title,
        status=status,
        health_score=100.0,
    )
    session.add(course)
    return course


def _setup_overrides(db_session, user):
    async def override_db():
        yield db_session
    async def override_user():
        return user
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


# ─── Submissions endpoint tests ─────────────────────────────────────────

class TestDashboardSubmissions:
    async def test_returns_months(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        sub = Submission(
            id=uuid.uuid4(),
            stepik_submission_id=10001,
            stepik_step_id=1001,
            course_id=course.id,
            status="correct",
            score=1.0,
            submission_time=now,
            is_author=False,
        )
        db_session.add(sub)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/submissions")
            assert response.status_code == 200
            data = response.json()
            assert len(data["months"]) == 1
            assert data["months"][0]["total"] == 1
            assert data["months"][0]["correct"] == 1
        finally:
            app.dependency_overrides.clear()

    async def test_filters_author_submissions(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        sub_author = Submission(
            id=uuid.uuid4(),
            stepik_submission_id=10002,
            stepik_step_id=1001,
            course_id=course.id,
            status="correct",
            score=1.0,
            submission_time=now,
            is_author=True,
        )
        sub_student = Submission(
            id=uuid.uuid4(),
            stepik_submission_id=10003,
            stepik_step_id=1001,
            course_id=course.id,
            status="correct",
            score=1.0,
            submission_time=now,
            is_author=False,
        )
        db_session.add_all([sub_author, sub_student])
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/submissions")
            assert response.status_code == 200
            data = response.json()
            assert len(data["months"]) == 1
            assert data["months"][0]["total"] == 1
        finally:
            app.dependency_overrides.clear()

    async def test_correct_vs_incorrect(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        sub_correct = Submission(
            id=uuid.uuid4(), stepik_submission_id=10004, stepik_step_id=1001,
            course_id=course.id, status="correct", score=1.0,
            submission_time=now, is_author=False,
        )
        sub_wrong = Submission(
            id=uuid.uuid4(), stepik_submission_id=10005, stepik_step_id=1001,
            course_id=course.id, status="wrong", score=0.0,
            submission_time=now, is_author=False,
        )
        db_session.add_all([sub_correct, sub_wrong])
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/submissions")
            data = response.json()
            assert data["months"][0]["total"] == 2
            assert data["months"][0]["correct"] == 1
        finally:
            app.dependency_overrides.clear()

    async def test_no_courses_returns_empty(self, db_session):
        user = _make_user_in_db(db_session)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/submissions")
            assert response.status_code == 200
            assert response.json()["months"] == []
        finally:
            app.dependency_overrides.clear()

    async def test_multiple_months_sorted(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        last_month = now - timedelta(days=30)

        sub1 = Submission(
            id=uuid.uuid4(), stepik_submission_id=10006, stepik_step_id=1001,
            course_id=course.id, status="correct", score=1.0,
            submission_time=last_month, is_author=False,
        )
        sub2 = Submission(
            id=uuid.uuid4(), stepik_submission_id=10007, stepik_step_id=1001,
            course_id=course.id, status="correct", score=1.0,
            submission_time=now, is_author=False,
        )
        db_session.add_all([sub1, sub2])
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/submissions")
            data = response.json()
            assert len(data["months"]) == 2
            assert data["months"][0]["total"] == 1
            assert data["months"][1]["total"] == 1
        finally:
            app.dependency_overrides.clear()


# ─── KPI trend tests ────────────────────────────────────────────────────

class TestDashboardKPITrends:
    async def test_revenue_change_pct(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)

        months_data = [
            {"month": "Июнь 2026", "income": 8000, "payments_count": 8, "refunds_count": 1},
            {"month": "Июль 2026", "income": 10000, "payments_count": 10, "refunds_count": 2},
        ]
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"current_month_income": 10000, "total_income": 18000,
                            "total_turnover": 20000, "total_refunds": 0, "total_payments": 18,
                            "net_income": 18000, "total_refunds_count": 3,
                            "current_month_turnover": 12000, "current_month_payments": 10},
                "months": months_data,
                "courses": [],
                "recent_payments": [],
            },
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["revenue_change_pct"] == 25
        finally:
            app.dependency_overrides.clear()

    async def test_payments_change_pct(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)

        months_data = [
            {"month": "Июнь 2026", "income": 8000, "payments_count": 5, "refunds_count": 1},
            {"month": "Июль 2026", "income": 10000, "payments_count": 10, "refunds_count": 2},
        ]
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"current_month_income": 10000, "total_income": 18000,
                            "total_turnover": 20000, "total_refunds": 0, "total_payments": 15,
                            "net_income": 18000, "total_refunds_count": 3,
                            "current_month_turnover": 12000, "current_month_payments": 10},
                "months": months_data,
                "courses": [],
                "recent_payments": [],
            },
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["payments_change_pct"] == 100
        finally:
            app.dependency_overrides.clear()

    async def test_revenue_change_zero_both(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)

        months_data = [
            {"month": "Июнь 2026", "income": 0, "payments_count": 0, "refunds_count": 0},
            {"month": "Июль 2026", "income": 0, "payments_count": 0, "refunds_count": 0},
        ]
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"current_month_income": 0, "total_income": 0,
                            "total_turnover": 0, "total_refunds": 0, "total_payments": 0,
                            "net_income": 0, "total_refunds_count": 0,
                            "current_month_turnover": 0, "current_month_payments": 0},
                "months": months_data,
                "courses": [],
                "recent_payments": [],
            },
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["revenue_change_pct"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_revenue_change_no_previous(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)

        months_data = [
            {"month": "Июль 2026", "income": 5000, "payments_count": 5, "refunds_count": 0},
        ]
        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"current_month_income": 5000, "total_income": 5000,
                            "total_turnover": 6000, "total_refunds": 0, "total_payments": 5,
                            "net_income": 5000, "total_refunds_count": 0,
                            "current_month_turnover": 6000, "current_month_payments": 5},
                "months": months_data,
                "courses": [],
                "recent_payments": [],
            },
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["revenue_change_pct"] is None
        finally:
            app.dependency_overrides.clear()

    async def test_submissions_change_pct(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        if now.month == 1:
            prev_year, prev_month = now.year - 1, 12
        else:
            prev_year, prev_month = now.year, now.month - 1

        for i in range(5):
            sub = Submission(
                id=uuid.uuid4(), stepik_submission_id=20000 + i, stepik_step_id=1001,
                course_id=course.id, status="correct", score=1.0,
                submission_time=datetime(prev_year, prev_month, 15, tzinfo=timezone.utc),
                is_author=False,
            )
            db_session.add(sub)

        for i in range(10):
            sub = Submission(
                id=uuid.uuid4(), stepik_submission_id=20010 + i, stepik_step_id=1001,
                course_id=course.id, status="correct", score=1.0,
                submission_time=datetime(now.year, now.month, 15, tzinfo=timezone.utc),
                is_author=False,
            )
            db_session.add(sub)

        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["current_month_submissions"] == 10
            assert data["submissions_change_pct"] == 100
        finally:
            app.dependency_overrides.clear()

    async def test_comments_change_pct(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)

        now = datetime.now(timezone.utc)
        cur_key = f"{now.year}-{now.month:02d}"
        if now.month == 1:
            prev_key = f"{now.year - 1}-12"
        else:
            prev_key = f"{now.year}-{now.month - 1:02d}"

        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"current_month_income": 0, "total_income": 0,
                            "total_turnover": 0, "total_refunds": 0, "total_payments": 0,
                            "net_income": 0, "total_refunds_count": 0,
                            "current_month_turnover": 0, "current_month_payments": 0},
                "months": [],
                "courses": [],
                "recent_payments": [],
                "community": {
                    "total_comments": 30,
                    "comments_monthly": {prev_key: 10, cur_key: 20},
                },
            },
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["current_month_comments"] == 20
            assert data["comments_change_pct"] == 100
        finally:
            app.dependency_overrides.clear()

    async def test_community_fields(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)

        snapshot = FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"current_month_income": 0, "total_income": 0,
                            "total_turnover": 0, "total_refunds": 0, "total_payments": 0,
                            "net_income": 0, "total_refunds_count": 0,
                            "current_month_turnover": 0, "current_month_payments": 0},
                "months": [],
                "courses": [],
                "recent_payments": [],
                "community": {
                    "total_comments": 150,
                    "total_reviews": 50,
                    "average_rating": 4.5,
                },
            },
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(snapshot)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["total_comments"] == 150
            assert data["total_reviews"] == 50
            assert data["average_rating"] == 4.5
        finally:
            app.dependency_overrides.clear()


# ─── Cohorts with Zombie tests ──────────────────────────────────────────

class TestDashboardCohortsZombie:
    async def test_zombie_counted_separately(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)

        zombie = StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id="z1",
            cohort_status="Zombie", points_earned=0, certificate_issued=False,
            last_viewed_at=now - timedelta(days=100),
            date_joined=now - timedelta(days=100),
        )
        sleeping = StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id="s1",
            cohort_status="Sleeping", points_earned=0, certificate_issued=False,
            last_viewed_at=now - timedelta(days=100),
            date_joined=now - timedelta(days=200),
        )
        active = StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id="a1",
            cohort_status="Active", points_earned=50, certificate_issued=False,
            last_viewed_at=now - timedelta(days=3),
        )

        db_session.add_all([zombie, sleeping, active])
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/cohorts")
            data = response.json()
            assert data["zombie"] == 1
            assert data["sleeping"] == 1
            assert data["active"] == 1
            assert data["passive"] == 0
            assert data["fading"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_zombie_excluded_from_sleeping(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        now = datetime.now(timezone.utc)

        zombie = StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id="z1",
            cohort_status="Zombie", points_earned=0, certificate_issued=False,
            last_viewed_at=now - timedelta(days=100),
            date_joined=now - timedelta(days=100),
        )
        sleeping = StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id="s1",
            cohort_status="Sleeping", points_earned=0, certificate_issued=False,
            last_viewed_at=now - timedelta(days=100),
            date_joined=now - timedelta(days=200),
        )

        db_session.add_all([zombie, sleeping])
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/cohorts")
            data = response.json()
            assert data["sleeping"] == 1
            assert data["zombie"] == 1
        finally:
            app.dependency_overrides.clear()


# ─── KPI with no snapshot ──────────────────────────────────────────────

class TestDashboardKPINoSnapshot:
    async def test_no_snapshot_returns_zeros(self, db_session):
        user = _make_user_in_db(db_session)
        course = _make_course_in_db(db_session, user.id)
        await db_session.flush()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/dashboard/kpi")
            data = response.json()
            assert data["total_comments"] == 0
            assert data["total_reviews"] == 0
            assert data["average_rating"] == 0
            assert data["revenue_change_pct"] is None
        finally:
            app.dependency_overrides.clear()
