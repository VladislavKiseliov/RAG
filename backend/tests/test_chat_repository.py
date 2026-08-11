from __future__ import annotations

import uuid

from sqlalchemy import delete

from backend.models.database_models import ChatType, Chats


async def test_create_chat_and_get_chat(chat_repository, test_user):
    chat = await chat_repository.create_chat(test_user.id, "New chat", ChatType.GROUP)
    try:
        assert chat.id is not None
        assert chat.title == "New chat"

        fetched = await chat_repository.get_chat(chat.id)
        assert fetched.id == chat.id
    finally:
        await chat_repository.delete_chat(chat.id)


async def test_delete_chat(chat_repository, test_user):
    chat = await chat_repository.create_chat(test_user.id, "Temp", ChatType.GROUP)
    assert await chat_repository.delete_chat(chat.id) is True
    assert await chat_repository.get_chat(chat.id) is None
    assert await chat_repository.delete_chat(chat.id) is False


async def test_update_chat_title(chat_repository, test_user):
    chat = await chat_repository.create_chat(test_user.id, "Old title", ChatType.GROUP)
    try:
        updated = await chat_repository.update_chat_title(chat.id, "New title")
        assert updated is True

        fetched = await chat_repository.get_chat(chat.id)
        assert fetched.title == "New title"

        assert await chat_repository.update_chat_title(999_999_999, "x") is False
    finally:
        await chat_repository.delete_chat(chat.id)


async def test_get_chat_by_guid_for_participant_scoping(chat_repository, test_direct_chat, alice):
    found = await chat_repository.get_chat_by_guid_for_participant(
        test_direct_chat.guid, test_direct_chat.created_by_id
    )
    assert found is not None
    assert found.id == test_direct_chat.id

    # alice is not a participant of test_direct_chat — must not resolve
    not_found = await chat_repository.get_chat_by_guid_for_participant(test_direct_chat.guid, alice.id)
    assert not_found is None


async def test_get_user_active_chats_filters_by_type(chat_repository, alice, ai_chat, direct_chat):
    ai_only = await chat_repository.get_user_active_chats(alice.id, ChatType.AI_DIRECT)
    assert {c.id for c in ai_only} == {ai_chat.id}

    all_chats = await chat_repository.get_user_active_chats(alice.id)
    assert {c.id for c in all_chats} >= {ai_chat.id, direct_chat.id}


async def test_get_chat_member_guids(chat_repository, test_direct_chat, test_user, test_user_bob):
    guids = await chat_repository.get_chat_member_guids(test_direct_chat.id)
    assert set(guids) == {str(test_user.guid), str(test_user_bob.guid)}


async def test_get_chat_id_for_participant_and_by_guid(chat_repository, test_direct_chat, test_user, alice):
    chat_id = await chat_repository.get_chat_id_for_participant(test_direct_chat.guid, test_user.id)
    assert chat_id == test_direct_chat.id

    assert await chat_repository.get_chat_id_for_participant(test_direct_chat.guid, alice.id) is None

    by_guid = await chat_repository.get_chat_id_by_guid(test_direct_chat.guid)
    assert by_guid == test_direct_chat.id


async def test_create_direct_chat(chat_repository, test_user, test_user_bob):
    chat = await chat_repository.create_direct_chat(test_user.id, test_user_bob.id)
    try:
        assert chat.chat_type == ChatType.DIRECT
        guids = await chat_repository.get_chat_member_guids(chat.id)
        assert set(guids) == {str(test_user.guid), str(test_user_bob.guid)}
    finally:
        await chat_repository.delete_chat(chat.id)


async def test_is_chat_participant(chat_repository, test_direct_chat, test_user, alice):
    assert await chat_repository.is_chat_participant(test_direct_chat.id, test_user.id) is True
    assert await chat_repository.is_chat_participant(test_direct_chat.id, alice.id) is False


async def test_touch(chat_repository, test_direct_chat):
    touched = await chat_repository.touch(test_direct_chat.id)
    assert touched.id == test_direct_chat.id


async def test_get_user_chats_with_details(chat_repository, message_repository, test_direct_chat, test_user, test_user_bob):
    await message_repository.add_message(test_direct_chat.id, "hello", user_id=test_user.id)

    details = await chat_repository.get_user_chats_with_details(test_user.id)
    matching = [d for d in details if d.chat_guid == test_direct_chat.guid]
    assert len(matching) == 1
    assert matching[0].friend_guid == test_user_bob.guid
    assert matching[0].last_message_content == "hello"
