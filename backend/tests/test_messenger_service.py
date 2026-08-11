from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.services.messenger.messenger_service import MessengerService
from backend.utils.exceptions import ChatNotFoundError, UserNotFoundError


async def test_create_direct_chat_rejects_unknown_friend(fake_uow, fake_uow_factory):
    fake_uow.auth.get_user_by_guid.return_value = None
    service = MessengerService(uow_factory=fake_uow_factory)

    with pytest.raises(UserNotFoundError):
        await service.create_direct_chat(user_id=7, friend_guid=uuid.uuid4())

    fake_uow.chats.create_direct_chat.assert_not_awaited()


async def test_create_direct_chat_success(fake_uow, fake_uow_factory):
    friend = SimpleNamespace(
        id=2, guid=uuid.uuid4(), login="bob", first_name="Bob", last_name="Jones"
    )
    chat = SimpleNamespace(guid=uuid.uuid4(), updated_at=datetime.now(timezone.utc))
    fake_uow.auth.get_user_by_guid.return_value = friend
    fake_uow.chats.create_direct_chat.return_value = chat
    service = MessengerService(uow_factory=fake_uow_factory)

    result = await service.create_direct_chat(user_id=7, friend_guid=friend.guid)

    assert result.friend_guid == friend.guid
    assert result.chat_guid == chat.guid
    fake_uow.chats.create_direct_chat.assert_awaited_once_with(creator_id=7, friend_id=friend.id)
    fake_uow.commit.assert_awaited_once()


async def test_delete_direct_chat_rejects_non_participant(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = None
    service = MessengerService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.delete_direct_chat(chat_guid=uuid.uuid4(), user_id=999)

    fake_uow.chats.delete_chat.assert_not_awaited()


async def test_delete_direct_chat_success(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    fake_uow.chats.get_chat_member_guids.return_value = ["a", "b"]
    service = MessengerService(uow_factory=fake_uow_factory)

    result = await service.delete_direct_chat(chat_guid=uuid.uuid4(), user_id=7)

    assert result == ["a", "b"]
    fake_uow.chats.delete_chat.assert_awaited_once_with(1)
    fake_uow.commit.assert_awaited_once()


async def test_get_user_chats(fake_uow, fake_uow_factory):
    fake_uow.chats.get_user_chats_with_details.return_value = [{"chat_guid": "x"}]
    service = MessengerService(uow_factory=fake_uow_factory)

    result = await service.get_user_chats(user_id=7)

    assert result == [{"chat_guid": "x"}]


async def test_get_chat_messages_rejects_unknown_chat(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_by_guid.return_value = None
    service = MessengerService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.get_chat_messages(chat_guid=uuid.uuid4(), user_id=7)


async def test_get_chat_messages_rejects_non_participant(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_by_guid.return_value = 1
    fake_uow.chats.is_chat_participant.return_value = False
    service = MessengerService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.get_chat_messages(chat_guid=uuid.uuid4(), user_id=999)

    fake_uow.messages.get_messages_paginated.assert_not_awaited()


async def test_get_chat_messages_success(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_by_guid.return_value = 1
    fake_uow.chats.is_chat_participant.return_value = True
    msg = SimpleNamespace(
        guid=uuid.uuid4(),
        content="hi",
        user=SimpleNamespace(guid=uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
    )
    fake_uow.messages.get_messages_paginated.return_value = [msg]
    service = MessengerService(uow_factory=fake_uow_factory)

    result = await service.get_chat_messages(chat_guid=uuid.uuid4(), user_id=7)

    assert result[0]["content"] == "hi"
    assert result[0]["user_guid"] == str(msg.user.guid)
