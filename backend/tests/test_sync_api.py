import app.services.sync as sync_mod
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.models import FinancialSnapshot
from datetime import datetime, timezone
import uuid


client = TestClient(app, raise_server_exceptions=False)


class TestSyncStatus:
    async def test_status_returns_fields(self, db_session):
        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get("/api/sync/status")
            assert response.status_code == 200
            data = response.json()
            assert "in_progress" in data
            assert "last_sync" in data
            assert "cooldown_remaining_seconds" in data
            assert isinstance(data["in_progress"], bool)
        finally:
            app.dependency_overrides.clear()

    async def test_status_no_snapshot(self, db_session):
        async def override():
            yield db_session
        app.dependency_overrides[get_db] = override
        try:
            response = client.get("/api/sync/status")
            assert response.status_code == 200
            assert response.json()["last_sync"] is None
        finally:
            app.dependency_overrides.clear()


class TestSyncTrigger:
    def test_trigger_sync_no_auth_returns_401(self):
        response = client.post("/api/sync")
        assert response.status_code == 401


class TestSyncModule:
    def test_can_sync_initial(self):
        sync_mod._sync_in_progress = False
        sync_mod._last_sync_completed_at = 0
        assert sync_mod.can_sync() is True

    def test_can_sync_in_progress(self):
        sync_mod._sync_in_progress = True
        sync_mod._last_sync_completed_at = 0
        assert sync_mod.can_sync() is False
        sync_mod._sync_in_progress = False

    @pytest.mark.asyncio
    async def test_sync_all_skips_when_in_progress(self):
        sync_mod._sync_in_progress = True
        result = await sync_mod.sync_all(force=False)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_in_progress"
        sync_mod._sync_in_progress = False

    def test_sync_month_names(self):
        assert sync_mod.MONTH_NAMES[1] == "Январь"
        assert sync_mod.MONTH_NAMES[7] == "Июль"
        assert sync_mod.MONTH_NAMES[12] == "Декабрь"

    def test_sync_cooldown_constant(self):
        assert sync_mod.SYNC_COOLDOWN_SECONDS == 3600
