import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.models import User
from app.services.crypto import decrypt_token, encrypt_token


class TestTokenRefresh:
    async def test_skips_users_with_valid_token(self, db_session):
        from app.services.token_refresh import refresh_user_tokens

        future = (datetime.now(UTC) + timedelta(hours=2)).replace(tzinfo=None)
        user = User(
            id=uuid.uuid4(),
            stepik_id=123,
            access_token=encrypt_token("access"),
            refresh_token=encrypt_token("refresh"),
            token_expires_at=future,
        )
        db_session.add(user)
        await db_session.commit()

        @asynccontextmanager
        async def mock_session():
            yield db_session

        with patch("app.services.token_refresh.async_session", mock_session):
            await refresh_user_tokens()

        await db_session.refresh(user)
        assert decrypt_token(user.access_token) == "access"

    async def test_refreshes_expiring_token(self, db_session):
        from app.services.token_refresh import refresh_user_tokens

        expiring = (datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None)
        user = User(
            id=uuid.uuid4(),
            stepik_id=456,
            access_token=encrypt_token("old_access"),
            refresh_token=encrypt_token("old_refresh"),
            token_expires_at=expiring,
        )
        db_session.add(user)
        await db_session.commit()

        @asynccontextmanager
        async def mock_session():
            yield db_session

        with patch("app.services.token_refresh.async_session", mock_session):
            with patch("app.services.token_refresh.refresh_access_token", new_callable=AsyncMock) as mock_refresh:
                mock_refresh.return_value = {
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",
                    "expires_in": 3600,
                }
                await refresh_user_tokens()

        await db_session.refresh(user)
        assert decrypt_token(user.access_token) == "new_access"
        assert decrypt_token(user.refresh_token) == "new_refresh"

    async def test_handles_refresh_failure_gracefully(self, db_session):
        from app.services.stepik_api import StepikAPIError
        from app.services.token_refresh import refresh_user_tokens

        expiring = (datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None)
        user = User(
            id=uuid.uuid4(),
            stepik_id=789,
            access_token=encrypt_token("old_access"),
            refresh_token=encrypt_token("bad_refresh"),
            token_expires_at=expiring,
        )
        db_session.add(user)
        await db_session.commit()

        @asynccontextmanager
        async def mock_session():
            yield db_session

        with patch("app.services.token_refresh.async_session", mock_session):
            with patch("app.services.token_refresh.refresh_access_token", new_callable=AsyncMock) as mock_refresh:
                mock_refresh.side_effect = StepikAPIError(400, "Invalid")
                await refresh_user_tokens()

        await db_session.refresh(user)
        assert decrypt_token(user.access_token) == "old_access"
