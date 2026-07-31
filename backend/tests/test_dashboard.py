import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy import text
import json

from app.main import app
from app.database import Base, get_db, engine
from app.models import Course, StudentEnrollment, FinancialSnapshot, User
from app.api.auth import get_user
from app.services.crypto import encrypt_token


client = TestClient(app, raise_server_exceptions=False)


async def _seed_db(session):
    user = User(
        id=uuid.uuid4(),
        stepik_id=64381531,
        access_token=encrypt_token("test_access"),
        refresh_token=encrypt_token("test_refresh"),
        token_expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None),
    )
    session.add(user)
    await session.flush()
    return user


class TestDashboardKPI:
    async def test_kpi_returns_all_fields(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=100,
            title="Python", status="Published",
        )
        db_session.add(course)
        await db_session.flush()

        db_session.add(StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id=1,
            last_viewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            date_joined=datetime.now(timezone.utc).replace(tzinfo=None),
            points_earned=50, certificate_issued=False,
        ))
        db_session.add(StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id=2,
            last_viewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            date_joined=datetime.now(timezone.utc).replace(tzinfo=None),
            points_earned=100, certificate_issued=True,
        ))
        db_session.add(FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {
                "current_month_turnover": 40000, "current_month_income": 40000,
                "total_income": 150000,
                "net_income": 145000, "total_turnover": 200000,
                "total_refunds": 5000, "total_payments": 42,
            }, "months": [], "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
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
            assert data["courses_count"] == 1
            assert data["total_students"] == 2
            assert data["certificates_issued"] == 1
            assert data["total_revenue"] == 40000
        finally:
            app.dependency_overrides.clear()

    async def test_kpi_no_snapshot_returns_zeros(self, db_session):
        user = await _seed_db(db_session)

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
            assert data["total_revenue"] == 0
            assert data["total_students"] == 0
            assert data["courses_count"] == 0
        finally:
            app.dependency_overrides.clear()


class TestDashboardKPIMonthSplit:
    async def test_kpi_prev_months_and_current_month_split(self, db_session):
        """KPI: Студенты/Сертификаты/Комментарии/Отзывы = prev + current month."""
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=100,
            title="Python", status="Published",
        )
        db_session.add(course)
        await db_session.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        old = now.replace(year=now.year - 1, month=12)
        prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        prev_month_key = f"{prev_year}-{prev_month:02d}"

        db_session.add(StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id=1,
            last_viewed_at=old, date_joined=old,
            points_earned=50, certificate_issued=True,
        ))
        db_session.add(StudentEnrollment(
            id=uuid.uuid4(), course_id=course.id, student_id=2,
            last_viewed_at=now, date_joined=now,
            points_earned=100, certificate_issued=True,
        ))
        cur_month = f"{now.year}-{now.month:02d}"
        db_session.add(FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {
                "current_month_turnover": 40000, "current_month_income": 40000,
                "total_income": 150000,
                "net_income": 145000, "total_turnover": 200000,
                "total_refunds": 5000, "total_payments": 42,
            }, "months": [], "courses": [], "recent_payments": [],
            "community": {
                "total_comments": 5, "total_reviews": 3, "average_rating": 4.5,
                "total_solutions": 4,
                "comments_monthly": {cur_month: 2},
                "solutions_monthly": {cur_month: 1, prev_month_key: 2},
            }},
            updated_at=now,
        ))
        await db_session.execute(text("""
            INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json)
            VALUES ('c1', '1', '100', :j1)
        """), {"j1": json.dumps({"issue_date": cur_month + "-15T10:00:00Z"})})
        await db_session.execute(text("""
            INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json)
            VALUES ('c0', '9', '100', :j0)
        """), {"j0": json.dumps({"issue_date": prev_month_key + "-15T10:00:00Z"})})
        await db_session.execute(text("""
            INSERT INTO raw_course_review (review_id, course, _raw_json)
            VALUES ('r1', '100', :j2)
        """), {"j2": json.dumps({"create_date": cur_month + "-10T10:00:00Z"})})
        await db_session.execute(text("""
            INSERT INTO raw_course_review (review_id, course, _raw_json)
            VALUES ('r0', '100', :j3)
        """), {"j3": json.dumps({"create_date": prev_month_key + "-10T10:00:00Z"})})
        await db_session.execute(text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (500, 10, :j4)
        """), {"j4": json.dumps({"num_grades": [0, 0, 0, 2, 12]})})
        await db_session.execute(text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (501, 11, :j5)
        """), {"j5": json.dumps({"num_grades": [1, 1, 1, 1, 1]})})
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
            assert data["total_students"] == 2
            assert data["students_prev_months"] == 1
            assert data["current_month_students"] == 1
            assert data["certificates_issued"] == 2
            assert data["certificates_prev_months"] == 1
            assert data["certificates_current_month"] == 1
            assert data["certificates_change_pct"] == 0, "1 vs 1 → 0%"
            assert data["total_comments"] == 5
            assert data["comments_prev_months"] == 3
            assert data["current_month_comments"] == 2
            assert data["total_reviews"] == 3
            assert data["reviews_prev_months"] == 2
            assert data["reviews_current_month"] == 1
            assert data["reviews_change_pct"] == 0, "1 vs 1 → 0%"
            assert data["published_solutions_prev_months"] == 3, "4 - 1 (текущий месяц)"
            assert data["published_solutions_current_month"] == 1
            assert data["published_solutions_change_pct"] == -50, "1 vs 2 → -50%"
            expected_grade = (4 * 2 + 5 * 12 + 1 + 2 + 3 + 4 + 5) / 19
            assert data["steps_average_grade"] == round(expected_grade, 2), (
                "средняя оценка шагов из num_grades"
            )
        finally:
            app.dependency_overrides.clear()


class TestDashboardCohorts:
    async def test_cohorts_returns_all_statuses(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=100,
            title="Python", status="Published",
        )
        db_session.add(course)
        await db_session.flush()

        for sid, days in [(1, 3), (2, 15), (3, 50), (4, 100)]:
            db_session.add(StudentEnrollment(
                id=uuid.uuid4(), course_id=course.id, student_id=sid,
                last_viewed_at=(datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None),
                points_earned=50,
            ))
        await db_session.commit()

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/cohorts")
            assert response.status_code == 200
            data = response.json()
            assert data["active"] == 1
            assert data["passive"] == 1
            assert data["fading"] == 1
            assert data["sleeping"] == 1
        finally:
            app.dependency_overrides.clear()

    async def test_cohorts_no_courses(self, db_session):
        user = await _seed_db(db_session)

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/cohorts")
            assert response.status_code == 200
            assert response.json() == {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}
        finally:
            app.dependency_overrides.clear()


class TestDashboardRevenue:
    async def test_revenue_returns_months(self, db_session):
        user = await _seed_db(db_session)
        db_session.add(FinancialSnapshot(
            id=uuid.uuid4(),
            data={"summary": {}, "months": [{"month": "Январь 2026", "income": 50000}],
                  "courses": [], "recent_payments": []},
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        await db_session.commit()

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/revenue")
            assert response.status_code == 200
            months = response.json()["months"]
            assert len(months) == 1
            assert months[0]["income"] == 50000
        finally:
            app.dependency_overrides.clear()

    async def test_revenue_no_snapshot(self, db_session):
        user = await _seed_db(db_session)

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/revenue")
            assert response.status_code == 200
            assert response.json()["months"] == []
        finally:
            app.dependency_overrides.clear()


class TestDashboardAlerts:
    async def test_alerts_certificate_pending(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=123,
            title="ML", status="Published",
        )
        db_session.add(course)
        await db_session.flush()
        for i in range(5):
            db_session.add(StudentEnrollment(
                id=uuid.uuid4(), course_id=course.id, student_id=100 + i,
                last_viewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                points_earned=150, certificate_issued=False,
            ))
        await db_session.commit()

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/alerts")
            assert response.status_code == 200
            alerts = response.json()["alerts"]
            cert_alerts = [a for a in alerts if "сертификат" in a["message"]]
            assert len(cert_alerts) == 1
            assert "stepik.org/course/123/certificates" in cert_alerts[0]["link"]
        finally:
            app.dependency_overrides.clear()

    async def test_alerts_low_score(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=456,
            title="JS", status="Published",
        )
        db_session.add(course)
        await db_session.flush()
        for i in range(15):
            db_session.add(StudentEnrollment(
                id=uuid.uuid4(), course_id=course.id, student_id=200 + i,
                last_viewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                points_earned=0, certificate_issued=False,
            ))
        await db_session.commit()

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/alerts")
            assert response.status_code == 200
            errors = [a for a in response.json()["alerts"] if a["type"] == "error"]
            assert len(errors) == 1
            assert "15 студентов" in errors[0]["message"]
        finally:
            app.dependency_overrides.clear()

    async def test_alerts_no_courses(self, db_session):
        user = await _seed_db(db_session)

        async def override_db():
            yield db_session
        async def override_user():
            return user
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/alerts")
            assert response.status_code == 200
            assert response.json()["alerts"] == []
        finally:
            app.dependency_overrides.clear()
