import asyncio
import logging
import threading
import time
import weakref
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


# ContextVar не подходит — set() внутри корутины меняет только копию контекста
# текущей задачи, и каждая задача обработки запроса создавала свой AsyncClient,
# который никто не закрывал (утечка соединений).
#
# Клиент хранится НА КАЖДЫЙ event loop: пул соединений httpx/anyio привязан к
# тому циклу, в котором был создан. sync_all_sync выполняется в отдельном цикле
# (asyncio.new_event_loop в потоке executor), и клиент, созданный основным циклом
# (например, при обновлении токена на старте), в цикле синка падал с
# "Event is bound to a different event loop".
_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient] = weakref.WeakKeyDictionary()
# Both the main loop and the sync thread may create clients concurrently.
_clients_lock = threading.Lock()


async def _get_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    with _clients_lock:
        client = _clients.get(loop)
        if client is None or client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
            client = httpx.AsyncClient(limits=limits, timeout=30.0)
            _clients[loop] = client
    return client


async def close_client() -> None:
    """Закрыть httpx-клиент текущего event loop (вызывается при остановке
    приложения и в конце потока синка). Клиент чужого цикла закрыть отсюда
    нельзя — пул соединений привязан к своему циклу."""
    loop = asyncio.get_running_loop()
    with _clients_lock:
        client = _clients.pop(loop, None)
    if client is not None:
        await client.aclose()


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

    # Token bucket: wait for a free slot instead of sending immediately after a
    # fixed 1s pause (the old code could still exceed the upstream limit).
    while not await acquire_token():
        await handle_rate_limit(0.5)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    client = await _get_client()
    try:
        response = await client.request(
            method=method,
            url=f"{STEPIK_API_BASE}{path}",
            headers=headers,
            params=params,
        )
    except httpx.TransportError as e:
        # Долгий sync (десятки тысяч запросов) не должен падать из-за одного
        # ReadTimeout/обрыва соединения — повторяем с backoff, как для 429/5xx.
        if retries >= MAX_RETRIES:
            raise StepikAPIError(
                0,
                f"network error after {MAX_RETRIES} retries: {type(e).__name__}: {e}",
            ) from e
        wait = 2**retries
        logger.warning(
            "Network error on %s (%s: %s), retry %d/%d after %ds",
            path,
            type(e).__name__,
            e,
            retries + 1,
            MAX_RETRIES,
            wait,
        )
        await asyncio.sleep(wait)
        return await _request(method, path, token, params, retries + 1)

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

    try:
        return response.json()
    except ValueError as e:
        # 200 с обрезанным/HTML-телом (прокси, обрыв) не должен убивать
        # многочасовой sync без повтора.
        if retries >= MAX_RETRIES:
            raise StepikAPIError(0, f"invalid JSON after {MAX_RETRIES} retries: {e}") from e
        wait = 2**retries
        logger.warning("Invalid JSON on %s, retry %d/%d after %ds", path, retries + 1, MAX_RETRIES, wait)
        await asyncio.sleep(wait)
        return await _request(method, path, token, params, retries + 1)


async def get_user_profile(token: str) -> dict:
    """Fetch the authenticated user's own Stepik account.

    Uses ``/stepics/1`` — the canonical "current user" endpoint, which always
    returns the token owner (``user`` is the real user id, ``id`` is the
    profile id). Do not fall back to the bare ``/users`` list: it is not
    filtered by the token and its first row is an arbitrary user (id 1).
    Regression: that fallback created phantom accounts on login.
    """
    data = await _request("GET", "/stepics/1", token)
    stepics = data.get("stepics", []) if isinstance(data, dict) else []
    if isinstance(stepics, list):
        return stepics[0] if stepics and isinstance(stepics[0], dict) else {}
    if isinstance(stepics, dict):
        return stepics
    return {}


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
# A module-level asyncio.Lock binds to the first event loop that waits on it;
# the finance token is requested from the sync thread's loop, so a lock shared
# across loops raised "is bound to a different event loop". One lock per loop.
_finance_token_locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = weakref.WeakKeyDictionary()
_finance_locks_guard = threading.Lock()


def _finance_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    with _finance_locks_guard:
        lock = _finance_token_locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            _finance_token_locks[loop] = lock
        return lock


async def get_finance_token(client_id: str, client_secret: str) -> str:
    """Get or refresh finance API token using client_credentials grant.

    Caches the token until 60s before expiry; one in-flight request per loop.
    """
    async with _finance_lock():
        now = time.time()
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
                if response.status_code in (401, 403):
                    _finance_token_cache["token"] = None
                    _finance_token_cache["expires_at"] = 0
                raise StepikAPIError(response.status_code, response.text)
            data = response.json()
            token = data.get("access_token")
            if not token:
                raise StepikAPIError(response.status_code, "no access_token in finance response")
            try:
                expires_in = int(data.get("expires_in") or 36000)
            except (TypeError, ValueError):
                expires_in = 36000
            _finance_token_cache["token"] = token
            _finance_token_cache["expires_at"] = now + expires_in
            return token
