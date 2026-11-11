from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response

from app.api.auth import _profile_stepik_id, callback
from app.models import User


class TestProfileStepikId:
    """Regression: Stepik /profiles returns profile id in `id` and the real user
    id in `user`; storing profile.id (1) broke users.stepik_id."""

    def test_uses_user_field_from_profile(self):
        assert _profile_stepik_id({"id": 1, "user": 64381531}) == 64381531

    def test_falls_back_to_id_for_users_response(self):
        assert _profile_stepik_id({"id": 64381531}) == 64381531

    def test_returns_none_for_missing_or_invalid(self):
        assert _profile_stepik_id({}) is None
        assert _profile_stepik_id({"user": None, "id": None}) is None
        assert _profile_stepik_id({"user": "not-a-number"}) is None
        assert _profile_stepik_id(None) is None


def _callback_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/callback",
            "query_string": b"code=test-code&state=test-state",
            "headers": [(b"cookie", b"oauth_state=test-state")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


class TestAuthCallback:
    """End-to-end callback: profile shape must produce the real Stepik user id."""

    @pytest.mark.asyncio
    async def test_callback_stores_user_id_from_profile_user_field(self, db_session):
        with (
            patch("app.api.auth.check_auth_rate_limit", new_callable=AsyncMock, return_value=(True, 0)),
            patch(
                "app.api.auth.exchange_code_for_token",
                new_callable=AsyncMock,
                return_value={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600},
            ),
            patch(
                "app.api.auth.get_user_profile",
                new_callable=AsyncMock,
                return_value={"id": 1, "user": 64381531, "first_name": "Test"},
            ),
        ):
            response = await callback("test-code", _callback_request(), Response(), db_session)

        assert response.status_code == 302
        user = (await db_session.execute(select(User))).scalar_one()
        assert user.stepik_id == 64381531
        assert user.access_token
