from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.models.database_models import ChatType
from backend.services.chat_service import ChatService
from backend.utils.exceptions import ChatNotFoundError, UserNotFoundError


def _fake_chat(**overrides):
    defaults = dict(id=1, guid=uuid.uuid4(), chat_type=ChatType.GROUP, title="Chat", created_by_id=7)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def test_create_chat(fake_uow, fake_uow_factory):
    fake_uow.chats.create_chat.return_value = _fake_chat(title="New chat")
    service = ChatService(uow_factory=fake_uow_factory)

    result = await service.create_chat(user_id=7, chat_type=ChatType.GROUP, title="New chat")

    assert result.title == "New chat"
    fake_uow.chats.create_chat.assert_awaited_once_with(user_id=7, chat_type=ChatType.GROUP, title="New chat")
    fake_uow.commit.assert_awaited_once()


async def test_get_user_active_chats(fake_uow, fake_uow_factory):
    fake_uow.chats.get_user_active_chats.return_value = [_fake_chat(), _fake_chat(id=2)]
    service = ChatService(uow_factory=fake_uow_factory)

    result = await service.get_user_active_chats(user_id=7, chat_type=ChatType.AI_DIRECT)

    assert len(result) == 2
    fake_uow.chats.get_user_active_chats.assert_awaited_once_with(7, ChatType.AI_DIRECT)


async def test_update_chat_title_rejects_non_participant(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = None
    service = ChatService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.update_chat_title(chat_guid=uuid.uuid4(), user_id=999, new_title="Hacked")

    fake_uow.chats.update_chat_title.assert_not_awaited()


async def test_update_chat_title_success(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    fake_uow.chats.update_chat_title.return_value = True
    service = ChatService(uow_factory=fake_uow_factory)

    result = await service.update_chat_title(chat_guid=uuid.uuid4(), user_id=7, new_title="New")

    assert result is True
    fake_uow.commit.assert_awaited_once()


async def test_update_chat_title_raises_when_update_fails(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    fake_uow.chats.update_chat_title.return_value = False
    service = ChatService(uow_factory=fake_uow_factory)

    with pytest.raises(UserNotFoundError):
        await service.update_chat_title(chat_guid=uuid.uuid4(), user_id=7, new_title="New")


async def test_delete_chat_rejects_non_participant(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = None
    service = ChatService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.delete_chat(chat_guid=uuid.uuid4(), user_id=999)

    fake_uow.chats.delete_chat.assert_not_awaited()


async def test_delete_chat_success(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    fake_uow.chats.delete_chat.return_value = True
    service = ChatService(uow_factory=fake_uow_factory)

    assert await service.delete_chat(chat_guid=uuid.uuid4(), user_id=7) is True


async def test_get_history_rejects_non_participant(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = None
    service = ChatService(uow_factory=fake_uow_factory)

    with pytest.raises(ChatNotFoundError):
        await service.get_history(chat_guid=uuid.uuid4(), user_id=999)

    fake_uow.messages.get_history.assert_not_awaited()


async def test_get_history_strips_source_text(fake_uow, fake_uow_factory):
    fake_uow.chats.get_chat_id_for_participant.return_value = 1
    fake_uow.messages.get_history.return_value = [
        SimpleNamespace(
            role="assistant",
            content="answer",
            sources=[{"doc_id": "d1", "text": "huge chunk text"}],
            created_at=datetime.now(timezone.utc),
        )
    ]
    service = ChatService(uow_factory=fake_uow_factory)

    result = await service.get_history(chat_guid=uuid.uuid4(), user_id=7)

    assert result[0]["sources"] == [{"doc_id": "d1"}]
