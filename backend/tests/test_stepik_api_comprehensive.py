"""Comprehensive tests for Stepik API client: get_finance_token, 5xx retries."""
import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.stepik_api import (
    _request, get_finance_token, StepikAPIError,
    StepikRateLimitError, MAX_RETRIES, _finance_token_cache, _finance_token_lock,
)


class TestRequest5xxRetry:
    @pytest.mark.asyncio
    async def test_500_retries_and_succeeds(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_500 = MagicMock()
                    mock_response_500.status_code = 500
                    mock_response_500.text = "Server Error"

                    mock_response_200 = MagicMock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {"data": "ok"}

                    instance = mock_client.return_value
                    instance.request = AsyncMock(side_effect=[mock_response_500, mock_response_200])

                    result = await _request("GET", "/test")
                    assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_500_exhausts_retries(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_500 = MagicMock()
                    mock_response_500.status_code = 500
                    mock_response_500.text = "Server Error"

                    instance = mock_client.return_value
                    instance.request = AsyncMock(return_value=mock_response_500)

                    with pytest.raises(StepikAPIError) as exc_info:
                        await _request("GET", "/test")
                    assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_503_retries_and_succeeds(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_503 = MagicMock()
                    mock_response_503.status_code = 503

                    mock_response_200 = MagicMock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {"ok": True}

                    instance = mock_client.return_value
                    instance.request = AsyncMock(side_effect=[mock_response_503, mock_response_200])

                    result = await _request("GET", "/test")
                    assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_502_exhausts_retries(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_502 = MagicMock()
                    mock_response_502.status_code = 502
                    mock_response_502.text = "Bad Gateway"

                    instance = mock_client.return_value
                    instance.request = AsyncMock(return_value=mock_response_502)

                    with pytest.raises(StepikAPIError):
                        await _request("GET", "/test")


class TestStepikAPIConstants:
    def test_max_retries_is_5(self):
        assert MAX_RETRIES == 5

    def test_api_base_url(self):
        from app.services.stepik_api import STEPIK_API_BASE
        assert STEPIK_API_BASE == "https://stepik.org/api"

    def test_rate_limit_error_is_stepik_error(self):
        error = StepikRateLimitError("too many")
        assert error.status_code == 429
        assert isinstance(error, StepikAPIError)


class TestGetFinanceToken:
    def setup_method(self):
        _finance_token_cache["token"] = None
        _finance_token_cache["expires_at"] = 0

    @pytest.mark.asyncio
    async def test_first_call_fetches_token(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "finance_token_123",
                "expires_in": 36000,
            }
            instance = mock_client.return_value
            instance.__aenter__.return_value = instance
            instance.post = AsyncMock(return_value=mock_response)

            token = await get_finance_token("fin_client", "fin_secret")
            assert token == "finance_token_123"

            call_kwargs = instance.post.call_args[1]
            assert call_kwargs["data"]["grant_type"] == "client_credentials"
            assert call_kwargs["data"]["scope"] == "read"
            assert call_kwargs["data"]["client_id"] == "fin_client"
            assert call_kwargs["data"]["client_secret"] == "fin_secret"

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self):
        _finance_token_cache["token"] = "cached_token"
        _finance_token_cache["expires_at"] = time.time() + 36000

        with patch('httpx.AsyncClient') as mock_client:
            token = await get_finance_token("fin_client", "fin_secret")
            assert token == "cached_token"
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_refreshes_when_expired(self):
        _finance_token_cache["token"] = "expired_token"
        _finance_token_cache["expires_at"] = time.time() - 100

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "fresh_token",
                "expires_in": 36000,
            }
            instance = mock_client.return_value
            instance.__aenter__.return_value = instance
            instance.post = AsyncMock(return_value=mock_response)

            token = await get_finance_token("fin_client", "fin_secret")
            assert token == "fresh_token"

    @pytest.mark.asyncio
    async def test_refreshes_when_near_expiry(self):
        _finance_token_cache["token"] = "old_token"
        _finance_token_cache["expires_at"] = time.time() + 30

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "refreshed_token",
                "expires_in": 36000,
            }
            instance = mock_client.return_value
            instance.__aenter__.return_value = instance
            instance.post = AsyncMock(return_value=mock_response)

            token = await get_finance_token("fin_client", "fin_secret")
            assert token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid client"
            instance = mock_client.return_value
            instance.__aenter__.return_value = instance
            instance.post = AsyncMock(return_value=mock_response)

            with pytest.raises(StepikAPIError) as exc_info:
                await get_finance_token("bad_client", "bad_secret")
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_preserves_cache_after_refresh(self):
        _finance_token_cache["token"] = "old_token"
        _finance_token_cache["expires_at"] = time.time() - 100

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_token",
                "expires_in": 36000,
            }
            instance = mock_client.return_value
            instance.__aenter__.return_value = instance
            instance.post = AsyncMock(return_value=mock_response)

            await get_finance_token("fin_client", "fin_secret")
            assert _finance_token_cache["token"] == "new_token"
            assert _finance_token_cache["expires_at"] > time.time()

    @pytest.mark.asyncio
    async def test_fallback_expires_in(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "no_expiry_token",
            }
            instance = mock_client.return_value
            instance.__aenter__.return_value = instance
            instance.post = AsyncMock(return_value=mock_response)

            t0 = time.time()
            token = await get_finance_token("fin_client", "fin_secret")
            assert token == "no_expiry_token"
            assert _finance_token_cache["expires_at"] >= t0 + 36000 - 10
