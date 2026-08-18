import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.api.dashboard import kpi as kpi_module
from app.database import get_db
from app.main import app
from app.models import (
    Course,
    FinancialSnapshot,
    MartCertificate,
    MartReview,
    MartStep,
    StudentEnrollment,
    User,
)
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


async def _seed_user(session):
    user = User(
        id=uuid.uuid4(),
        stepik_id=64381531,
        access_token=encrypt_token("test_access"),
        refresh_token=encrypt_token("test_refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    session.add(user)
    await session.flush()
    return user


async def _owned_course(session, user, stepik_id=100):
    course = Course(
        id=uuid.uuid4(),
        user_id=user.id,
        stepik_course_id=stepik_id,
        title="Python",
        status="Published",
    )
    session.add(course)
    await session.flush()
    return course


class TestKpiEdgeCases:
    async def test_january_prev_month_is_december(self, db_session):
        # Regression: in January, prev month must roll back to December of the
        # previous year, not month 0.
        user = await _seed_user(db_session)
        course = await _owned_course(db_session, user, 100)
        db_session.add(
            MartReview(
                id=uuid.uuid4(),
                course_id=course.id,
                stepik_course_id=100,
                review_id=1,
                year=2025,
                month=12,
                score=4.5,
            )
        )
        db_session.add(
            MartReview(
                id=uuid.uuid4(),
                course_id=course.id,
                stepik_course_id=100,
                review_id=2,
                year=2026,
                month=1,
                score=4.0,
            )
        )
        db_session.add(
            MartCertificate(
                id=uuid.uuid4(),
                course_id=course.id,
                stepik_course_id=100,
                certificate_id=1,
                year=2025,
                month=12,
                type="regular",
            )
        )
        db_session.add(
            MartCertificate(
                id=uuid.uuid4(),
                course_id=course.id,
                stepik_course_id=100,
                certificate_id=2,
                year=2026,
                month=1,
                type="regular",
            )
        )
        await db_session.commit()

        fixed = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

        class _FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            with patch.object(kpi_module, "datetime", _FixedDateTime):
                response = client.get("/api/dashboard/kpi")
            assert response.status_code == 200
            data = response.json()
            # December (prev year) is treated as the previous month → change 0%.
            assert data["reviews_current_month"] == 1
            assert data["reviews_change_pct"] == 0
            assert data["certificates_current_month"] == 1
            assert data["certificates_change_pct"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_prev_zero_cur_positive_trend_is_none(self, db_session):
        # Regression: when previous month value is 0 but current is positive,
        # the trend percentage must be None (no misleading "infinite growth").
        user = await _seed_user(db_session)
        await _owned_course(db_session, user, 100)
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {
                        "current_month_income": 50000,
                        "total_income": 50000,
                        "total_turnover": 60000,
                        "total_refunds": 0,
                        "total_payments": 10,
                    },
                    "months": [
                        {
                            "month": "Декабрь 2025",
                            "year": 2025,
                            "month_num": 12,
                            "income": 0,
                            "turnover": 0,
                            "refunds": 0,
                            "payments_count": 0,
                            "refunds_count": 0,
                        },
                        {
                            "month": "Январь 2026",
                            "year": 2026,
                            "month_num": 1,
                            "income": 50000,
                            "turnover": 60000,
                            "refunds": 0,
                            "payments_count": 10,
                            "refunds_count": 0,
                        },
                    ],
                    "courses": [],
                    "recent_payments": [],
                },
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/kpi")
            assert response.status_code == 200
            data = response.json()
            assert data["revenue_change_pct"] is None
            assert data["revenue_change_detail"] is None
            assert data["payments_change_pct"] is None
        finally:
            app.dependency_overrides.clear()

    async def test_prev_months_clamped_when_no_current_activity(self, db_session):
        # Without current-month activity, prev_months == total (max(0, ...) holds).
        user = await _seed_user(db_session)
        course = await _owned_course(db_session, user, 100)
        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=course.id,
                student_id=1,
                last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                date_joined=(datetime.now(UTC) - timedelta(days=60)).replace(tzinfo=None),
                certificate_issued=False,
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/kpi")
            assert response.status_code == 200
            data = response.json()
            assert data["total_students"] == 1
            assert data["students_prev_months"] == 1
            assert data["certificates_issued"] == 0
            assert data["certificates_prev_months"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_steps_average_grade_zero_when_no_votes(self, db_session):
        # A step with grade but zero votes must not skew the average → 0.0.
        user = await _seed_user(db_session)
        course = await _owned_course(db_session, user, 100)
        db_session.add(
            MartStep(
                id=uuid.uuid4(),
                course_id=course.id,
                stepik_course_id=100,
                step_id=1,
                grade=4.0,
                grade_votes=0,
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/kpi")
            assert response.status_code == 200
            assert response.json()["steps_average_grade"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_average_rating_zero_when_missing(self, db_session):
        user = await _seed_user(db_session)
        await _owned_course(db_session, user, 100)
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {},
                    "months": [],
                    "courses": [],
                    "recent_payments": [],
                    "community": {"total_comments": 5},
                },
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/kpi")
            assert response.status_code == 200
            assert response.json()["average_rating"] == 0
        finally:
            app.dependency_overrides.clear()
