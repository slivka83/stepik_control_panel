import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response

from app.api.auth import _profile_stepik_id, callback
from app.api.auth import settings as auth_settings
from app.models import User
from app.services.crypto import decrypt_token, encrypt_token


class TestProfileStepikId:
    """Regression: Stepik /stepics/1 отдаёт id профиля в `id` (обычно 1),
    а настоящий id учётной записи — в `user`. Хранить `id` нельзя: так
    создавалась пустая вторая учётная запись со stepik_id=1."""

    def test_uses_user_field_from_current_user(self):
        assert _profile_stepik_id({"id": 1, "user": 64381531}) == 64381531

    def test_ignores_profile_id(self):
        assert _profile_stepik_id({"id": 1}) is None
        assert _profile_stepik_id({"id": 64381531}) is None

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


def _token_exchange_patches(profile: dict, panel_owner: int = 0):
    return (
        patch("app.api.auth.check_auth_rate_limit", new_callable=AsyncMock, return_value=(True, 0)),
        patch(
            "app.api.auth.exchange_code_for_token",
            new_callable=AsyncMock,
            return_value={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600},
        ),
        patch("app.api.auth.get_user_profile", new_callable=AsyncMock, return_value=profile),
        patch.object(auth_settings, "stepik_user_id", panel_owner),
    )


class TestAuthCallback:
    """End-to-end callback: профиль должен давать реальный id пользователя."""

    @pytest.mark.asyncio
    async def test_callback_stores_user_id_from_profile_user_field(self, db_session):
        rate_limit, exchange, profile, panel = _token_exchange_patches(
            {"id": 1, "user": 64381531, "first_name": "Test"}
        )
        with rate_limit, exchange, profile, panel:
            response = await callback("test-code", _callback_request(), Response(), db_session)

        assert response.status_code == 302
        user = (await db_session.execute(select(User))).scalar_one()
        assert user.stepik_id == 64381531
        assert user.access_token

    @pytest.mark.asyncio
    async def test_callback_reuses_existing_account_instead_of_creating_second(self, db_session):
        """Regression: повторный вход создавал вторую пустую учётную запись."""
        existing = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("old-access"),
            refresh_token=encrypt_token("old-refresh"),
            token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db_session.add(existing)
        await db_session.commit()
        existing_id = existing.id

        rate_limit, exchange, profile, panel = _token_exchange_patches({"id": 1, "user": 64381531})
        with rate_limit, exchange, profile, panel:
            response = await callback("test-code", _callback_request(), Response(), db_session)

        assert response.status_code == 302
        users = list((await db_session.execute(select(User))).scalars())
        assert len(users) == 1
        assert users[0].id == existing_id
        assert decrypt_token(users[0].access_token) == "access"
        assert decrypt_token(users[0].refresh_token) == "refresh"

    @pytest.mark.asyncio
    async def test_callback_rejects_profile_without_user_id(self, db_session):
        """Regression: профиль без поля `user` не должен превращаться в id=1."""
        rate_limit, exchange, profile, panel = _token_exchange_patches({"id": 1, "first_name": "Test"})
        with rate_limit, exchange, profile, panel, pytest.raises(HTTPException) as exc_info:
            await callback("test-code", _callback_request(), Response(), db_session)

        assert exc_info.value.status_code == 401
        users = list((await db_session.execute(select(User))).scalars())
        assert users == []

    @pytest.mark.asyncio
    async def test_callback_rejects_empty_profile(self, db_session):
        rate_limit, exchange, profile, panel = _token_exchange_patches({})
        with rate_limit, exchange, profile, panel, pytest.raises(HTTPException) as exc_info:
            await callback("test-code", _callback_request(), Response(), db_session)

        assert exc_info.value.status_code == 401
        assert list((await db_session.execute(select(User))).scalars()) == []

    @pytest.mark.asyncio
    async def test_callback_rejects_foreign_stepik_account(self, db_session):
        """Панель настроена на одного автора: чужой аккаунт не создаёт запись."""
        rate_limit, exchange, profile, panel = _token_exchange_patches(
            {"id": 1, "user": 99999999}, panel_owner=64381531
        )
        with rate_limit, exchange, profile, panel, pytest.raises(HTTPException) as exc_info:
            await callback("test-code", _callback_request(), Response(), db_session)

        assert exc_info.value.status_code == 403
        assert list((await db_session.execute(select(User))).scalars()) == []


class TestSessionRefresh:
    """Regression: старый session-token после refresh оставался валидным через
    60 секунд — blacklist жил меньше, чем сама подпись токена."""

    async def _make_user(self, session):
        user = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("access"),
            refresh_token=encrypt_token("refresh"),
            token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
        )
        session.add(user)
        await session.commit()
        return user

    @staticmethod
    def _request_with_cookie(token: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/auth/refresh",
                "headers": [(b"cookie", f"stepik_session={token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )

    @pytest.mark.asyncio
    async def test_refresh_blacklists_old_token_for_full_session_ttl(self, db_session):
        from app.api import auth as auth_module

        user = await self._make_user(db_session)
        token = auth_module.create_session_token(str(user.id))
        request = self._request_with_cookie(token)

        with (
            patch("app.api.auth._is_blacklisted", new_callable=AsyncMock, return_value=False),
            patch("app.api.auth._blacklist_token", new_callable=AsyncMock) as blacklist,
        ):
            response = await auth_module.refresh_session(request, Response(), db_session)

        assert response.status_code == 200
        blacklist.assert_awaited_once()
        assert blacklist.await_args.args[0] == token
        assert blacklist.await_args.args[1] == auth_module._session_ttl_hours() * 3600

