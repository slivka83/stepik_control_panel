import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, FinancialSnapshot, StudentEnrollment, StudentMart, User
from app.services.crypto import encrypt_token
from tests.conftest import build_marts

client = TestClient(app, raise_server_exceptions=False)


async def _seed_db(session):
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


class TestDashboardKPI:
    async def test_kpi_returns_all_fields(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=100,
            title="Python",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()

        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=course.id,
                student_id=1,
                last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                date_joined=datetime.now(UTC).replace(tzinfo=None),
                points_earned=50,
                certificate_issued=False,
            )
        )
        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=course.id,
                student_id=2,
                last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                date_joined=datetime.now(UTC).replace(tzinfo=None),
                points_earned=100,
                certificate_issued=True,
            )
        )
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {
                        "current_month_turnover": 40000,
                        "current_month_income": 40000,
                        "total_income": 150000,
                        "total_turnover": 200000,
                        "total_refunds": 5000,
                        "total_payments": 42,
                    },
                    "months": [],
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
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=100,
            title="Python",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        old = now.replace(year=now.year - 1, month=12)
        prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        prev_month_key = f"{prev_year}-{prev_month:02d}"

        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=course.id,
                student_id=1,
                last_viewed_at=old,
                date_joined=old,
                points_earned=50,
                certificate_issued=True,
            )
        )
        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=course.id,
                student_id=2,
                last_viewed_at=now,
                date_joined=now,
                points_earned=100,
                certificate_issued=True,
            )
        )
        cur_month = f"{now.year}-{now.month:02d}"
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {
                        "current_month_turnover": 40000,
                        "current_month_income": 40000,
                        "total_income": 150000,
                        "total_turnover": 200000,
                        "total_refunds": 5000,
                        "total_payments": 42,
                    },
                    "months": [],
                    "courses": [],
                    "recent_payments": [],
                    "community": {
                        "total_comments": 1,
                        "total_reviews": 3,
                        "average_rating": 4.5,
                        "total_solutions": 4,
                        "comments_monthly": {cur_month: 1},
                        "solutions_monthly": {cur_month: 1, prev_month_key: 2},
                    },
                },
                updated_at=now,
            )
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json)
            VALUES ('c1', '1', '100', :j1)
        """),
            {"j1": json.dumps({"issue_date": cur_month + "-15T10:00:00Z"})},
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json)
            VALUES ('c0', '9', '100', :j0)
        """),
            {"j0": json.dumps({"issue_date": prev_month_key + "-15T10:00:00Z"})},
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_course_review (review_id, course, _raw_json)
            VALUES ('r1', '100', :j2)
        """),
            {"j2": json.dumps({"create_date": cur_month + "-10T10:00:00Z"})},
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_course_review (review_id, course, _raw_json)
            VALUES ('r0', '100', :j3)
        """),
            {"j3": json.dumps({"create_date": prev_month_key + "-10T10:00:00Z"})},
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (500, 10, :j4)
        """),
            {"j4": json.dumps({"num_grades": [0, 0, 0, 2, 12]})},
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (501, 11, :j5)
        """),
            {"j5": json.dumps({"num_grades": [1, 1, 1, 1, 1]})},
        )
        await db_session.commit()
        await build_marts(db_session)

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
            assert data["certificates_change_detail"] == {"current": 1, "previous": 1}
            assert data["total_comments"] == 1
            assert data["comments_prev_months"] == 0
            assert data["current_month_comments"] == 1
            assert data["comments_change_detail"] is None, "1 vs 0 → нет процента (деление на ноль)"
            assert data["total_reviews"] == 3
            assert data["reviews_prev_months"] == 2
            assert data["reviews_current_month"] == 1
            assert data["reviews_change_pct"] == 0, "1 vs 1 → 0%"
            assert data["reviews_change_detail"] == {"current": 1, "previous": 1}
            assert data["published_solutions_prev_months"] == 3, "4 - 1 (текущий месяц)"
            assert data["published_solutions_current_month"] == 1
            assert data["published_solutions_change_pct"] == -50, "1 vs 2 → -50%"
            assert data["published_solutions_change_detail"] == {"current": 1, "previous": 2}
            expected_grade = (4 * 2 + 5 * 12 + 1 + 2 + 3 + 4 + 5) / 19
            assert data["steps_average_grade"] == round(expected_grade, 2), "средняя оценка шагов из num_grades"
        finally:
            app.dependency_overrides.clear()


class TestDashboardCohorts:
    async def test_cohorts_returns_all_statuses(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=100,
            title="Python",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()

        for sid, days in [(1, 3), (2, 15), (3, 50), (4, 100)]:
            db_session.add(
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=course.id,
                    student_id=sid,
                    last_viewed_at=(datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None),
                    points_earned=50,
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
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {},
                    "months": [{"month": "Январь 2026", "income": 50000}],
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


class TestDashboardStudents:
    """API читает только витрину student_marts — никаких запросов к сырому слою."""

    async def _setup(self, db_session, user):
        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user

    def _seed_mart(self, db_session, student_id, **overrides):
        row = {
            "id": uuid.uuid4(),
            "student_id": student_id,
            "name": None,
            "cohort_status": "Sleeping",
            "courses_count": 0,
            "certificates": 0,
            "submissions_count": 0,
            "submissions_successful": 0,
            "comments_count": 0,
            "published_solutions": 0,
            "last_activity": None,
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }
        row.update(overrides)
        db_session.add(StudentMart(**row))

    async def test_returns_student_mart_rows(self, db_session):
        user = await _seed_db(db_session)
        self._seed_mart(
            db_session,
            7,
            name="Иван Петров",
            cohort_status="Active",
            courses_count=2,
            certificates=1,
            submissions_count=3,
            submissions_successful=2,
            comments_count=4,
            published_solutions=6,
            last_activity=datetime.now(UTC).replace(tzinfo=None),
        )
        self._seed_mart(db_session, 9, courses_count=1, certificates=1)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            response = client.get("/api/dashboard/students")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            by_id = {s["student_id"]: s for s in data["students"]}
            s7 = by_id[7]
            assert s7["name"] == "Иван Петров"
            assert s7["profile_url"] == "https://stepik.org/users/7"
            assert s7["cohort_status"] == "Active"
            assert s7["courses_count"] == 2
            assert s7["certificates"] == 1
            assert s7["submissions_count"] == 3
            assert s7["submissions_successful"] == 2
            assert s7["comments_count"] == 4
            assert s7["published_solutions"] == 6
            assert s7["last_activity"] is not None
        finally:
            app.dependency_overrides.clear()

    async def test_orders_by_last_activity_desc(self, db_session):
        user = await _seed_db(db_session)
        now = datetime.now(UTC).replace(tzinfo=None)
        from datetime import timedelta as _td

        self._seed_mart(db_session, 1, last_activity=now - _td(days=10))
        self._seed_mart(db_session, 2, last_activity=now)
        self._seed_mart(db_session, 3, last_activity=None)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            data = client.get("/api/dashboard/students").json()
            assert [s["student_id"] for s in data["students"]] == [2, 1, 3]
        finally:
            app.dependency_overrides.clear()

    async def test_sort_by_submissions_count(self, db_session):
        user = await _seed_db(db_session)
        self._seed_mart(db_session, 1, submissions_count=5)
        self._seed_mart(db_session, 2, submissions_count=50)
        self._seed_mart(db_session, 3, submissions_count=1)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            desc = client.get("/api/dashboard/students?sort=submissions_count&order=desc").json()
            assert [s["student_id"] for s in desc["students"]] == [2, 1, 3]
            asc = client.get("/api/dashboard/students?sort=submissions_count&order=asc").json()
            assert [s["student_id"] for s in asc["students"]] == [3, 1, 2]
        finally:
            app.dependency_overrides.clear()

    async def test_sort_by_published_solutions(self, db_session):
        user = await _seed_db(db_session)
        self._seed_mart(db_session, 1, published_solutions=5)
        self._seed_mart(db_session, 2, published_solutions=50)
        self._seed_mart(db_session, 3, published_solutions=1)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            desc = client.get("/api/dashboard/students?sort=published_solutions&order=desc").json()
            assert [s["student_id"] for s in desc["students"]] == [2, 1, 3]
            asc = client.get("/api/dashboard/students?sort=published_solutions&order=asc").json()
            assert [s["student_id"] for s in asc["students"]] == [3, 1, 2]
        finally:
            app.dependency_overrides.clear()

    async def test_sort_last_activity_asc_nulls_last(self, db_session):
        user = await _seed_db(db_session)
        now = datetime.now(UTC).replace(tzinfo=None)
        from datetime import timedelta as _td

        self._seed_mart(db_session, 1, last_activity=now)
        self._seed_mart(db_session, 2, last_activity=None)
        self._seed_mart(db_session, 3, last_activity=now - _td(days=10))
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            data = client.get("/api/dashboard/students?sort=last_activity&order=asc").json()
            assert [s["student_id"] for s in data["students"]] == [3, 1, 2]
        finally:
            app.dependency_overrides.clear()

    async def test_sort_by_name(self, db_session):
        user = await _seed_db(db_session)
        self._seed_mart(db_session, 1, name="Иван Петров")
        self._seed_mart(db_session, 2, name="Анна Иванова")
        self._seed_mart(db_session, 3, name="Олег Сидоров")
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            data = client.get("/api/dashboard/students?sort=name&order=asc").json()
            assert [s["student_id"] for s in data["students"]] == [2, 1, 3]
        finally:
            app.dependency_overrides.clear()

    async def test_invalid_sort_field_returns_400(self, db_session):
        user = await _seed_db(db_session)
        self._seed_mart(db_session, 1)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            response = client.get("/api/dashboard/students?sort=nope")
            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    async def test_invalid_order_returns_400(self, db_session):
        user = await _seed_db(db_session)
        self._seed_mart(db_session, 1)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            response = client.get("/api/dashboard/students?sort=courses_count&order=sideways")
            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    async def test_pagination(self, db_session):
        user = await _seed_db(db_session)
        for sid in range(1, 6):
            self._seed_mart(db_session, sid)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            page = client.get("/api/dashboard/students?skip=1&limit=2").json()
            assert page["total"] == 5
            assert len(page["students"]) == 2
        finally:
            app.dependency_overrides.clear()

    async def test_orders_ties_by_student_id(self, db_session):
        """Regression: без tiebreaker'а равные значения сортировки давали
        нестабильный порядок — один и тот же студент попадал на разные
        страницы пагинации."""
        user = await _seed_db(db_session)
        self._seed_mart(db_session, 5, courses_count=1)
        self._seed_mart(db_session, 1, courses_count=1)
        self._seed_mart(db_session, 3, courses_count=2)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            data = client.get("/api/dashboard/students?sort=courses_count&order=desc").json()
            assert [s["student_id"] for s in data["students"]] == [3, 1, 5]
        finally:
            app.dependency_overrides.clear()

    async def test_pagination_pages_do_not_overlap(self, db_session):
        """Regression: при равных значениях сортировки страницы пагинации
        не должны пересекаться и терять студентов."""
        user = await _seed_db(db_session)
        for sid in range(1, 10):
            self._seed_mart(db_session, sid, courses_count=1)
        await db_session.commit()

        await self._setup(db_session, user)
        try:
            seen = []
            for skip in (0, 3, 6):
                data = client.get(f"/api/dashboard/students?sort=courses_count&order=desc&skip={skip}&limit=3").json()
                seen.extend(s["student_id"] for s in data["students"])
            assert seen == list(range(1, 10))
        finally:
            app.dependency_overrides.clear()

    async def test_students_empty_without_mart(self, db_session):
        user = await _seed_db(db_session)

        await self._setup(db_session, user)
        try:
            response = client.get("/api/dashboard/students")
            assert response.status_code == 200
            assert response.json() == {"students": [], "total": 0}
        finally:
            app.dependency_overrides.clear()


class TestDashboardAlerts:
    async def test_alerts_certificate_pending(self, db_session):
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=123,
            title="ML",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()
        for i in range(5):
            db_session.add(
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=course.id,
                    student_id=100 + i,
                    last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                    points_earned=150,
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
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=456,
            title="JS",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()
        for i in range(15):
            db_session.add(
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=course.id,
                    student_id=200 + i,
                    last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                    points_earned=0,
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


class TestDashboardCertificates:
    async def _call(self, db_session, user, course_ids=None):
        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            url = "/api/dashboard/certificates"
            if course_ids is not None:
                url += f"?course_ids={course_ids}"
            response = client.get(url)
            assert response.status_code == 200
            return response.json()["months"]
        finally:
            app.dependency_overrides.clear()

    async def test_monthly_split_distinction_vs_regular(self, db_session):
        """Regression: /certificates отдаёт сертификаты по месяцам выдачи с
        разбивкой «С отличием» (type=distinction) и «Обычные»: dark = всего,
        light = обычные (overlap = «С отличием»)."""
        user = await _seed_db(db_session)
        course = Course(
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=100,
            title="Python",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()
        certs = [
            ("d1", "100", "2026-06-15T10:00:00Z", "distinction"),
            ("d2", "100", "2026-06-20T10:00:00Z", "distinction"),
            ("r1", "100", "2026-06-25T10:00:00Z", "regular"),
            ("r2", "100", "2026-07-01T10:00:00Z", "regular"),
            ("u1", "100", "2026-07-02T10:00:00Z", None),
            ("n1", "100", None, "regular"),
        ]
        for cid, course_id, issue, ctype in certs:
            raw = {"issue_date": issue, "type": ctype}
            await db_session.execute(
                text("INSERT INTO raw_certificate (certificate_id, course_id, _raw_json) VALUES (:cid, :course, :j)"),
                {"cid": cid, "course": course_id, "j": json.dumps(raw)},
            )
        await db_session.commit()
        await build_marts(db_session)

        months = await self._call(db_session, user)
        assert months == [
            {"month": "Июнь 2026", "dark": 3, "light": 1},
            {"month": "Июль 2026", "dark": 2, "light": 2},
        ], "без type и без issue_date не должны ломать разбивку"

    async def test_empty_without_data(self, db_session):
        user = await _seed_db(db_session)
        await db_session.commit()
        assert await self._call(db_session, user) == []
