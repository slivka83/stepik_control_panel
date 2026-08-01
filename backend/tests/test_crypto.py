import pytest
from cryptography.fernet import Fernet

from app.services.crypto import decrypt_token, encrypt_token, get_fernet


class TestEncryptDecrypt:
    def test_encrypt_returns_string(self):
        result = encrypt_token("test_token")
        assert isinstance(result, str)

    def test_decrypt_returns_original(self):
        original = "my_secret_token_123"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_encrypt_different_each_time(self):
        token = "same_token"
        enc1 = encrypt_token(token)
        enc2 = encrypt_token(token)
        assert enc1 != enc2

    def test_decrypt_wrong_key_fails(self):
        encrypted = encrypt_token("test")
        from cryptography.fernet import InvalidToken

        wrong_fernet = Fernet(Fernet.generate_key())
        with pytest.raises(InvalidToken):
            wrong_fernet.decrypt(encrypted.encode())

    def test_encrypt_empty_string(self):
        encrypted = encrypt_token("")
        decrypted = decrypt_token(encrypted)
        assert decrypted == ""

    def test_encrypt_long_token(self):
        long_token = "x" * 10000
        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == long_token

    def test_encrypt_unicode(self):
        token = "токен_с_кириллицей_ñ"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == token

    def test_get_fernet_returns_fernet_instance(self):
        fernet = get_fernet()
        assert isinstance(fernet, Fernet)

    def test_encrypt_special_characters(self):
        token = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == token

    def test_encrypt_newlines(self):
        token = "line1\nline2\nline3"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == token
