import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models import User
from app.services.crypto import decrypt_token, encrypt_token
from app.services.stepik_api import refresh_access_token

logger = logging.getLogger(__name__)

TOKEN_EXPIRY_BUFFER_SECONDS = 900  # 15 minutes before expiry


async def refresh_user_tokens():
    """Refresh user access tokens that expire within 15 minutes.

    Each user is refreshed in a separate transaction so a failure for one
    user does not roll back successful refreshes for others.
    """
    settings = get_settings()
    try:
        async with async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            user_ids = [u.id for u in users]

        refreshed = 0
        for user_id in user_ids:
            try:
                async with async_session() as session:
                    user = await session.get(User, user_id)
                    if not user:
                        continue

                    now = datetime.now(UTC)
                    expires_at = user.token_expires_at
                    if expires_at:
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=UTC)
                        if expires_at > now + timedelta(seconds=TOKEN_EXPIRY_BUFFER_SECONDS):
                            continue

                    refresh_token = decrypt_token(user.refresh_token)
                    token_data = await refresh_access_token(
                        refresh_token=refresh_token,
                        client_id=settings.stepik_client_id,
                        client_secret=settings.stepik_client_secret,
                    )

                    new_access = token_data.get("access_token", "")
                    new_refresh = token_data.get("refresh_token", refresh_token)
                    expires_in = token_data.get("expires_in", 3600)

                    user.access_token = encrypt_token(new_access)
                    user.refresh_token = encrypt_token(new_refresh)
                    user.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
                    await session.commit()
                    refreshed += 1
                    logger.info("Token refreshed for user %s", user.stepik_id)
            except Exception as e:
                logger.warning("Failed to refresh token for user %s: %s", user_id, e)

        logger.info("Token refresh complete: %d refreshed", refreshed)
    except Exception as e:
        logger.error("Token refresh task failed: %s", e)
