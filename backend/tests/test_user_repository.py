from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from backend.models.database_models import Users
from backend.repository.repository import UserRepository


@pytest.mark.asyncio
async def test_create_user_and_get_by_login(
    user_repository: UserRepository,
    session_factory,
) -> None:
    login = f"user-repo-create-{uuid.uuid4()}"
    password = "test-password"

    created = await user_repository.create_user(login=login, password=password)
    loaded = await user_repository.get_user_by_login(login)

    assert isinstance(created, Users)
    assert created.id is not None
    assert created.login == login
    assert created.password == password
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.login == login

    async with session_factory() as session:
        merged = await session.merge(created)
        await session.delete(merged)
        await session.commit()


@pytest.mark.asyncio
async def test_get_user_by_id_returns_user(
    user_repository: UserRepository,
    test_user: Users,
) -> None:
    loaded = await user_repository.get_user_by_id(test_user.id)

    assert loaded is not None
    assert loaded.id == test_user.id
    assert loaded.login == test_user.login


@pytest.mark.asyncio
async def test_get_users_respects_page_size(
    user_repository: UserRepository,
    session_factory,
) -> None:
    created_users: list[Users] = []

    async with session_factory() as session:
        for _ in range(3):
            user = Users(login=f"user-repo-list-{uuid.uuid4()}", password="test-password")
            session.add(user)
            created_users.append(user)
        await session.commit()
        for user in created_users:
            await session.refresh(user)

    try:
        users = await user_repository.get_users(page_size=2)

        assert len(users) == 2
    finally:
        async with session_factory() as session:
            ids = [user.id for user in created_users]
            result = await session.execute(select(Users).where(Users.id.in_(ids)))
            for user in result.scalars().all():
                await session.delete(user)
            await session.commit()


@pytest.mark.asyncio
async def test_update_user_updates_login_and_password(
    user_repository: UserRepository,
    session_factory,
) -> None:
    old_login = f"user-repo-update-old-{uuid.uuid4()}"
    new_login = f"user-repo-update-new-{uuid.uuid4()}"
    old_password = "old-password"
    new_password = "new-password"

    created = await user_repository.create_user(login=old_login, password=old_password)

    try:
        updated = await user_repository.update_user(
            user_id=created.id,
            new_login=new_login,
            new_password=new_password,
        )
        loaded = await user_repository.get_user_by_id(created.id)

        assert updated is True
        assert loaded is not None
        assert loaded.login == new_login
        assert loaded.password == new_password
    finally:
        async with session_factory() as session:
            merged = await session.merge(created)
            await session.delete(merged)
            await session.commit()


@pytest.mark.asyncio
async def test_update_user_returns_false_for_missing_user(
    user_repository: UserRepository,
) -> None:
    updated = await user_repository.update_user(
        user_id=uuid.uuid4(),
        new_login=f"user-repo-missing-{uuid.uuid4()}",
        new_password="new-password",
    )

    assert updated is False


@pytest.mark.asyncio
async def test_delete_user_removes_user(
    user_repository: UserRepository,
) -> None:
    login = f"user-repo-delete-{uuid.uuid4()}"
    created = await user_repository.create_user(login=login, password="test-password")

    deleted = await user_repository.delete_user(created.id)
    loaded = await user_repository.get_user_by_id(created.id)

    assert deleted is True
    assert loaded is None


@pytest.mark.asyncio
async def test_delete_user_returns_false_for_missing_user(
    user_repository: UserRepository,
) -> None:
    deleted = await user_repository.delete_user(uuid.uuid4())

    assert deleted is False
