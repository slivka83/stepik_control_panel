import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.rate_limiter import handle_rate_limit, TOKEN_BUCKET_CAPACITY


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
