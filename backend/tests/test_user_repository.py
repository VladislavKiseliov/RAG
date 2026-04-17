from __future__ import annotations

import pytest

from backend.models.database_models import Users
from backend.repository.repository import UserRepository


@pytest.mark.asyncio
async def test_get_user_id_returns_user(user_repository: UserRepository, test_user: Users) -> None:
    loaded = await user_repository.get_user_id(test_user.id)

    assert loaded is not None
    assert loaded.id == test_user.id
    assert loaded.login == test_user.login


@pytest.mark.asyncio
async def test_delete_user_removes_user(user_repository: UserRepository, session_factory) -> None:
    async with session_factory() as session:
        user = Users(login='delete-user-test', password='test-password')
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    deleted = await user_repository.delete_user(user_id)

    async with session_factory() as session:
        loaded = await session.get(Users, user_id)

    assert deleted is True
    assert loaded is None
