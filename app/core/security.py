import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings

_FERNET_KDF_LABEL = b"pipelineiq-token-encryption-v1:"

def _get_fernet() -> Fernet:
    """Return the Fernet instance used to encrypt stored GitHub tokens.

    Prefers a dedicated ``TOKEN_ENCRYPTION_KEY`` (a urlsafe-base64 32-byte key);
    otherwise derives one from ``SECRET_KEY`` with domain separation.
    """
    if settings.TOKEN_ENCRYPTION_KEY:
        return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
    key_bytes = hashlib.sha256(_FERNET_KDF_LABEL + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))

def encrypt_token(token: str) -> str:
    """Fernet-encrypt a plaintext token and return the encrypted string."""
    return _get_fernet().encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted token back to plaintext."""
    return _get_fernet().decrypt(encrypted.encode()).decode()

def create_access_token(data: dict[str, Any]) -> str:
    """Create a signed JWT with a 30-day expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_access_token(token: str) -> dict | None:
    """Verify and decode a JWT. Returns the payload dict or None if invalid."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
