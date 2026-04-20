from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.user_service import UserService


@pytest.fixture
def user_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(user_repo: AsyncMock) -> UserService:
    return UserService(user_repo=user_repo)


def _user_obj(user_id: uuid.UUID, login: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(id=user_id, login=login, created_at=now, updated_at=now)


@pytest.mark.asyncio
async def test_get_users_repo_maps_payload(service: UserService, user_repo: AsyncMock) -> None:
    first = _user_obj(uuid.uuid4(), "alice")
    second = _user_obj(uuid.uuid4(), "bob")
    user_repo.get_users.return_value = [first, second]

    result = await service.get_users_repo(page_size=2)

    assert result["total"] == 2
    assert result["page_size"] == 2
    assert result["items"][0]["id"] == str(first.id)
    assert result["items"][0]["login"] == "alice"
    assert result["items"][1]["id"] == str(second.id)
    assert result["items"][1]["login"] == "bob"
    user_repo.get_users.assert_awaited_once_with(page_size=2)


@pytest.mark.asyncio
async def test_get_user_repo_by_id_returns_none_when_missing(service: UserService, user_repo: AsyncMock) -> None:
    user_repo.get_user_by_id.return_value = None

    result = await service.get_user_repo_by_id(uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_user_repo_by_id_maps_payload(service: UserService, user_repo: AsyncMock) -> None:
    user = _user_obj(uuid.uuid4(), "alice")
    user_repo.get_user_by_id.return_value = user

    result = await service.get_user_repo_by_id(user.id)

    assert result is not None
    assert result["id"] == str(user.id)
    assert result["login"] == "alice"


@pytest.mark.asyncio
async def test_create_user_repo_raises_for_duplicate_login(service: UserService, user_repo: AsyncMock) -> None:
    user_repo.get_user_by_login.return_value = _user_obj(uuid.uuid4(), "alice")

    with pytest.raises(ValueError, match="already exists"):
        await service.create_user_repo(login="alice", password="secret")

    user_repo.create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_repo_creates_and_maps_payload(service: UserService, user_repo: AsyncMock) -> None:
    created = _user_obj(uuid.uuid4(), "alice")
    user_repo.get_user_by_login.return_value = None
    user_repo.create_user.return_value = created

    result = await service.create_user_repo(login="alice", password="secret")

    assert result["id"] == str(created.id)
    assert result["login"] == "alice"
    user_repo.create_user.assert_awaited_once_with(login="alice", password="secret")


@pytest.mark.asyncio
async def test_update_user_repo_raises_for_duplicate_login(service: UserService, user_repo: AsyncMock) -> None:
    target_user_id = uuid.uuid4()
    user_repo.get_user_by_login.return_value = _user_obj(uuid.uuid4(), "taken")

    with pytest.raises(ValueError, match="already exists"):
        await service.update_user_repo(user_id=target_user_id, login="taken", password="secret")

    user_repo.update_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_repo_returns_none_when_target_missing(service: UserService, user_repo: AsyncMock) -> None:
    target_user_id = uuid.uuid4()
    user_repo.get_user_by_login.return_value = None
    user_repo.update_user.return_value = False

    result = await service.update_user_repo(user_id=target_user_id, login="alice", password="secret")

    assert result is None


@pytest.mark.asyncio
async def test_update_user_repo_maps_payload_after_update(service: UserService, user_repo: AsyncMock) -> None:
    target_user_id = uuid.uuid4()
    updated_user = _user_obj(target_user_id, "alice-new")
    user_repo.get_user_by_login.return_value = None
    user_repo.update_user.return_value = True
    user_repo.get_user_by_id.return_value = updated_user

    result = await service.update_user_repo(user_id=target_user_id, login="alice-new", password="secret")

    assert result is not None
    assert result["id"] == str(target_user_id)
    assert result["login"] == "alice-new"
    user_repo.update_user.assert_awaited_once_with(
        user_id=target_user_id,
        new_login="alice-new",
        new_password="secret",
    )


@pytest.mark.asyncio
async def test_delete_user_repo_returns_repository_result(service: UserService, user_repo: AsyncMock) -> None:
    user_repo.delete_user.return_value = True
    user_id = uuid.uuid4()

    result = await service.delete_user_repo(user_id)

    assert result is True
    user_repo.delete_user.assert_awaited_once_with(user_id)
