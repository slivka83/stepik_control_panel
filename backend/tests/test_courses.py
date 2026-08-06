import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, StudentEnrollment, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


async def _seed_db(session):
    user = User(
        id=uuid.uuid4(),
        stepik_id=64381531,
        access_token=encrypt_token("test_access"),
        refresh_token=encrypt_token("test_refresh"),
        token_expires_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(user)
    await session.flush()
    return user


async def _override_get_user():
    pass


def _setup_overrides(session, user):
    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


class TestCoursesList:
    async def test_list_courses_empty(self, db_session):
        user = await _seed_db(db_session)
        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/courses")
            assert response.status_code == 200
            assert response.json() == {"courses": []}
        finally:
            app.dependency_overrides.clear()

    async def test_list_courses_sorted_by_published_at(self, db_session):
        """Regression: таблица курсов должна быть отсортирована по Опубликован
        (сначала опубликованные — новые сверху, черновики в конце)."""
        user = await _seed_db(db_session)
        old = datetime(2025, 1, 1).replace(tzinfo=UTC).replace(tzinfo=None)
        new = datetime(2026, 7, 1).replace(tzinfo=UTC).replace(tzinfo=None)
        mid = datetime(2025, 6, 15).replace(tzinfo=UTC).replace(tzinfo=None)
        draft = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=300, title="Draft", status="Draft", published_at=None
        )
        c_new = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="New", status="Published", published_at=new
        )
        c_old = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=200, title="Old", status="Published", published_at=old
        )
        c_mid = Course(
            id=uuid.uuid4(), user_id=user.id, stepik_course_id=400, title="Mid", status="Published", published_at=mid
        )
        db_session.add_all([draft, c_old, c_new, c_mid])
        await db_session.commit()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/courses")
            assert response.status_code == 200
            titles = [c["title"] for c in response.json()["courses"]]
            assert titles == ["New", "Mid", "Old", "Draft"], titles
        finally:
            app.dependency_overrides.clear()

    async def test_list_courses_returns_data(self, db_session):
        user = await _seed_db(db_session)
        c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=200, title="JS", status="Draft")
        db_session.add_all([c1, c2])
        await db_session.flush()
        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=c1.id,
                student_id=1,
                last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                points_earned=50,
            )
        )
        db_session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=c1.id,
                student_id=2,
                last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                points_earned=90,
                certificate_issued=True,
            )
        )
        await db_session.commit()

        _setup_overrides(db_session, user)
        try:
            response = client.get("/api/courses")
            assert response.status_code == 200
            courses = response.json()["courses"]
            assert len(courses) == 2
            py = next(c for c in courses if c["title"] == "Python")
            assert py["enrollment_count"] == 2
            assert py["certificates_count"] == 1
            js = next(c for c in courses if c["title"] == "JS")
            assert js["enrollment_count"] == 0
            assert js["certificates_count"] == 0
        finally:
            app.dependency_overrides.clear()


class TestCoursesGet:
    async def test_get_course_found(self, db_session):
        user = await _seed_db(db_session)
        course = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        db_session.add(course)
        await db_session.commit()
        course_id = str(course.id)

        _setup_overrides(db_session, user)
        try:
            response = client.get(f"/api/courses/{course_id}")
            assert response.status_code == 200
            data = response.json()["course"]
            assert data["title"] == "Python"
            assert data["stepik_course_id"] == 100
        finally:
            app.dependency_overrides.clear()

    async def test_get_course_not_found(self, db_session):
        user = await _seed_db(db_session)
        _setup_overrides(db_session, user)
        try:
            response = client.get(f"/api/courses/{uuid.uuid4()}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
