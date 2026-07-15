import asyncio
import time

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

TOKEN_BUCKET_KEY_PREFIX = "rate_limit:stepik:"
TOKEN_BUCKET_CAPACITY = 10
TOKEN_BUCKET_REFILL_RATE = 2


async def acquire_token() -> bool:
    key = f"{TOKEN_BUCKET_KEY_PREFIX}tokens"
    now = time.time()

    pipe = redis_client.pipeline()
    pipe.get(key)
    pipe.get(f"{TOKEN_BUCKET_KEY_PREFIX}last_refill")
    results = await pipe.execute()

    current_tokens = float(results[0]) if results[0] else TOKEN_BUCKET_CAPACITY
    last_refill = float(results[1]) if results[1] else now

    elapsed = now - last_refill
    current_tokens = min(TOKEN_BUCKET_CAPACITY, current_tokens + elapsed * TOKEN_BUCKET_REFILL_RATE)

    if current_tokens >= 1:
        current_tokens -= 1
        pipe = redis_client.pipeline()
        pipe.set(key, str(current_tokens))
        pipe.set(f"{TOKEN_BUCKET_KEY_PREFIX}last_refill", str(now))
        await pipe.execute()
        return True

    return False


async def handle_rate_limit(retry_after: float) -> None:
    await asyncio.sleep(retry_after)
