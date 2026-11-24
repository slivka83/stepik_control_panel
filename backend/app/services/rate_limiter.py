"""Redis-backed token bucket rate limiter for Stepik API.

Uses an atomic Lua script to avoid race conditions in GET-then-SET pattern.
Fails open (allows requests) when Redis is unavailable.
"""

import asyncio
import logging
import threading
import time
import weakref

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# Redis asyncio-клиент привязан к event loop, в котором создал соединения.
# Синхронизация выполняется в отдельном потоке/цикле, поэтому у каждого цикла
# свой клиент и свой Lua-скрипт (раньше sync просто выключал rate limiter).
_main_loop: asyncio.AbstractEventLoop | None = None
_loop_clients: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_loop_scripts: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_loop_lock = threading.Lock()

TOKEN_BUCKET_KEY_PREFIX = "rate_limit:stepik:"
TOKEN_BUCKET_CAPACITY = 10
TOKEN_BUCKET_REFILL_RATE = 2

LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local last_refill_key = KEYS[2]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local current_tokens = tonumber(redis.call('GET', key)) or max_tokens
local last_refill = tonumber(redis.call('GET', last_refill_key)) or now

local elapsed = now - last_refill
current_tokens = math.min(max_tokens, current_tokens + elapsed * refill_rate)

if current_tokens >= 1 then
    current_tokens = current_tokens - 1
    redis.call('SET', key, tostring(current_tokens))
    redis.call('SET', last_refill_key, tostring(now))
    redis.call('EXPIRE', key, 60)
    redis.call('EXPIRE', last_refill_key, 60)
    return 1
else
    redis.call('SET', key, tostring(current_tokens))
    redis.call('SET', last_refill_key, tostring(now))
    redis.call('EXPIRE', key, 60)
    redis.call('EXPIRE', last_refill_key, 60)
    return 0
end
"""

_token_bucket_script = redis_client.register_script(LUA_TOKEN_BUCKET)
_default_redis = redis_client
_default_script = _token_bucket_script


def bind_main_loop() -> None:
    """Запомнить event loop приложения.

    Вызывается из lifespan ДО первого синка. Без этого «главным» становился
    первый цикл, который обратился к Redis: если это был поток синка, главный
    цикл позже получал клиент/скрипт, привязанный к уже закрытому циклу.
    """
    global _main_loop
    if redis_client is not _default_redis:
        return
    loop = asyncio.get_running_loop()
    with _loop_lock:
        if _main_loop is None or _main_loop.is_closed():
            _main_loop = loop


def _get_redis():
    """Redis-клиент текущего event loop (main loop — общий, sync — свой)."""
    global _main_loop
    if redis_client is not _default_redis:
        return redis_client
    loop = asyncio.get_running_loop()
    with _loop_lock:
        if _main_loop is None or _main_loop.is_closed():
            _main_loop = loop
        if loop is _main_loop:
            return redis_client
        client = _loop_clients.get(loop)
        if client is None:
            client = redis.from_url(settings.redis_url, decode_responses=True)
            _loop_clients[loop] = client
        return client


def _get_token_bucket_script():
    global _main_loop
    if _token_bucket_script is not _default_script:
        return _token_bucket_script
    loop = asyncio.get_running_loop()
    with _loop_lock:
        if _main_loop is None or _main_loop.is_closed():
            _main_loop = loop
        main_loop = _main_loop
    if loop is main_loop:
        return _token_bucket_script
    client = _get_redis()
    with _loop_lock:
        script = _loop_scripts.get(loop)
        if script is None:
            script = client.register_script(LUA_TOKEN_BUCKET)
            _loop_scripts[loop] = script
        return script


async def close_redis() -> None:
    """Close the Redis client belonging to the current event loop."""
    loop = asyncio.get_running_loop()
    with _loop_lock:
        client = _loop_clients.pop(loop, None)
        _loop_scripts.pop(loop, None)
        main_loop = _main_loop
    if client is not None:
        await client.aclose()
    # The main loop uses the module-level client; close it on shutdown too.
    if loop is main_loop and redis_client is _default_redis:
        await redis_client.aclose()


async def acquire_token() -> bool:
    """Try to acquire a token from the bucket. Fails open if Redis is down."""
    key = f"{TOKEN_BUCKET_KEY_PREFIX}tokens"
    last_refill_key = f"{TOKEN_BUCKET_KEY_PREFIX}last_refill"
    now = time.time()

    try:
        result = await _get_token_bucket_script()(
            keys=[key, last_refill_key],
            args=[TOKEN_BUCKET_CAPACITY, TOKEN_BUCKET_REFILL_RATE, now],
        )
        return bool(result)
    except (RedisError, RedisConnectionError) as e:
        logger.warning("Redis unavailable, allowing request (fail-open): %s", e)
        return True


async def handle_rate_limit(retry_after: float) -> None:
    """Sleep for retry_after seconds when rate limited by upstream."""
    await asyncio.sleep(retry_after)


async def check_auth_rate_limit(ip: str, max_requests: int = 5, window_seconds: int = 60) -> tuple[bool, int]:
    """Rate limit for auth endpoints: max_requests per window per IP.

    Returns (allowed, retry_after_seconds). Fails open if Redis is down.
    """
    key = f"rate_limit:auth:{ip}"
    now = time.time()
    window_start = now - window_seconds

    try:
        client = _get_redis()
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        count = results[2]

        # Текущий запрос уже учтён в count (zadd выше): при лимите 5
        # пятый запрос видит count=5 и должен проходить, шестой (6) — нет.
        # Раньше сравнение было >= и реально допускало только 4 запроса.
        if count > max_requests:
            oldest_in_window = await client.zrange(key, 0, 0, withscores=True)
            if oldest_in_window:
                oldest_ts = oldest_in_window[0][1]
                retry_after = int(oldest_ts + window_seconds - now) + 1
                return False, max(retry_after, 1)
            return False, window_seconds
        return True, 0
    except (RedisError, RedisConnectionError) as e:
        logger.warning("Redis unavailable, allowing auth request (fail-open): %s", e)
        return True, 0
