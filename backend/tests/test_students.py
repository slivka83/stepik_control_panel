import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import StudentMart, User
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
