import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
DEFAULT_TTL = 300  # 5 minutes


def cached(key: str, ttl: int = DEFAULT_TTL) -> Any | None:
    if key in _cache:
        expires_at, value = _cache[key]
        if time.time() < expires_at:
            return value
        del _cache[key]
    return None


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL):
    _cache[key] = (time.time() + ttl, value)


def cache_clear():
    _cache.clear()
