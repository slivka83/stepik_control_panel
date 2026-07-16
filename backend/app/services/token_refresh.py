import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.models import User
from app.services.crypto import encrypt_token, decrypt_token
from app.services.stepik_api import refresh_access_token

logger = logging.getLogger(__name__)


async def refresh_user_tokens():
    """Refresh all user access tokens that expire within 15 minutes."""
    settings = get_settings()
    try:
        async with async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

            for user in users:
                try:
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
                    user.token_expires_at = (
                        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    ).replace(tzinfo=None)
                    logger.info("Token refreshed for user %s", user.stepik_id)
                except Exception as e:
                    logger.warning("Failed to refresh token for user %s: %s", user.stepik_id, e)

            await session.commit()
    except Exception as e:
        logger.error("Token refresh task failed: %s", e)
