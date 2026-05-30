"""Small encryption helpers for reversible backend secrets."""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    raw_key = settings.SECRET_ENCRYPTION_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    """Encrypt a secret for storage."""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Decrypt a stored secret."""
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
