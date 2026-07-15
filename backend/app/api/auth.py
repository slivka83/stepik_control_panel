from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.models import User
from app.services.crypto import encrypt_token, decrypt_token
from app.services.stepik_api import exchange_code_for_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

settings = get_settings()


async def get_user(db: AsyncSession = Depends(get_db)) -> User:
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.get("/login")
async def login():
    params = {
        "response_type": "code",
        "client_id": settings.stepik_client_id,
        "redirect_uri": settings.stepik_redirect_uri,
        "scope": "read",
    }
    return RedirectResponse(f"https://stepik.org/oauth2/authorize/?{urlencode(params)}")


@router.get("/callback")
async def callback(code: str, db: AsyncSession = Depends(get_db)):
    token_data = await exchange_code_for_token(
        code=code,
        client_id=settings.stepik_client_id,
        client_secret=settings.stepik_client_secret,
    )

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()

    if user:
        user.access_token = encrypted_access
        user.refresh_token = encrypted_refresh
        user.token_expires_at = expires_at
    else:
        user = User(
            stepik_id=0,
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            token_expires_at=expires_at,
        )
        db.add(user)

    await db.commit()
    return RedirectResponse("http://localhost:3000")


@router.get("/token")
async def get_token(user: User = Depends(get_user)):
    return {"access_token": decrypt_token(user.access_token)}
