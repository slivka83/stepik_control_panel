import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from app.services.stepik_api import (
    _request, get_course, get_courses_batch, get_sections,
    get_units, get_steps, get_course_grades, get_wrong_submissions,
    exchange_code_for_token, StepikAPIError, STEPIK_API_BASE
)


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
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

                result = await _request("get", "/courses/1")
                assert result == {"courses": [{"id": 1}]}

    @pytest.mark.asyncio
    async def test_get_uppercase_works(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"courses": [{"id": 1}]}
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

                result = await _request("GET", "/courses/1")
                assert result == {"courses": [{"id": 1}]}


class TestRateLimitHandling:
    @pytest.mark.asyncio
    async def test_429_retries_with_sleep(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('app.services.stepik_api.handle_rate_limit', new_callable=AsyncMock) as mock_handle:
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_429 = MagicMock()
                    mock_response_429.status_code = 429
                    mock_response_429.headers = {"Retry-After": "2"}

                    mock_response_200 = MagicMock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {"data": "ok"}

                    mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                    mock_client.request = AsyncMock(side_effect=[mock_response_429, mock_response_200])

                    result = await _request("GET", "/test")
                    mock_handle.assert_called_once_with(2.0)
                    assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_429_default_retry_after(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('app.services.stepik_api.handle_rate_limit', new_callable=AsyncMock) as mock_handle:
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response_429 = MagicMock()
                    mock_response_429.status_code = 429
                    mock_response_429.headers = {}

                    mock_response_200 = MagicMock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {}

                    mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                    mock_client.request = AsyncMock(side_effect=[mock_response_429, mock_response_200])

                    await _request("GET", "/test")
                    mock_handle.assert_called_once_with(5.0)


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_400_raises_error(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 400
                mock_response.text = "Bad Request"
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

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
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

                with pytest.raises(StepikAPIError):
                    await _request("GET", "/test")

    @pytest.mark.asyncio
    async def test_500_raises_error(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

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
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

                await _request("GET", "/test", token="my_token_123")

                call_kwargs = mock_client.request.call_args[1]
                assert call_kwargs["headers"]["Authorization"] == "Bearer my_token_123"

    @pytest.mark.asyncio
    async def test_no_token_no_auth_header(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

                await _request("GET", "/test")

                call_kwargs = mock_client.request.call_args[1]
                assert "Authorization" not in call_kwargs["headers"]


class TestBatchLoading:
    @pytest.mark.asyncio
    async def test_batch_uses_ids_param(self):
        with patch('app.services.stepik_api.acquire_token', new_callable=AsyncMock, return_value=True):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"courses": [{"id": 1}, {"id": 2}]}
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.request = AsyncMock(return_value=mock_response)

                result = await get_courses_batch([1, 2])

                call_kwargs = mock_client.request.call_args[1]
                assert call_kwargs["params"] == {"ids[]": [1, 2]}


class TestEndpointFunctions:
    @pytest.mark.asyncio
    async def test_get_course(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"courses": [{"id": 1, "title": "Test"}]}
            result = await get_course(1)
            assert result == {"id": 1, "title": "Test"}
            mock_req.assert_called_once_with("GET", "/courses/1", None)

    @pytest.mark.asyncio
    async def test_get_sections(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"sections": [{"id": 1}]}
            result = await get_sections(1)
            assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_get_units(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"units": [{"id": 1}]}
            result = await get_units(1)
            assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_get_steps(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"steps": [{"id": 1}]}
            result = await get_steps(1)
            assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_get_course_grades(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"course-grades": [{"student": 1}]}
            result = await get_course_grades(1)
            assert result == [{"student": 1}]

    @pytest.mark.asyncio
    async def test_get_wrong_submissions(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"submissions": [{"id": 1}]}
            result = await get_wrong_submissions(1)
            assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_get_course_empty_response(self):
        with patch('app.services.stepik_api._request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            result = await get_course(1)
            assert result == {}


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
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await exchange_code_for_token("code123", "client_id", "client_secret")

            assert result["access_token"] == "test_access"
            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["data"]["scope"] == "read"
            assert call_kwargs["data"]["grant_type"] == "authorization_code"

    @pytest.mark.asyncio
    async def test_exchange_failure(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid code"
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(StepikAPIError):
                await exchange_code_for_token("bad_code", "client_id", "client_secret")
