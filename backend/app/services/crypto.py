import logging
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)
_fernet_instance: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    settings = get_settings()
    key = settings.encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not set. Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")

    key_bytes = key.encode() if isinstance(key, str) else key
    try:
        _fernet_instance = Fernet(key_bytes)
    except Exception as e:
        raise RuntimeError(f"Invalid ENCRYPTION_KEY: {e}. Must be a 32-byte URL-safe base64-encoded key.")

    return _fernet_instance


def encrypt_token(token: str) -> str:
    fernet = get_fernet()
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    fernet = get_fernet()
    try:
        return fernet.decrypt(encrypted_token.encode()).decode()
    except InvalidToken:
        raise RuntimeError("Failed to decrypt token — ENCRYPTION_KEY may have changed or data is corrupted")
