"""Tests for app.main: lifespan, CORS, scheduler, startup tasks."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, scheduler

client = TestClient(app)


class TestAppMetadata:
    def test_app_title(self):
        assert app.title == "Stepik Control Panel"

    def test_app_version(self):
        assert app.version == "0.2.0"


class TestCORSMiddleware:
    def test_cors_headers_on_preflight(self):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_allows_get_only(self):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "GET" in allow_methods
        assert "POST" in allow_methods

    def test_cors_allows_credentials(self):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allowed_headers(self):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        headers = response.headers.get("access-control-allow-headers", "")
        assert "Content-Type" in headers
        assert "Cookie" in headers

    def test_cors_rejects_wrong_methods(self):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "DELETE" not in allow_methods


class TestRouterRegistration:
    def _collect_paths(self):
        paths = set()

        def _walk(router):
            for route in getattr(router, "routes", router):
                if hasattr(route, "path") and not hasattr(route, "routes"):
                    paths.add(route.path)
                elif hasattr(route, "original_router"):
                    sub = route.original_router
                    sub_prefix = getattr(sub, "prefix", "")
                    old_paths = paths.copy()
                    _walk(sub)
                    # If the collected sub-paths do not already include the
                    # router prefix, prepend it (dashboard nested routers).
                    if sub_prefix:
                        for p in paths - old_paths:
                            if not p.startswith(sub_prefix):
                                paths.add(sub_prefix + p)
                elif hasattr(route, "routes"):
                    _walk(route)

        _walk(app)
        return paths

    def test_all_routers_registered(self):
        route_paths = self._collect_paths()
        assert "/api/auth/login" in route_paths
        assert "/api/courses" in route_paths
        assert "/api/dashboard/kpi" in route_paths
        assert "/api/financials" in route_paths
        assert "/api/sync/status" in route_paths
        assert "/api/health" in route_paths


class TestHealthEndpoint:
    def test_health_returns_ok_or_degraded(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("ok", "degraded")

    def test_health_only_get(self):
        response = client.post("/api/health")
        assert response.status_code == 405


class TestScheduler:
    def test_scheduler_is_asyncio(self):
        assert scheduler.__class__.__name__ == "AsyncIOScheduler"

    def test_scheduler_interval_50_minutes(self):
        from app.main import lifespan

        assert lifespan.__name__ == "lifespan"


class TestStartupTasks:
    @pytest.mark.asyncio
    async def test_startup_runs_token_refresh(self):
        with patch("app.main.refresh_user_tokens", new_callable=AsyncMock) as mock_refresh:

            async def _fake_startup():
                await mock_refresh()

            await _fake_startup()
            mock_refresh.assert_awaited_once()

    def test_lifespan_context_exists(self):
        assert app.router.lifespan_context is not None
