from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.services.auth_service import AuthService
from backend.utils.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    RefreshTokenError,
    TokenExpiredError,
    TokenRevokedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


class StubRepo:
    def __init__(self) -> None:
        self.user_by_login = None
        self.user_by_id = None
        self.refresh_record = None
        self.created_user = None
        self.add_refresh_calls: list[tuple[uuid.UUID, str, datetime]] = []
        self.revoked_tokens: list[str] = []
        self.revoke_all_calls: list[uuid.UUID] = []

    async def get_user_by_login(self, login: str):
        return self.user_by_login

    async def add_refresh_token(self, user_id: uuid.UUID, token: str, expires_at: datetime) -> None:
        self.add_refresh_calls.append((user_id, token, expires_at))

    async def create_user(self, login: str, hashed_password: str):
        self.created_user = SimpleNamespace(id=uuid.uuid4(), login=login, password=hashed_password)
        return self.created_user

    async def get_refresh_token(self, token: str):
        return self.refresh_record

    async def revoke_refresh_token(self, token: str) -> bool:
        self.revoked_tokens.append(token)
        return True

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        self.revoke_all_calls.append(user_id)
        return 3

    async def get_user_id(self, user_id: uuid.UUID):
        return self.user_by_id


@pytest.fixture
def auth_handler() -> Mock:
    return Mock()


@pytest.fixture
def service(auth_handler: Mock) -> tuple[AuthService, StubRepo]:
    repo = StubRepo()
    svc = AuthService(repo=repo, auth_handler=auth_handler)
    return svc, repo


@pytest.mark.asyncio
async def test_login_returns_tokens_and_persists_refresh(monkeypatch: pytest.MonkeyPatch, service, auth_handler: Mock) -> None:
    svc, repo = service
    user_id = uuid.uuid4()
    repo.user_by_login = SimpleNamespace(id=user_id, password='hashed-password')
    auth_handler.authenticate_user.return_value = 'access-token'
    monkeypatch.setattr('backend.app.services.AuthService.secrets.token_urlsafe', lambda _: 'refresh-token')

    result = await svc.login('alice', 'plain-password')

    assert result == {
        'message': 'Login successful',
        'access_token': 'access-token',
        'refresh_token': 'refresh-token',
        'token_type': 'bearer',
    }
    auth_handler.authenticate_user.assert_called_once_with(
        user_id=str(user_id),
        hashed_password='hashed-password',
        provided_password='plain-password',
    )
    assert len(repo.add_refresh_calls) == 1
    saved_user_id, saved_token, saved_expires_at = repo.add_refresh_calls[0]
    assert saved_user_id == user_id
    assert saved_token == 'refresh-token'
    assert saved_expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_login_raises_when_user_not_found(service, auth_handler: Mock) -> None:
    svc, _ = service

    with pytest.raises(UserNotFoundError):
        await svc.login('missing', 'plain-password')

    auth_handler.authenticate_user.assert_not_called()


@pytest.mark.asyncio
async def test_login_raises_when_password_is_invalid(service, auth_handler: Mock) -> None:
    svc, repo = service
    repo.user_by_login = SimpleNamespace(id=uuid.uuid4(), password='hashed-password')
    auth_handler.authenticate_user.return_value = None

    with pytest.raises(InvalidCredentialsError):
        await svc.login('alice', 'wrong-password')

    assert repo.add_refresh_calls == []


@pytest.mark.asyncio
async def test_register_creates_user_with_hashed_password(service, auth_handler: Mock) -> None:
    svc, repo = service
    auth_handler.get_password_hash.return_value = 'hashed-password'

    result = await svc.register('alice', 'plain-password')

    assert result['status'] == 'success'
    assert result['message'] == 'User created successfully'
    assert result['user_id'] == str(repo.created_user.id)
    auth_handler.get_password_hash.assert_called_once_with('plain-password')
    assert repo.created_user.login == 'alice'
    assert repo.created_user.password == 'hashed-password'


@pytest.mark.asyncio
async def test_register_raises_when_user_already_exists(service, auth_handler: Mock) -> None:
    svc, repo = service
    repo.user_by_login = SimpleNamespace(id=uuid.uuid4(), password='hashed-password')

    with pytest.raises(UserAlreadyExistsError):
        await svc.register('alice', 'plain-password')

    auth_handler.get_password_hash.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(monkeypatch: pytest.MonkeyPatch, service, auth_handler: Mock) -> None:
    svc, repo = service
    user_id = uuid.uuid4()
    repo.refresh_record = SimpleNamespace(
        user_id=user_id,
        revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    auth_handler.create_access_token.return_value = 'new-access-token'
    monkeypatch.setattr('backend.app.services.AuthService.secrets.token_urlsafe', lambda _: 'new-refresh-token')

    result = await svc.refresh('old-refresh-token')

    assert result == {
        'access_token': 'new-access-token',
        'refresh_token': 'new-refresh-token',
        'token_type': 'bearer',
    }
    auth_handler.create_access_token.assert_called_once_with(str(user_id))
    assert repo.revoked_tokens == ['old-refresh-token']
    assert len(repo.add_refresh_calls) == 1
    saved_user_id, saved_token, _ = repo.add_refresh_calls[0]
    assert saved_user_id == user_id
    assert saved_token == 'new-refresh-token'


@pytest.mark.asyncio
async def test_refresh_raises_for_missing_revoked_and_expired_tokens(service) -> None:
    svc, repo = service

    with pytest.raises(RefreshTokenError):
        await svc.refresh('missing')

    repo.refresh_record = SimpleNamespace(
        user_id=uuid.uuid4(),
        revoked=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    with pytest.raises(TokenRevokedError):
        await svc.refresh('revoked')

    repo.refresh_record = SimpleNamespace(
        user_id=uuid.uuid4(),
        revoked=False,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    with pytest.raises(TokenExpiredError):
        await svc.refresh('expired')


@pytest.mark.asyncio
async def test_logout_revokes_current_token(service) -> None:
    svc, repo = service
    user_id = uuid.uuid4()
    repo.refresh_record = SimpleNamespace(user_id=user_id, revoked=False)

    result = await svc.logout('refresh-token', revoke_all=False)

    assert result == {'status': 'success', 'message': 'Logged out successfully.'}
    assert repo.revoked_tokens == ['refresh-token']


@pytest.mark.asyncio
async def test_logout_revokes_all_tokens(service) -> None:
    svc, repo = service
    user_id = uuid.uuid4()
    repo.refresh_record = SimpleNamespace(user_id=user_id, revoked=False)

    result = await svc.logout('refresh-token', revoke_all=True)

    assert result == {'status': 'success', 'message': 'Logged out from all devices. Revoked 3 tokens.'}
    assert repo.revoke_all_calls == [user_id]


@pytest.mark.asyncio
async def test_logout_returns_success_when_token_missing_or_already_revoked(service) -> None:
    svc, repo = service

    result_missing = await svc.logout('missing-token')
    assert result_missing == {'status': 'success', 'message': 'Already logged out'}

    repo.refresh_record = SimpleNamespace(user_id=uuid.uuid4(), revoked=True)
    result_revoked = await svc.logout('revoked-token')
    assert result_revoked == {'status': 'success', 'message': 'Already logged out'}


@pytest.mark.asyncio
async def test_get_user_from_token_returns_user(service, auth_handler: Mock) -> None:
    svc, repo = service
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, login='alice')
    repo.user_by_id = user
    auth_handler.decode_token.return_value = {'sub': str(user_id)}

    result = await svc.get_user_from_token('access-token')

    assert result is user


@pytest.mark.asyncio
async def test_get_user_from_token_raises_for_invalid_claims(service, auth_handler: Mock) -> None:
    svc, repo = service

    auth_handler.decode_token.return_value = {}
    with pytest.raises(AuthenticationError):
        await svc.get_user_from_token('access-token')

    auth_handler.decode_token.return_value = {'sub': 'not-a-uuid'}
    with pytest.raises(AuthenticationError):
        await svc.get_user_from_token('access-token')

    auth_handler.decode_token.return_value = {'sub': str(uuid.uuid4())}
    repo.user_by_id = None
    with pytest.raises(UserNotFoundError):
        await svc.get_user_from_token('access-token')
