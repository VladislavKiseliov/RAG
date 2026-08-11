from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.services.auth_handler import AuthHandler
from backend.utils.exceptions import AccessTokenExpiredError, AuthenticationError

SECRET = "test-secret-key-at-least-32-bytes-long"
ALGORITHM = "HS256"


@pytest.fixture
def handler() -> AuthHandler:
    return AuthHandler(secret_key=SECRET, algorithm=ALGORITHM, expire_minutes=15, refresh_expire_days=7)


def test_create_access_token_and_decode_roundtrip(handler):
    token = handler.create_access_token("user-123")
    payload = handler.decode_token(token)
    assert payload["sub"] == "user-123"


def test_decode_token_expired_raises(handler):
    expired_payload = {
        "sub": "user-123",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=20),
    }
    expired_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

    with pytest.raises(AccessTokenExpiredError):
        handler.decode_token(expired_token)


def test_decode_token_invalid_raises(handler):
    with pytest.raises(AuthenticationError):
        handler.decode_token("not-a-valid-jwt")


def test_decode_token_wrong_secret_raises(handler):
    other_token = jwt.encode({"sub": "x"}, "wrong-secret", algorithm=ALGORITHM)
    with pytest.raises(AuthenticationError):
        handler.decode_token(other_token)


def test_password_hash_and_verify_roundtrip(handler):
    hashed = handler.get_password_hash("s3cret-pw")
    assert handler.verify_password("s3cret-pw", hashed) is True
    assert handler.verify_password("wrong-pw", hashed) is False


def test_authenticate_user_returns_token_on_correct_password(handler):
    hashed = handler.get_password_hash("correct-pw")
    token = handler.authenticate_user("user-123", hashed, "correct-pw")
    assert token is not None
    assert handler.decode_token(token)["sub"] == "user-123"


def test_authenticate_user_returns_none_on_wrong_password(handler):
    hashed = handler.get_password_hash("correct-pw")
    assert handler.authenticate_user("user-123", hashed, "wrong-pw") is None
