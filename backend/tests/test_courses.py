import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import Course, StudentEnrollment, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


async def _seed_db(session):
    user = User(
        id=uuid.uuid4(), stepik_id=64381531,
        access_token=encrypt_token("test_access"),
        refresh_token=encrypt_token("test_refresh"),
        token_expires_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(user)
    await session.flush()
    return user


class TestCoursesList:
    async def test_list_courses_empty(self, db_session):
        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get("/api/courses")
            assert response.status_code == 200
            assert response.json() == {"courses": []}
        finally:
            app.dependency_overrides.clear()

    async def test_list_courses_returns_data(self, db_session):
        user = await _seed_db(db_session)
        c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100,
                     title="Python", status="Published", health_score=95.0)
        c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=200,
                     title="JS", status="Draft", health_score=80.0)
        db_session.add_all([c1, c2])
        await db_session.flush()
        db_session.add(StudentEnrollment(
            id=uuid.uuid4(), course_id=c1.id, student_id=1,
            last_viewed_at=datetime.now(timezone.utc).replace(tzinfo=None), points_earned=50,
        ))
        await db_session.commit()

        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get("/api/courses")
            assert response.status_code == 200
            courses = response.json()["courses"]
            assert len(courses) == 2
            py = next(c for c in courses if c["title"] == "Python")
            assert py["enrollment_count"] == 1
            js = next(c for c in courses if c["title"] == "JS")
            assert js["enrollment_count"] == 0
        finally:
            app.dependency_overrides.clear()


class TestCoursesGet:
    async def test_get_course_found(self, db_session):
        user = await _seed_db(db_session)
        course = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100,
                        title="Python", status="Published", health_score=95.0)
        db_session.add(course)
        await db_session.commit()
        course_id = str(course.id)

        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get(f"/api/courses/{course_id}")
            assert response.status_code == 200
            data = response.json()["course"]
            assert data["title"] == "Python"
            assert data["stepik_course_id"] == 100
        finally:
            app.dependency_overrides.clear()

    async def test_get_course_not_found(self, db_session):
        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get(f"/api/courses/{uuid.uuid4()}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
