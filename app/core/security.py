import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings

_FERNET_KDF_LABEL = b"stagecraft-token-encryption-v1:"

def _get_fernet() -> Fernet:
    if settings.TOKEN_ENCRYPTION_KEY:
        return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
    key_bytes = hashlib.sha256(_FERNET_KDF_LABEL + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))

def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()

def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
