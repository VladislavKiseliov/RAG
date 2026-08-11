from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.services.auth_service import AuthService
from backend.utils.exceptions import (
    AuthenticationError, InvalidCredentialsError, RefreshTokenError,
    RefreshTokenExpiredError, TokenRevokedError, UserAlreadyExistsError, UserNotFoundError,
)


@pytest.fixture
def auth_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(fake_uow_factory, auth_handler) -> AuthService:
    return AuthService(uow_factory=fake_uow_factory, auth_handler=auth_handler)


# ── login ──────────────────────────────────────────────────────────────────

async def test_login_unknown_user_raises_generic_error(fake_uow, service, auth_handler):
    fake_uow.auth.get_user.return_value = None

    with pytest.raises(InvalidCredentialsError):
        await service.login("nobody", "pw")

    auth_handler.authenticate_user.assert_not_called()


async def test_login_wrong_password_raises_same_generic_error(fake_uow, service, auth_handler):
    fake_uow.auth.get_user.return_value = SimpleNamespace(guid=uuid.uuid4(), password="hash", id=1)
    auth_handler.authenticate_user.return_value = None

    with pytest.raises(InvalidCredentialsError):
        await service.login("alice", "wrong-pw")

    fake_uow.auth.add_refresh_token.assert_not_awaited()


async def test_login_success(fake_uow, service, auth_handler):
    user = SimpleNamespace(guid=uuid.uuid4(), password="hash", id=1)
    fake_uow.auth.get_user.return_value = user
    auth_handler.authenticate_user.return_value = "jwt-token"

    result = await service.login("alice", "correct-pw")

    assert result["access_token"] == "jwt-token"
    assert result["token_type"] == "bearer"
    fake_uow.auth.add_refresh_token.assert_awaited_once()
    fake_uow.commit.assert_awaited_once()


# ── register ───────────────────────────────────────────────────────────────

async def test_register_existing_user_raises(fake_uow, service):
    fake_uow.auth.get_user.return_value = SimpleNamespace(id=1)

    with pytest.raises(UserAlreadyExistsError):
        await service.register("alice", "pw")

    fake_uow.auth.create_user.assert_not_awaited()


async def test_register_success(fake_uow, service, auth_handler):
    fake_uow.auth.get_user.return_value = None
    auth_handler.get_password_hash.return_value = "hashed-pw"
    fake_uow.auth.create_user.return_value = SimpleNamespace(id=5)

    result = await service.register("newuser", "pw")

    assert result["status"] == "success"
    assert result["user_id"] == "5"
    fake_uow.auth.create_user.assert_awaited_once_with(login="newuser", hashed_password="hashed-pw")
    fake_uow.commit.assert_awaited_once()


# ── refresh ────────────────────────────────────────────────────────────────

def _stored_token(**overrides):
    defaults = dict(
        user_id=1, revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def test_refresh_not_found_raises(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = None

    with pytest.raises(RefreshTokenError):
        await service.refresh("no-such-token")


async def test_refresh_revoked_raises(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = _stored_token(revoked=True)

    with pytest.raises(TokenRevokedError):
        await service.refresh("revoked-token")


async def test_refresh_expired_raises(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = _stored_token(
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )

    with pytest.raises(RefreshTokenExpiredError):
        await service.refresh("expired-token")


async def test_refresh_success_rotates_token(fake_uow, service, auth_handler):
    fake_uow.auth.get_refresh_token.return_value = _stored_token()
    fake_uow.auth.get_user_by_id.return_value = SimpleNamespace(guid=uuid.uuid4())
    auth_handler.create_access_token.return_value = "new-access"

    result = await service.refresh("old-token")

    assert result["access_token"] == "new-access"
    fake_uow.auth.revoke_refresh_token.assert_awaited_once_with(token="old-token")
    fake_uow.auth.add_refresh_token.assert_awaited_once()
    fake_uow.commit.assert_awaited_once()


# ── logout ─────────────────────────────────────────────────────────────────

async def test_logout_missing_token_is_idempotent(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = None

    result = await service.logout("no-such-token")

    assert result["status"] == "success"
    fake_uow.commit.assert_not_awaited()


async def test_logout_already_revoked_is_idempotent(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = _stored_token(revoked=True)

    result = await service.logout("already-revoked")

    assert result["status"] == "success"
    fake_uow.commit.assert_not_awaited()


async def test_logout_revokes_single_token(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = _stored_token()

    await service.logout("token", revoke_all=False)

    fake_uow.auth.revoke_refresh_token.assert_awaited_once_with("token")
    fake_uow.commit.assert_awaited_once()


async def test_logout_revoke_all(fake_uow, service):
    fake_uow.auth.get_refresh_token.return_value = _stored_token()
    fake_uow.auth.revoke_all_user_tokens.return_value = 3

    result = await service.logout("token", revoke_all=True)

    assert "3" in result["message"]
    fake_uow.auth.revoke_all_user_tokens.assert_awaited_once_with(1)


# ── get_user_from_token ──────────────────────────────────────────────────

async def test_get_user_from_token_missing_sub_raises(fake_uow, service, auth_handler):
    auth_handler.decode_token.return_value = {}

    with pytest.raises(AuthenticationError):
        await service.get_user_from_token("token")


async def test_get_user_from_token_bad_uuid_raises(fake_uow, service, auth_handler):
    auth_handler.decode_token.return_value = {"sub": "not-a-uuid"}

    with pytest.raises(AuthenticationError):
        await service.get_user_from_token("token")


async def test_get_user_from_token_unknown_user_raises(fake_uow, service, auth_handler):
    user_guid = uuid.uuid4()
    auth_handler.decode_token.return_value = {"sub": str(user_guid)}
    fake_uow.auth.get_user_by_guid.return_value = None

    with pytest.raises(UserNotFoundError):
        await service.get_user_from_token("token")


async def test_get_user_from_token_success(fake_uow, service, auth_handler):
    user_guid = uuid.uuid4()
    auth_handler.decode_token.return_value = {"sub": str(user_guid)}
    fake_uow.auth.get_user_by_guid.return_value = SimpleNamespace(
        id=1, guid=user_guid, login="alice", first_name="A", last_name="S", is_superuser=False,
    )

    result = await service.get_user_from_token("token")

    assert result.login == "alice"
    assert result.guid == user_guid
