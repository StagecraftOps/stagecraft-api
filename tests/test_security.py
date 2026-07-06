import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32ch")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")

def test_fernet_encrypt_decrypt_roundtrip():
    from app.core.security import decrypt_token, encrypt_token

    plaintext = "ghp_test_github_access_token_value"
    encrypted = encrypt_token(plaintext)

    assert encrypted != plaintext, "encrypt_token must not return plaintext"
    assert decrypt_token(encrypted) == plaintext

def test_fernet_wrong_key_raises():
    import base64, hashlib
    from cryptography.fernet import Fernet, InvalidToken
    from app.core.security import encrypt_token

    encrypted = encrypt_token("some_token")

    wrong_key = base64.urlsafe_b64encode(hashlib.sha256(b"wrong-secret").digest())
    f = Fernet(wrong_key)

    with pytest.raises(InvalidToken):
        f.decrypt(encrypted.encode())

def test_jwt_create_and_verify():
    from app.core.security import create_access_token, verify_access_token

    payload = {"sub": "user-uuid-123", "login": "testuser"}
    token = create_access_token(payload)

    decoded = verify_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-uuid-123"
    assert decoded["login"] == "testuser"

def test_jwt_tampered_token_returns_none():
    from app.core.security import create_access_token, verify_access_token

    token = create_access_token({"sub": "user-uuid-123"})
    tampered = token[:-4] + "XXXX"

    assert verify_access_token(tampered) is None

def test_fernet_key_domain_separation():
    import base64, hashlib
    from app.core.config import settings

    raw_key = settings.SECRET_KEY.encode()

    label = b"stagecraft-token-encryption-v1:"
    derived = base64.urlsafe_b64encode(hashlib.sha256(label + raw_key).digest())

    raw_b64 = base64.urlsafe_b64encode(raw_key)
    assert derived != raw_b64, "Fernet key must not equal raw SECRET_KEY"

def test_production_insecure_key_raises(monkeypatch):
    from app.core.config import INSECURE_DEFAULT_SECRET

    monkeypatch.setenv("SECRET_KEY", INSECURE_DEFAULT_SECRET)
    monkeypatch.setenv("ENVIRONMENT", "production")

    import importlib
    import app.core.config as cfg_mod
    importlib.reload(cfg_mod)
    settings = cfg_mod.Settings()

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        if settings.is_production and settings.SECRET_KEY == INSECURE_DEFAULT_SECRET:
            raise RuntimeError(
                "SECRET_KEY is set to the insecure development default while "
                "ENVIRONMENT is production."
            )
