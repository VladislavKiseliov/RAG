from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete

from backend.models.database_models import Users
from backend.schemas.schemas import UserProfileUpdateRequest
from backend.services.user_service import UserService
from backend.utils.exceptions import (
    LastAdminError, SelfActionForbiddenError, UserAlreadyExistsError, UserNotFoundError,
)


@pytest.fixture
def auth_handler() -> MagicMock:
    handler = MagicMock()
    handler.get_password_hash.return_value = "hashed-pw"
    return handler


@pytest.fixture
def service(session_factory, auth_handler) -> UserService:
    return UserService(session_factory=session_factory, auth_handler=auth_handler)


async def test_get_users_repo(service):
    result = await service.get_users_repo(page_size=2)
    assert result["page_size"] == 2
    assert len(result["items"]) <= 2
    assert result["total"] == len(result["items"])
    assert result["items"][0]["role"] in ("admin", "user")


async def test_get_user_repo_by_id(service, alice):
    profile = await service.get_user_repo_by_id(alice.id)
    assert profile.login == alice.login
    assert await service.get_user_repo_by_id(999_999_999) is None


async def test_create_user_repo_success(service, session_factory, auth_handler):
    login = f"userservice-{uuid.uuid4()}"
    try:
        result = await service.create_user_repo(login, "plain-pw")
        assert result["login"] == login
        auth_handler.get_password_hash.assert_called_once_with("plain-pw")
    finally:
        async with session_factory() as session:
            await session.execute(delete(Users).where(Users.login == login))
            await session.commit()


async def test_create_user_repo_existing_raises(service, alice):
    with pytest.raises(UserAlreadyExistsError):
        await service.create_user_repo(alice.login, "pw")


async def test_update_user_repo_success(service, test_user):
    updated = await service.update_user_repo(
        test_user.id, UserProfileUpdateRequest(first_name="Changed")
    )
    assert updated.first_name == "Changed"


async def test_update_user_repo_not_found_raises(service):
    with pytest.raises(UserNotFoundError):
        await service.update_user_repo(999_999_999, UserProfileUpdateRequest(first_name="X"))


async def test_update_user_credentials_success(service, test_user, auth_handler):
    new_login = f"changed-{uuid.uuid4()}"
    result = await service.update_user_credentials(test_user.id, new_login, "new-pw")
    assert result["login"] == new_login
    auth_handler.get_password_hash.assert_called_once_with("new-pw")


async def test_update_user_credentials_conflicts_with_other_user(service, test_user, test_user_bob):
    with pytest.raises(UserAlreadyExistsError):
        await service.update_user_credentials(test_user.id, test_user_bob.login, "pw")


async def test_delete_user_repo_self_forbidden(service, test_user):
    with pytest.raises(SelfActionForbiddenError):
        await service.delete_user_repo(test_user.id, current_user_id=test_user.id)


async def test_delete_user_repo_success(service, test_user, alice):
    assert await service.delete_user_repo(test_user.id, current_user_id=alice.id) is True
    assert await service.get_user_repo_by_id(test_user.id) is None


async def test_update_user_role_self_demote_forbidden(service, test_user):
    with pytest.raises(SelfActionForbiddenError):
        await service.update_user_role(test_user.id, is_superuser=False, current_user_id=test_user.id)


async def test_update_user_role_promote_success(service, test_user, alice):
    result = await service.update_user_role(test_user.id, is_superuser=True, current_user_id=alice.id)
    assert result["role"] == "admin"


async def test_update_user_role_last_admin_forbidden(service, test_user, test_user_bob, alice):
    await service.update_user_role(test_user.id, is_superuser=True, current_user_id=alice.id)

    with pytest.raises(LastAdminError):
        await service.update_user_role(test_user_bob.id, is_superuser=False, current_user_id=alice.id)


async def test_search_users_excludes_self(service, test_user, test_user_bob):
    results = await service.search_users(test_user.login[:8], exclude_id=test_user.id)
    assert all(r["guid"] != str(test_user.guid) for r in results)
