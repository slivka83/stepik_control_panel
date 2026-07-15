import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app


client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_get_only(self):
        response = client.post("/api/health")
        assert response.status_code == 405


class TestAuthLogin:
    def test_login_redirects_to_stepik(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        assert response.status_code == 307
        assert "stepik.org/oauth2/authorize/" in response.headers["location"]

    def test_login_includes_scope_read(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        location = response.headers["location"]
        assert "scope=read" in location

    def test_login_includes_response_type(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        location = response.headers["location"]
        assert "response_type=code" in location

    def test_login_includes_client_id(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        location = response.headers["location"]
        assert "client_id=" in location

    def test_login_includes_redirect_uri(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        location = response.headers["location"]
        assert "redirect_uri=" in location


class TestAuthToken:
    def test_token_no_user_returns_401(self):
        response = client.get("/api/auth/token")
        assert response.status_code == 401


class TestCoursesEndpoint:
    def test_list_courses_no_auth(self):
        response = client.get("/api/courses")
        assert response.status_code == 401


class TestDashboardKPI:
    def test_kpi_no_auth(self):
        response = client.get("/api/dashboard/kpi")
        assert response.status_code == 401


class TestDashboardCohorts:
    def test_cohorts_no_auth(self):
        response = client.get("/api/dashboard/cohorts")
        assert response.status_code == 401


class TestDashboardRevenue:
    def test_revenue_no_auth(self):
        response = client.get("/api/dashboard/revenue")
        assert response.status_code == 401


class TestCORSMiddleware:
    def test_cors_allows_localhost_3000(self):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200


class TestZeroWritePolicy:
    def test_only_get_allowed_in_api(self):
        methods = ["post", "put", "patch", "delete"]
        for method in methods:
            response = getattr(client, method)("/api/health")
            assert response.status_code == 405
