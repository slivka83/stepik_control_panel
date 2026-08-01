import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import FinancialSnapshot, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


class TestFinancials:
    async def test_returns_snapshot_data(self, db_session):
        user = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("test_access"),
            refresh_token=encrypt_token("test_refresh"),
            token_expires_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(user)
        await db_session.flush()

        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {
                        "total_turnover": 200000,
                        "total_income": 150000,
                        "total_refunds": 5000,
                        "total_payments": 42,
                        "net_income": 145000,
                    },
                    "months": [
                        {
                            "month": "Январь 2025",
                            "year": 2025,
                            "month_num": 1,
                            "income": 50000,
                            "turnover": 70000,
                            "refunds": 0,
                            "payments_count": 15,
                            "refunds_count": 0,
                        },
                        {
                            "month": "Февраль 2025",
                            "year": 2025,
                            "month_num": 2,
                            "income": 30000,
                            "turnover": 40000,
                            "refunds": 2000,
                            "payments_count": 10,
                            "refunds_count": 1,
                        },
                        {
                            "month": "Январь 2026",
                            "year": 2026,
                            "month_num": 1,
                            "income": 70000,
                            "turnover": 90000,
                            "refunds": 0,
                            "payments_count": 17,
                            "refunds_count": 0,
                        },
                    ],
                    "courses": [{"title": "Python", "income": 100000}],
                    "recent_payments": [{"id": 1, "amount": 2940}],
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
            response = client.get("/api/financials")
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["total_turnover"] == 200000
            assert data["summary"]["net_income"] == 145000
            assert len(data["months"]) == 3
            assert len(data["courses"]) == 1
            assert [y["year"] for y in data["years"]] == [2025, 2026]
            assert data["years"][0]["payments_count"] == 25
            assert data["years"][0]["turnover"] == 110000
            assert data["years"][0]["income"] == 80000
            assert data["years"][0]["refunds"] == 2000
            assert data["years"][1]["payments_count"] == 17
            assert data["years"][1]["income"] == 70000
        finally:
            app.dependency_overrides.clear()

    async def test_no_snapshot_returns_defaults(self, db_session):
        user = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("test_access"),
            refresh_token=encrypt_token("test_refresh"),
            token_expires_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(user)
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/financials")
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["total_turnover"] == 0
            assert data["months"] == []
            assert data["years"] == []
        finally:
            app.dependency_overrides.clear()
