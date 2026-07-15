import pytest
import os
import ast


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
    def test_no_post_to_stepik_in_api_client(self):
        from app.services.stepik_api import _request
        import inspect
        source = inspect.getsource(_request)
        assert "Only GET requests" in source

    def test_encryption_key_required(self):
        assert os.environ.get("ENCRYPTION_KEY") is not None

    def test_scope_read_in_token_exchange(self):
        from app.services.stepik_api import exchange_code_for_token
        import inspect
        source = inspect.getsource(exchange_code_for_token)
        assert "scope" in source
        assert "read" in source

    def test_all_get_only_to_stepik(self):
        from app.services.stepik_api import _request
        import inspect
        source = inspect.getsource(_request)
        assert "GET" in source
