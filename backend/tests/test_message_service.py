from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from backend.services.messenger.message_service import ChatNotFoundError, MessageService


async def test_resolve_chat_cache_hit_skips_uow(fake_uow, fake_uow_factory):
    service = MessageService(uow_factory=fake_uow_factory)
    chats = {"guid-1": 5}

    chat_id, was_queried = await service.resolve_chat("guid-1", chats, user_id=7)

    assert (chat_id, was_queried) == (5, False)
    fake_uow.chats.get_chat_id_for_participant.assert_not_awaited()


async def test_resolve_chat_queries_and_caches_on_miss(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 5
    service = MessageService(uow_factory=fake_uow_factory)
    chats: dict = {}

    chat_id, was_queried = await service.resolve_chat("guid-1", chats, user_id=7)

    assert (chat_id, was_queried) == (5, True)
    assert chats["guid-1"] == 5
    fake_uow.chats.get_chat_id_for_participant.assert_awaited_once_with("guid-1", 7)


async def test_resolve_chat_never_trusts_bare_guid(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = None
    service = MessageService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.resolve_chat("guid-1", {}, user_id=999)


async def test_get_chat_member_guids(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_member_guids.return_value = ["a", "b"]
    service = MessageService(uow_factory=fake_uow_factory)

    result = await service.get_chat_member_guids(1)

    assert result == ["a", "b"]
    fake_uow.chats.get_chat_member_guids.assert_awaited_once_with(1)


async def test_save_message_persists_and_refreshes(fake_uow, fake_uow_factory):
    message = SimpleNamespace(id=10)
    chat = SimpleNamespace(id=1)
    fake_uow.messages.add_message.return_value = message
    fake_uow.chats.touch.return_value = chat
    service = MessageService(uow_factory=fake_uow_factory)

    result_message, result_chat = await service.save_message(content="hi", chat_id=1, user_id=7)

    assert (result_message, result_chat) == (message, chat)
    fake_uow.messages.add_message.assert_awaited_once_with(chat_id=1, content="hi", user_id=7)
    fake_uow.commit.assert_awaited_once()
    fake_uow.refresh.assert_any_await(message, ["user", "chat"])
    fake_uow.refresh.assert_any_await(chat, ["users"])


async def test_mark_message_read_returns_none_when_message_missing(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    fake_uow.messenger.get_message_by_guid.return_value = None
    service = MessageService(uow_factory=fake_uow_factory)

    result = await service.mark_message_read(
        message_guid=str(uuid.uuid4()), chat_guid="guid-1", chats={}, user_id=7
    )

    assert result is None
    fake_uow.messenger.upsert_read_status.assert_not_awaited()


async def test_mark_message_read_success(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    message = SimpleNamespace(id=42)
    fake_uow.messenger.get_message_by_guid.return_value = message
    service = MessageService(uow_factory=fake_uow_factory)

    result = await service.mark_message_read(
        message_guid=str(uuid.uuid4()), chat_guid="guid-1", chats={}, user_id=7
    )

    assert result is message
    fake_uow.messenger.upsert_read_status.assert_awaited_once_with(7, 1, 42)
    fake_uow.commit.assert_awaited_once()
