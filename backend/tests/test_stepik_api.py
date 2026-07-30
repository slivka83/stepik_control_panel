import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from app.services.stepik_api import (
    _request,
    get_user_profile, refresh_access_token,
    exchange_code_for_token, StepikAPIError, STEPIK_API_BASE
)


def _mock_request_client(mock_client_class, mock_response):
    """Set up httpx.AsyncClient mock for _request tests.
    _request uses _get_client() which calls httpx.AsyncClient() and 
    uses the returned client directly (not as context manager).
    """
    instance = mock_client_class.return_value
    instance.request = AsyncMock(return_value=mock_response)
    return instance


def _mock_async_client(mock_client_class, mock_response):
    """Set up httpx.AsyncClient mock for functions using async with."""
    instance = mock_client_class.return_value
    instance.__aenter__.return_value = instance
    instance.post = AsyncMock(return_value=mock_response)
    return instance


class TestRequestGuard:
    @pytest.mark.asyncio
    async def test_post_raises_value_error(self):
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("POST", "/courses/1")

    @pytest.mark.asyncio
    async def test_put_raises_value_error(self):
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("PUT", "/courses/1")

    @pytest.mark.asyncio
    async def test_patch_raises_value_error(self):
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("PATCH", "/courses/1")

    @pytest.mark.asyncio
    async def test_delete_raises_value_error(self):
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("DELETE", "/courses/1")

    @pytest.mark.asyncio
    async def test_get_lowercase_works(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"courses": [{"id": 1}]}
                _mock_request_client(mock_client, mock_response)

                result = await _request("get", "/courses/1")
                assert result == {"courses": [{"id": 1}]}

    @pytest.mark.asyncio
    async def test_get_uppercase_works(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"courses": [{"id": 1}]}
                _mock_request_client(mock_client, mock_response)

                result = await _request("GET", "/courses/1")
                assert result == {"courses": [{"id": 1}]}


class TestRateLimitHandling:
    @pytest.mark.asyncio
    async def test_429_retries_with_sleep(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_429 = MagicMock()
                    mock_response_429.status_code = 429
                    mock_response_429.headers = {"Retry-After": "2"}

                    mock_response_200 = MagicMock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {"data": "ok"}

                    instance = mock_client.return_value
                    instance.request = AsyncMock(side_effect=[mock_response_429, mock_response_200])

                    result = await _request("GET", "/test")
                    mock_sleep.assert_called_once_with(1)
                    assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_429_default_retry_after(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_429 = MagicMock()
                    mock_response_429.status_code = 429
                    mock_response_429.headers = {}

                    mock_response_200 = MagicMock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {}

                    instance = mock_client.return_value
                    instance.request = AsyncMock(side_effect=[mock_response_429, mock_response_200])

                    await _request("GET", "/test")
                    mock_sleep.assert_called_once_with(1)


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_400_raises_error(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 400
                mock_response.text = "Bad Request"
                _mock_request_client(mock_client, mock_response)

                with pytest.raises(StepikAPIError) as exc_info:
                    await _request("GET", "/test")
                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_401_raises_error(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_response.text = "Unauthorized"
                _mock_request_client(mock_client, mock_response)

                with pytest.raises(StepikAPIError):
                    await _request("GET", "/test")

    @pytest.mark.asyncio
    async def test_500_raises_error(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                _mock_request_client(mock_client, mock_response)

                with pytest.raises(StepikAPIError):
                    await _request("GET", "/test")


class TestTokenAuth:
    @pytest.mark.asyncio
    async def test_token_added_to_headers(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                inst = _mock_request_client(mock_client, mock_response)

                await _request("GET", "/test", token="my_token_123")

                call_kwargs = inst.request.call_args[1]
                assert call_kwargs["headers"]["Authorization"] == "Bearer my_token_123"

    @pytest.mark.asyncio
    async def test_no_token_no_auth_header(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                inst = _mock_request_client(mock_client, mock_response)

                await _request("GET", "/test")

                call_kwargs = inst.request.call_args[1]
                assert "Authorization" not in call_kwargs["headers"]


class TestExchangeCodeForToken:
    @pytest.mark.asyncio
    async def test_exchange_success(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "test_access",
                "refresh_token": "test_refresh",
                "expires_in": 3600
            }
            _mock_async_client(mock_client, mock_response)

            result = await exchange_code_for_token(
                "code123", "client_id", "client_secret", "http://localhost:3000/api/auth/callback"
            )

            assert result["access_token"] == "test_access"
            call_kwargs = mock_client.return_value.post.call_args[1]
            assert call_kwargs["data"]["scope"] == "read"
            assert call_kwargs["data"]["grant_type"] == "authorization_code"
            assert call_kwargs["data"]["redirect_uri"] == "http://localhost:3000/api/auth/callback"

    @pytest.mark.asyncio
    async def test_exchange_failure(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid code"
            _mock_async_client(mock_client, mock_response)

            with pytest.raises(StepikAPIError):
                await exchange_code_for_token(
                    "bad_code", "client_id", "client_secret", "http://localhost:3000/api/auth/callback"
                )


class TestGetUserProfile:
    @pytest.mark.asyncio
    async def test_returns_profile_from_profiles_endpoint(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"profiles": [{"id": 123, "email": "test@test.com"}]}
            result = await get_user_profile("my_token")
            assert result == {"id": 123, "email": "test@test.com"}
            mock_req.assert_called_once_with("GET", "/profiles", "my_token")

    @pytest.mark.asyncio
    async def test_falls_back_to_users_endpoint(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [
                {"profiles": []},
                {"users": [{"id": 456, "first_name": "John"}]},
            ]
            result = await get_user_profile("my_token")
            assert result == {"id": 456, "first_name": "John"}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_data(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [{"profiles": []}, {"users": []}]
            result = await get_user_profile("my_token")
            assert result == {}


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_refresh_success(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            }
            _mock_async_client(mock_client, mock_response)

            result = await refresh_access_token("old_refresh", "client_id", "client_secret")
            assert result["access_token"] == "new_access"
            call_kwargs = mock_client.return_value.post.call_args[1]
            assert call_kwargs["data"]["grant_type"] == "refresh_token"
            assert call_kwargs["data"]["scope"] == "read"

    @pytest.mark.asyncio
    async def test_refresh_failure(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid refresh token"
            _mock_async_client(mock_client, mock_response)

            with pytest.raises(StepikAPIError):
                await refresh_access_token("bad_refresh", "client_id", "client_secret")
