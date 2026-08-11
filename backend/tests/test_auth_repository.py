from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from backend.models.database_models import Users


async def test_create_user_and_get_by_login(auth_repository, session_factory):
    login = f"authrepo-{uuid.uuid4()}"
    user = await auth_repository.create_user(login, "hashed-pw")
    try:
        assert user.id is not None
        assert user.login == login

        found = await auth_repository.get_user_by_login(login)
        assert found.id == user.id
    finally:
        async with session_factory() as session:
            await session.execute(delete(Users).where(Users.id == user.id))
            await session.commit()


async def test_get_user_by_login_not_found(auth_repository):
    assert await auth_repository.get_user_by_login("no-such-login") is None


async def test_get_user_by_id_and_guid(auth_repository, test_user):
    by_id = await auth_repository.get_user_by_id(test_user.id)
    assert by_id.login == test_user.login

    by_guid = await auth_repository.get_user_by_guid(test_user.guid)
    assert by_guid.id == test_user.id


async def test_get_user(auth_repository, alice):
    found = await auth_repository.get_user(alice.login)
    assert found.id == alice.id


async def test_add_and_get_refresh_token(auth_repository, test_user):
    token = f"token-{uuid.uuid4()}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await auth_repository.add_refresh_token(test_user.id, token, expires_at)

    stored = await auth_repository.get_refresh_token(token)
    assert stored is not None
    assert stored.user_id == test_user.id
    assert stored.revoked is False


async def test_get_refresh_token_not_found(auth_repository):
    assert await auth_repository.get_refresh_token("no-such-token") is None


async def test_revoke_refresh_token(auth_repository, test_user):
    token = f"token-{uuid.uuid4()}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await auth_repository.add_refresh_token(test_user.id, token, expires_at)

    revoked = await auth_repository.revoke_refresh_token(token)
    assert revoked is True

    stored = await auth_repository.get_refresh_token(token)
    assert stored.revoked is True

    assert await auth_repository.revoke_refresh_token("no-such-token") is False


async def test_revoke_all_user_tokens(auth_repository, test_user, test_user_bob):
    tokens = [f"token-{uuid.uuid4()}" for _ in range(3)]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    for token in tokens:
        await auth_repository.add_refresh_token(test_user.id, token, expires_at)

    other_token = f"token-{uuid.uuid4()}"
    await auth_repository.add_refresh_token(test_user_bob.id, other_token, expires_at)

    count = await auth_repository.revoke_all_user_tokens(test_user.id)
    assert count == len(tokens)

    for token in tokens:
        stored = await auth_repository.get_refresh_token(token)
        assert stored.revoked is True

    other_stored = await auth_repository.get_refresh_token(other_token)
    assert other_stored.revoked is False
