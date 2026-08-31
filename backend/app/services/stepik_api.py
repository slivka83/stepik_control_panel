import asyncio
import logging
import time
from typing import Any

import httpx

from app.services.rate_limiter import acquire_token, handle_rate_limit

STEPIK_API_BASE = "https://stepik.org/api"
STEPIK_OAUTH_TOKEN_URL = "https://stepik.org/oauth2/token/"
MAX_RETRIES = 5

logger = logging.getLogger(__name__)


class StepikAPIError(Exception):
    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Stepik API error {status_code}: {detail}")


class StepikRateLimitError(StepikAPIError):
    def __init__(self, detail: str = ""):
        super().__init__(429, detail)


# Module-level singleton: ContextVar не подходит — set() внутри корутины
# меняет только копию контекста текущей задачи, и каждая задача обработки
# запроса создавала свой AsyncClient, который никто не закрывал (утечка
# соединений). Один клиент потокобезопасен для конкурентных запросов.
_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
                _client = httpx.AsyncClient(limits=limits, timeout=30.0)
    return _client


async def close_client() -> None:
    """Закрыть общий httpx-клиент (вызывается при остановке приложения)."""
    global _client
    async with _client_lock:
        if _client is not None:
            await _client.aclose()
            _client = None


async def _request(
    method: str,
    path: str,
    token: str | None = None,
    params: dict | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    """Make a GET request to Stepik API with retry on 429/5xx.

    Flow:
    1. Acquire rate-limit token from Redis bucket
    2. Send GET request with Bearer token
    3. On 429: sleep with exponential backoff, retry (max MAX_RETRIES)
    4. On 5xx: sleep with exponential backoff, retry (max MAX_RETRIES)
    5. After MAX_RETRIES: raise StepikRateLimitError
    """
    if method.upper() != "GET":
        raise ValueError("Only GET requests are allowed to Stepik API (Zero-Write Policy)")

    if not await acquire_token():
        await handle_rate_limit(1.0)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    client = await _get_client()
    response = await client.request(
        method=method,
        url=f"{STEPIK_API_BASE}{path}",
        headers=headers,
        params=params,
    )

    if response.status_code == 429:
        if retries >= MAX_RETRIES:
            raise StepikRateLimitError(f"Exceeded {MAX_RETRIES} retries for {path}")
        try:
            retry_after_header = int(response.headers.get("Retry-After", 2**retries))
        except (ValueError, TypeError):
            retry_after_header = 2**retries
        # Respect the server's Retry-After, but cap to avoid hanging forever.
        retry_after = min(retry_after_header, 300)
        logger.warning("Rate limited on %s, retry %d/%d after %ds", path, retries + 1, MAX_RETRIES, retry_after)
        await asyncio.sleep(retry_after)
        return await _request(method, path, token, params, retries + 1)

    if response.status_code >= 500 and retries < MAX_RETRIES:
        wait = 2**retries
        logger.warning(
            "Server error %d on %s, retry %d/%d after %ds",
            response.status_code,
            path,
            retries + 1,
            MAX_RETRIES,
            wait,
        )
        await asyncio.sleep(wait)
        return await _request(method, path, token, params, retries + 1)

    if response.status_code >= 400:
        raise StepikAPIError(response.status_code, response.text)

    return response.json()


async def get_user_profile(token: str) -> dict:
    """Fetch authenticated user's profile from Stepik."""
    data = await _request("GET", "/profiles", token)
    profiles = data.get("profiles", [])
    if profiles:
        return profiles[0]
    users_data = await _request("GET", "/users", token)
    users = users_data.get("users", [])
    return users[0] if users else {}


async def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    """Exchange refresh_token for a new access_token via Stepik OAuth2."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            STEPIK_OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "read",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        return response.json()


async def exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange OAuth2 authorization code for access/refresh tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            STEPIK_OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "scope": "read",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        return response.json()


_finance_token_cache: dict[str, Any] = {"token": None, "expires_at": 0}
_finance_token_lock = asyncio.Lock()


async def get_finance_token(client_id: str, client_secret: str) -> str:
    """Get or refresh finance API token using client_credentials grant.

    Uses asyncio.Lock to be thread-safe across concurrent async contexts.
    Caches token until 60s before expiry.
    """
    now = time.time()
    async with _finance_token_lock:
        if _finance_token_cache["token"] and _finance_token_cache["expires_at"] > now + 60:
            return _finance_token_cache["token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            STEPIK_OAUTH_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "read",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        data = response.json()
        token = data.get("access_token", "")
        expires_in = data.get("expires_in", 36000)
        async with _finance_token_lock:
            _finance_token_cache["token"] = token
            _finance_token_cache["expires_at"] = now + expires_in
        return token
