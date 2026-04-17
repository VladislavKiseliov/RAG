from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.models.database_models import RefreshTokens, Users
from backend.repository.repository import AuthRepository


@pytest.mark.asyncio
async def test_create_user_and_get_user_by_login(auth_repository: AuthRepository, session_factory) -> None:
    login = f"auth-user-{datetime.now(timezone.utc).timestamp()}"
    hashed_password = "hashed-password"

    created = await auth_repository.create_user(login, hashed_password)
    loaded = await auth_repository.get_user_by_login(login)

    assert isinstance(created, Users)
    assert created.id is not None
    assert created.login == login
    assert created.password == hashed_password
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.login == login
    assert loaded.password == hashed_password

    async with session_factory() as session:
        merged = await session.merge(created)
        await session.delete(merged)
        await session.commit()


@pytest.mark.asyncio
async def test_add_and_get_refresh_token(auth_repository: AuthRepository, test_user: Users) -> None:
    token = f"refresh-{test_user.id}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await auth_repository.add_refresh_token(test_user.id, token, expires_at)
    stored = await auth_repository.get_refresh_token(token)

    assert stored is not None
    assert isinstance(stored, RefreshTokens)
    assert stored.user_id == test_user.id
    assert stored.token == token
    assert stored.revoked is False


@pytest.mark.asyncio
async def test_revoke_refresh_token_marks_token_as_revoked(auth_repository: AuthRepository, test_user: Users) -> None:
    token = f"refresh-revoke-{test_user.id}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await auth_repository.add_refresh_token(test_user.id, token, expires_at)
    result = await auth_repository.revoke_refresh_token(token)
    stored = await auth_repository.get_refresh_token(token)

    assert result is True
    assert stored is not None
    assert stored.revoked is True


@pytest.mark.asyncio
async def test_revoke_all_user_tokens_revokes_only_target_user_tokens(
    auth_repository: AuthRepository,
    session_factory,
    test_user: Users,
) -> None:
    first_token = f"refresh-all-1-{test_user.id}"
    second_token = f"refresh-all-2-{test_user.id}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await auth_repository.add_refresh_token(test_user.id, first_token, expires_at)
    await auth_repository.add_refresh_token(test_user.id, second_token, expires_at)

    other_user = Users(
        login=f"other-auth-user-{datetime.now(timezone.utc).timestamp()}",
        password="hashed-password",
    )
    async with session_factory() as session:
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

    try:
        other_token = f"refresh-other-{other_user.id}"
        await auth_repository.add_refresh_token(other_user.id, other_token, expires_at)

        affected_rows = await auth_repository.revoke_all_user_tokens(test_user.id)

        async with session_factory() as session:
            result = await session.execute(select(RefreshTokens).where(RefreshTokens.user_id == test_user.id))
            target_tokens = list(result.scalars().all())

        other_stored = await auth_repository.get_refresh_token(other_token)

        assert affected_rows == 2
        assert all(token.revoked is True for token in target_tokens)
        assert other_stored is not None
        assert other_stored.revoked is False
    finally:
        async with session_factory() as session:
            merged = await session.merge(other_user)
            await session.delete(merged)
            await session.commit()
