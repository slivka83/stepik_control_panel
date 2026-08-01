import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.services.crypto import encrypt_token
from app.services.rate_limiter import check_auth_rate_limit
from app.services.stepik_api import exchange_code_for_token, get_user_profile

router = APIRouter(prefix="/api/auth", tags=["auth"])

settings = get_settings()
logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "stepik_session"
STATE_COOKIE_NAME = "oauth_state"
STATE_TTL_SECONDS = 300
BLACKLIST_KEY_PREFIX = "session:blacklist:"


def _session_ttl_hours() -> int:
    return settings.session_ttl_hours


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key)


def create_session_token(user_id: str) -> str:
    serializer = _get_serializer()
    return serializer.dumps(user_id, salt="session")


def verify_session_token(token: str) -> str | None:
    serializer = _get_serializer()
    try:
        user_id = serializer.loads(
            token,
            salt="session",
            max_age=_session_ttl_hours() * 3600,
        )
        return user_id
    except (BadSignature, SignatureExpired):
        return None


def _get_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def _is_blacklisted(token: str) -> bool:
    try:
        from app.services.rate_limiter import redis_client

        return bool(await redis_client.get(f"{BLACKLIST_KEY_PREFIX}{token}"))
    except Exception:
        return False


async def _blacklist_token(token: str, ttl_seconds: int) -> None:
    try:
        from app.services.rate_limiter import redis_client

        await redis_client.setex(f"{BLACKLIST_KEY_PREFIX}{token}", ttl_seconds, "1")
    except Exception as e:
        logger.warning("Failed to blacklist token: %s", e)


async def get_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if await _is_blacklisted(token):
        raise HTTPException(status_code=401, detail="Session revoked")

    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=_session_ttl_hours() * 3600,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )


def _generate_state() -> str:
    return secrets.token_urlsafe(32)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/login")
async def login(request: Request, response: Response):
    ip = _get_client_ip(request)
    allowed, retry_after = await check_auth_rate_limit(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many auth attempts",
            headers={"Retry-After": str(retry_after)},
        )

    state = _generate_state()
    params = {
        "response_type": "code",
        "client_id": settings.stepik_client_id,
        "redirect_uri": settings.stepik_redirect_uri,
        "scope": "read",
        "state": state,
    }
    url = f"https://stepik.org/oauth2/authorize/?{urlencode(params)}"

    resp = RedirectResponse(url=url, status_code=302)
    resp.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/callback")
async def callback(
    code: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = _get_client_ip(request)
    allowed, retry_after = await check_auth_rate_limit(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many auth attempts",
            headers={"Retry-After": str(retry_after)},
        )

    expected_state = request.cookies.get(STATE_COOKIE_NAME)
    actual_state = request.query_params.get("state")

    if not expected_state or not actual_state or expected_state != actual_state:
        raise HTTPException(status_code=403, detail="Invalid OAuth state (CSRF detected)")

    token_data = await exchange_code_for_token(
        code=code,
        client_id=settings.stepik_client_id,
        client_secret=settings.stepik_client_secret,
        redirect_uri=settings.stepik_redirect_uri,
    )

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    profile = await get_user_profile(access_token)
    stepik_id = profile.get("id", 0)

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token)
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    result = await db.execute(select(User).where(User.stepik_id == stepik_id))
    user = result.scalar_one_or_none()

    if user:
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

    resp = RedirectResponse(url=settings.frontend_url, status_code=302)
    _set_session_cookie(resp, session_token)
    resp.delete_cookie(
        key=STATE_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )
    return resp


@router.get("/me")
async def get_me(user: User = Depends(get_user)):
    return {
        "id": str(user.id),
        "stepik_id": user.stepik_id,
        "authenticated": True,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = _get_token_from_request(request)
    if token:
        await _blacklist_token(token, _session_ttl_hours() * 3600)
    resp = Response(status_code=204)
    _clear_session_cookie(resp)
    return resp


@router.post("/refresh")
async def refresh_session(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Refresh the session token (extends TTL)."""
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if await _is_blacklisted(token):
        raise HTTPException(status_code=401, detail="Session revoked")

    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    await _blacklist_token(token, 60)

    new_token = create_session_token(str(user.id))
    resp = Response(status_code=200, content='{"status":"ok"}', media_type="application/json")
    _set_session_cookie(resp, new_token)
    return resp
