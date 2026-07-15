from cryptography.fernet import Fernet

from app.config import get_settings


def get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key
    return Fernet(key)


def encrypt_token(token: str) -> str:
    fernet = get_fernet()
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    fernet = get_fernet()
    return fernet.decrypt(encrypted_token.encode()).decode()
