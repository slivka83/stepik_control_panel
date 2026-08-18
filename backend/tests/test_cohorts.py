import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, StudentEnrollment, User
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


class TestCohortsBoundaries:
    """Boundary (off-by-one) cases for get_cohorts segmentation.

    active:   0 <= d < 7
    passive:  7 <= d < 30
    fading:   30 <= d < 90
    sleeping: d >= 90   (and not Zombie)
    """

    async def _run(self, db_session, user, enrollments):
        course = Course(
            id=uuid.uuid4(),
            user_id=user.id,
            stepik_course_id=100,
            title="Python",
            status="Published",
        )
        db_session.add(course)
        await db_session.flush()
        now = datetime.now(UTC)
        for sid, days, status in enrollments:
            db_session.add(
                StudentEnrollment(
                    id=uuid.uuid4(),
                    course_id=course.id,
                    student_id=sid,
                    last_viewed_at=(now - timedelta(days=days)).replace(tzinfo=None),
                    cohort_status=status,
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
            return response.json()
        finally:
            app.dependency_overrides.clear()

    async def test_active_passive_boundary(self, db_session):
        # 1h buffer inside the boundary avoids cross-second flakiness.
        user = await _seed_user(db_session)
        data = await self._run(
            db_session,
            user,
            [
                (1, 7 + 1 / 24, "Active"),  # just over 7d → passive
                (2, 7 - 1 / 24, "Active"),  # just under 7d → active
            ],
        )
        assert data["active"] == 1
        assert data["passive"] == 1

    async def test_fading_sleeping_boundary(self, db_session):
        user = await _seed_user(db_session)
        data = await self._run(
            db_session,
            user,
            [
                (1, 90 + 1 / 24, "Active"),  # just over 90d → sleeping
                (2, 90 - 1 / 24, "Active"),  # just under 90d → fading
            ],
        )
        assert data["fading"] == 1
        assert data["sleeping"] == 1

    async def test_passive_and_fading_inclusion(self, db_session):
        user = await _seed_user(db_session)
        data = await self._run(
            db_session,
            user,
            [
                (1, 30 - 1 / 24, "Active"),  # just under 30d → passive
                (2, 90 - 1 / 24, "Active"),  # just under 90d → fading
            ],
        )
        assert data["passive"] == 1
        assert data["fading"] == 1

    async def test_zombie_excluded_from_all(self, db_session):
        user = await _seed_user(db_session)
        # A zombie active "today" must not be counted in any segment.
        data = await self._run(db_session, user, [(1, 1, "Zombie")])
        assert data["active"] == 0
        assert data["passive"] == 0
        assert data["fading"] == 0
        assert data["sleeping"] == 0

    async def test_null_last_viewed_not_counted(self, db_session):
        user = await _seed_user(db_session)
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
                last_viewed_at=None,
                cohort_status="Active",
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
            data = client.get("/api/dashboard/cohorts").json()
            assert data["active"] == 0
            assert data["passive"] == 0
            assert data["fading"] == 0
            assert data["sleeping"] == 0
        finally:
            app.dependency_overrides.clear()
