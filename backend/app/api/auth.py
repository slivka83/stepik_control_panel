from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.models import User
from app.services.crypto import encrypt_token, decrypt_token
from app.services.stepik_api import exchange_code_for_token, get_user_profile, refresh_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

settings = get_settings()


def _sign_session(user_id: str) -> str:
    return hmac.new(
        settings.secret_key.encode(),
        user_id.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_session_token(user_id: str) -> str:
    return f"{user_id}.{_sign_session(user_id)}"


def verify_session_token(token: str) -> str | None:
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    user_id, sig = parts
    if hmac.compare_digest(sig, _sign_session(user_id)):
        return user_id
    return None


def _get_token_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    token = request.cookies.get("stepik_session")
    if token:
        return token
    return request.query_params.get("session_token")


async def get_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    token = _get_token_from_request(request)
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


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

    profile = await get_user_profile(access_token)
    stepik_id = profile.get("id", 0)

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).replace(tzinfo=None)

    result = await db.execute(select(User).where(User.stepik_id == stepik_id))
    user = result.scalar_one_or_none()

    if user:
        user.access_token = encrypted_access
        user.refresh_token = encrypted_refresh
        user.token_expires_at = expires_at
    else:
        result_all = await db.execute(select(User).limit(1))
        user = result_all.scalar_one_or_none()
        if user:
            user.stepik_id = stepik_id
            user.access_token = encrypted_access
            user.refresh_token = encrypted_refresh
            user.token_expires_at = expires_at
        else:
            user = User(
                stepik_id=stepik_id,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_expires_at=expires_at,
            )
            db.add(user)

    await db.commit()
    await db.refresh(user)

    session_token = create_session_token(str(user.id))
    return RedirectResponse(f"http://localhost:3000?session_token={session_token}")


@router.get("/me")
async def get_me(user: User = Depends(get_user)):
    return {
        "id": str(user.id),
        "stepik_id": user.stepik_id,
        "authenticated": True,
    }


@router.get("/logout")
async def logout():
    return {"ok": True}


@router.get("/token")
async def get_token(user: User = Depends(get_user)):
    return {"access_token": decrypt_token(user.access_token)}
