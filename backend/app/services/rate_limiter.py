"""Redis-backed token bucket rate limiter for Stepik API.

Uses an atomic Lua script to avoid race conditions in GET-then-SET pattern.
Fails open (allows requests) when Redis is unavailable.
"""

import asyncio
import logging
import threading
import time

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

_sync_thread_local = threading.local()

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


async def acquire_token() -> bool:
    """Try to acquire a token from the bucket. Fails open if Redis is down."""
    if getattr(_sync_thread_local, "skip_rate_limit", False):
        return True

    key = f"{TOKEN_BUCKET_KEY_PREFIX}tokens"
    last_refill_key = f"{TOKEN_BUCKET_KEY_PREFIX}last_refill"
    now = time.time()

    try:
        result = await _token_bucket_script(
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
        pipe = redis_client.pipeline()
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
            oldest_in_window = await redis_client.zrange(key, 0, 0, withscores=True)
            if oldest_in_window:
                oldest_ts = oldest_in_window[0][1]
                retry_after = int(oldest_ts + window_seconds - now) + 1
                return False, max(retry_after, 1)
            return False, window_seconds
        return True, 0
    except (RedisError, RedisConnectionError) as e:
        logger.warning("Redis unavailable, allowing auth request (fail-open): %s", e)
        return True, 0
