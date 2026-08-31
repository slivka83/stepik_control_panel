import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rate_limiter import (
    acquire_token,
    check_auth_rate_limit,
    handle_rate_limit,
)


class TestHandleRateLimit:
    @pytest.mark.asyncio
    async def test_handle_rate_limit_sleeps(self):
        start = time.time()
        await handle_rate_limit(0.1)
        elapsed = time.time() - start
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_handle_rate_limit_zero(self):
        start = time.time()
        await handle_rate_limit(0)
        elapsed = time.time() - start
        assert elapsed < 0.1


class TestAcquireToken:
    @pytest.mark.asyncio
    async def test_token_available_returns_true(self):
        mock_script = AsyncMock(return_value=1)
        with patch("app.services.rate_limiter._token_bucket_script", mock_script):
            result = await acquire_token()
            assert result is True

    @pytest.mark.asyncio
    async def test_no_tokens_returns_false(self):
        mock_script = AsyncMock(return_value=0)
        with patch("app.services.rate_limiter._token_bucket_script", mock_script):
            result = await acquire_token()
            assert result is False

    @pytest.mark.asyncio
    async def test_redis_down_fail_open(self):
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_script = AsyncMock(side_effect=RedisConnectionError("Redis down"))
        with patch("app.services.rate_limiter._token_bucket_script", mock_script):
            result = await acquire_token()
            assert result is True


class TestCheckAuthRateLimit:
    @pytest.mark.asyncio
    async def test_under_limit_allowed(self):
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock()
        mock_pipe.zadd = MagicMock()
        mock_pipe.zcard = MagicMock()
        mock_pipe.expire = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[0, 1, 1, True])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.rate_limiter.redis_client", mock_redis):
            allowed, retry_after = await check_auth_rate_limit("127.0.0.1")
            assert allowed is True
            assert retry_after == 0

    @pytest.mark.asyncio
    async def test_over_limit_blocked(self):
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock()
        mock_pipe.zadd = MagicMock()
        mock_pipe.zcard = MagicMock()
        mock_pipe.expire = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[0, 1, 10, True])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.zrange = AsyncMock(return_value=[(b"123", 123.0)])

        with patch("app.services.rate_limiter.redis_client", mock_redis):
            allowed, retry_after = await check_auth_rate_limit("127.0.0.1", max_requests=5)
            assert allowed is False
            assert retry_after >= 1

    @pytest.mark.asyncio
    async def test_exactly_at_limit_allowed(self):
        """Regression: off-by-one — при max_requests=5 пятый запрос (count=5)
        должен проходить. Раньше сравнение `count >= max_requests` блокировало
        уже пятый запрос, и реальный лимит был 4/60с."""

        async def _check(count):
            mock_pipe = MagicMock()
            mock_pipe.execute = AsyncMock(return_value=[0, 1, count, True])
            mock_redis = MagicMock()
            mock_redis.pipeline.return_value = mock_pipe
            mock_redis.zrange = AsyncMock(return_value=[(b"123", 123.0)])
            with patch("app.services.rate_limiter.redis_client", mock_redis):
                return await check_auth_rate_limit("127.0.0.1", max_requests=5)

        assert (await _check(5))[0] is True, "пятый запрос (count=5) должен проходить при лимите 5"
        assert (await _check(6))[0] is False, "шестой запрос (count=6) должен блокироваться при лимите 5"

    @pytest.mark.asyncio
    async def test_redis_down_fail_open(self):
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=RedisConnectionError("down"))

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.rate_limiter.redis_client", mock_redis):
            allowed, retry_after = await check_auth_rate_limit("127.0.0.1")
            assert allowed is True
            assert retry_after == 0
