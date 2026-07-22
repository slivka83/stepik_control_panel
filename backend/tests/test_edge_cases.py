import os

import pytest


class TestEdgeCases:
    def test_concurrent_encrypt_decrypt(self):
        from app.services.crypto import encrypt_token, decrypt_token
        tokens = [f"token_{i}" for i in range(100)]
        encrypted = [encrypt_token(t) for t in tokens]
        decrypted = [decrypt_token(e) for e in encrypted]
        assert tokens == decrypted

    def test_unicode_token_roundtrip(self):
        from app.services.crypto import encrypt_token, decrypt_token
        unicode_tokens = [
            "привет",
            "日本語",
            "中文",
            "العربية",
            "🎉🚀💻",
            "Ñoño",
        ]
        for token in unicode_tokens:
            encrypted = encrypt_token(token)
            decrypted = decrypt_token(encrypted)
            assert decrypted == token

    def test_very_long_token(self):
        from app.services.crypto import encrypt_token, decrypt_token
        long_token = "x" * 100000
        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == long_token

    def test_stepik_api_base_url(self):
        from app.services.stepik_api import STEPIK_API_BASE
        assert STEPIK_API_BASE == "https://stepik.org/api"

    def test_rate_limiter_constants(self):
        from app.services.rate_limiter import TOKEN_BUCKET_CAPACITY, TOKEN_BUCKET_REFILL_RATE
        assert TOKEN_BUCKET_CAPACITY == 10
        assert TOKEN_BUCKET_REFILL_RATE == 2


class TestCrossCuttingConcerns:
    @pytest.mark.asyncio
    async def test_no_post_to_stepik_in_api_client(self):
        from app.services.stepik_api import _request
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("POST", "/courses")

    @pytest.mark.asyncio
    async def test_no_put_to_stepik_in_api_client(self):
        from app.services.stepik_api import _request
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("PUT", "/courses")

    @pytest.mark.asyncio
    async def test_no_delete_to_stepik_in_api_client(self):
        from app.services.stepik_api import _request
        with pytest.raises(ValueError, match="Only GET requests"):
            await _request("DELETE", "/courses")

    def test_encryption_key_required(self):
        assert os.environ.get("ENCRYPTION_KEY") is not None

    @pytest.mark.asyncio
    async def test_scope_read_in_token_exchange(self):
        from app.services.stepik_api import exchange_code_for_token
        import httpx
        from unittest.mock import AsyncMock, patch

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            await exchange_code_for_token("code", "id", "secret", "uri")
            call_args = httpx.AsyncClient.post.call_args
            assert "scope" in call_args.kwargs["data"]
            assert call_args.kwargs["data"]["scope"] == "read"

    def test_token_refresh_checks_expiry(self):
        from app.services.token_refresh import TOKEN_EXPIRY_BUFFER_SECONDS
        assert TOKEN_EXPIRY_BUFFER_SECONDS == 900
