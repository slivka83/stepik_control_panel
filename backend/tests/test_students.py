import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import (
    Course,
    MartCertificate,
    MartComment,
    StudentEnrollment,
    StudentMart,
    Submission,
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


async def _seed_marts(session, n):
    for i in range(n):
        session.add(
            StudentMart(
                id=uuid.uuid4(),
                student_id=1000 + i,
                name=f"Student {i}",
                cohort_status="Sleeping",
            )
        )
    await session.commit()


class TestStudentsPagination:
    async def test_invalid_limit_zero(self, db_session):
        user = await _seed_user(db_session)

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/students?limit=0")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_invalid_limit_too_large(self, db_session):
        user = await _seed_user(db_session)

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/students?limit=201")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_invalid_skip_negative(self, db_session):
        user = await _seed_user(db_session)

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/students?skip=-1")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_skip_beyond_total_returns_empty(self, db_session):
        user = await _seed_user(db_session)
        await _seed_marts(db_session, 3)

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/dashboard/students?skip=100&limit=10")
            assert response.status_code == 200
            data = response.json()
            assert data["students"] == []
            assert data["total"] == 3
        finally:
            app.dependency_overrides.clear()


class TestStudentsFilteredCounters:
    async def test_row_counters_are_recomputed_for_selected_course(self, db_session):
        """Regression: при фильтре по курсам строка показывала account-wide
        счётчики из student_marts (решения/комментарии/сертификаты всех курсов)."""
        user = await _seed_user(db_session)
        c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="A", status="Published")
        c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=101, title="B", status="Published")
        db_session.add_all([c1, c2])
        db_session.add(
            StudentMart(
                id=uuid.uuid4(),
                student_id=7,
                name="Иван",
                cohort_status="Active",
                courses_count=3,
                certificates=99,
                submissions_count=99,
                submissions_successful=99,
                comments_count=99,
                published_solutions=99,
            )
        )
        old = (datetime.now(UTC) - timedelta(days=40)).replace(tzinfo=None)
        db_session.add_all(
            [
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    student_id=7,
                    cohort_status="Passive",
                    last_viewed_at=old,
                ),
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c2.id,
                    student_id=7,
                    cohort_status="Active",
                    last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                ),
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=1,
                    stepik_step_id=10,
                    course_id=c1.id,
                    status="correct",
                    score=1.0,
                    submission_time=datetime.now(UTC).replace(tzinfo=None),
                    user_id=7,
                    is_author=False,
                ),
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=2,
                    stepik_step_id=11,
                    course_id=c2.id,
                    status="wrong",
                    score=0.0,
                    submission_time=datetime.now(UTC).replace(tzinfo=None),
                    user_id=7,
                    is_author=False,
                ),
                MartCertificate(id=uuid.uuid4(), course_id=c1.id, stepik_course_id=100, certificate_id=1, user_id=7),
                MartCertificate(id=uuid.uuid4(), course_id=c2.id, stepik_course_id=101, certificate_id=2, user_id=7),
                MartComment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    stepik_course_id=100,
                    comment_id=1,
                    user_id=7,
                    is_solution=False,
                ),
                MartComment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    stepik_course_id=100,
                    comment_id=2,
                    user_id=7,
                    is_solution=True,
                ),
                MartComment(
                    id=uuid.uuid4(),
                    course_id=c2.id,
                    stepik_course_id=101,
                    comment_id=3,
                    user_id=7,
                    is_solution=False,
                ),
            ]
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            data = client.get(f"/api/dashboard/students?course_ids={c1.id}").json()
        finally:
            app.dependency_overrides.clear()

        assert data["total"] == 1
        row = data["students"][0]
        assert row["courses_count"] == 1
        assert row["certificates"] == 1
        assert row["submissions_count"] == 1
        assert row["submissions_successful"] == 1
        assert row["comments_count"] == 1
        assert row["published_solutions"] == 1
        assert row["cohort_status"] == "Passive"

    async def test_sorting_uses_filtered_counters(self, db_session):
        """Regression: при фильтре сортировка шла по account-wide счётчикам,
        а в ячейках показывались значения выбранного курса — порядок и
        страницы противоречили цифрам."""
        user = await _seed_user(db_session)
        c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="A", status="Published")
        db_session.add(c1)
        db_session.add_all(
            [
                StudentMart(
                    id=uuid.uuid4(),
                    student_id=7,
                    name="Account-wide leader",
                    cohort_status="Active",
                    submissions_count=99,
                ),
                StudentMart(
                    id=uuid.uuid4(),
                    student_id=8,
                    name="Filtered leader",
                    cohort_status="Active",
                    submissions_count=0,
                ),
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    student_id=7,
                    cohort_status="Active",
                    last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                ),
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=c1.id,
                    student_id=8,
                    cohort_status="Active",
                    last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                ),
            ]
        )
        for i in range(1, 5):
            db_session.add(
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=100 + i,
                    stepik_step_id=10,
                    course_id=c1.id,
                    status="correct",
                    score=1.0,
                    submission_time=datetime.now(UTC).replace(tzinfo=None),
                    user_id=7 if i == 1 else 8,
                    is_author=False,
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
            data = client.get(f"/api/dashboard/students?course_ids={c1.id}&sort=submissions_count&order=desc").json()
        finally:
            app.dependency_overrides.clear()

        assert [row["student_id"] for row in data["students"]] == [8, 7]
        assert data["students"][0]["submissions_count"] == 3
        assert data["students"][1]["submissions_count"] == 1
