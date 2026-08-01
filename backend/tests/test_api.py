from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")

    def test_health_get_only(self):
        response = client.post("/api/health")
        assert response.status_code == 405


class TestAuthLogin:
    def test_login_redirects_to_stepik(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        assert response.status_code == 302
        location = response.headers["location"]
        assert "stepik.org/oauth2/authorize/" in location

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

    def test_login_sets_state_cookie(self):
        response = client.get("/api/auth/login", follow_redirects=False)
        assert "oauth_state" in response.cookies


class TestAuthMe:
    def test_me_no_session_returns_401(self):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_invalid_session_returns_401(self):
        response = client.get("/api/auth/me", cookies={"stepik_session": "invalid.token"})
        assert response.status_code == 401


class TestAuthLogout:
    def test_logout_returns_no_content(self):
        response = client.post("/api/auth/logout")
        assert response.status_code == 204


class TestSessionSigning:
    def test_create_and_verify_session_token(self):
        from app.api.auth import create_session_token, verify_session_token

        token = create_session_token("user-123")
        result = verify_session_token(token)
        assert result == "user-123"

    def test_verify_invalid_token_returns_none(self):
        from app.api.auth import verify_session_token

        result = verify_session_token("invalid.token")
        assert result is None

    def test_verify_tampered_token_returns_none(self):
        from app.api.auth import create_session_token, verify_session_token

        token = create_session_token("user-123")
        tampered = token[:-5] + "XXXXX"
        result = verify_session_token(tampered)
        assert result is None

    def test_verify_empty_string_returns_none(self):
        from app.api.auth import verify_session_token

        result = verify_session_token("")
        assert result is None

    def test_verify_no_dot_returns_none(self):
        from app.api.auth import verify_session_token

        result = verify_session_token("nodothere")
        assert result is None


class TestCORSMiddleware:
    def test_cors_allows_frontend_origin(self):
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
