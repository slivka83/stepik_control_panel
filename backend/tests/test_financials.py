import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import FinancialSnapshot

client = TestClient(app, raise_server_exceptions=False)


class TestFinancials:
    async def test_returns_snapshot_data(self, db_session):
        db_session.add(FinancialSnapshot(
            id=uuid.uuid4(),
            data={
                "summary": {"total_turnover": 200000, "total_income": 150000,
                            "total_refunds": 5000, "total_payments": 42, "net_income": 145000},
                "months": [{"month": "Январь 2026", "income": 50000}],
                "courses": [{"title": "Python", "income": 100000}],
                "recent_payments": [{"id": 1, "amount": 2940}],
            },
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        await db_session.commit()

        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get("/api/financials")
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["total_turnover"] == 200000
            assert data["summary"]["net_income"] == 145000
            assert len(data["months"]) == 1
            assert len(data["courses"]) == 1
        finally:
            app.dependency_overrides.clear()

    async def test_no_snapshot_returns_defaults(self, db_session):
        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get("/api/financials")
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["total_turnover"] == 0
            assert data["months"] == []
        finally:
            app.dependency_overrides.clear()
