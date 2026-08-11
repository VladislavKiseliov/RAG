from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError


async def test_get_user_by_login(user_repository, alice):
    found = await user_repository.get_user_by_login(alice.login)
    assert found.id == alice.id
    assert await user_repository.get_user_by_login("no-such-login") is None


async def test_get_user_by_id(user_repository, alice):
    found = await user_repository.get_user_by_id(alice.id)
    assert found.login == alice.login
    assert await user_repository.get_user_by_id(999_999_999) is None


async def test_create_and_delete_user(user_repository):
    login = f"userrepo-{uuid.uuid4()}"
    user = await user_repository.create_user(login, "hashed-pw")
    assert user.id is not None

    found = await user_repository.get_user_by_login(login)
    assert found.id == user.id

    assert await user_repository.delete_user(user.id) is True
    assert await user_repository.get_user_by_id(user.id) is None
    assert await user_repository.delete_user(user.id) is False


async def test_create_user_enforces_login_uniqueness(user_repository, alice):
    with pytest.raises(IntegrityError):
        await user_repository.create_user(alice.login, "hashed-pw")


async def test_get_users_respects_page_size(user_repository):
    users = await user_repository.get_users(page_size=2)
    assert len(users) <= 2


async def test_search_users_excludes_self_and_matches_pattern(user_repository, test_user, test_user_bob):
    results = await user_repository.search_users(test_user.login[:8], exclude_id=test_user.id)
    result_ids = {u.id for u in results}
    assert test_user.id not in result_ids


async def test_count_superusers(user_repository, test_user):
    baseline = await user_repository.count_superusers()

    await user_repository.update_user(test_user.id, {"is_superuser": True})

    after = await user_repository.count_superusers()
    assert after == baseline + 1


async def test_update_user(user_repository, test_user):
    updated = await user_repository.update_user(test_user.id, {"first_name": "Changed"})
    assert updated.first_name == "Changed"

    assert await user_repository.update_user(999_999_999, {"first_name": "x"}) is None
