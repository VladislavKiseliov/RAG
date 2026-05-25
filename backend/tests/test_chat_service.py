from __future__ import annotations

import uuid
import pytest

from backend.services.chat_service import ChatService
from backend.utils.exceptions import UserNotFoundError


@pytest.fixture
def service(session_factory) -> ChatService:
    return ChatService(session_factory=session_factory)


@pytest.mark.asyncio
async def test_create_chat_returns_str_uuid(service: ChatService, test_user) -> None:
    result = await service.create_chat(test_user.id)

    assert isinstance(result, str)
    uuid.UUID(result)


@pytest.mark.asyncio
async def test_get_all_previews_returns_own_chats(service: ChatService, test_user) -> None:
    await service.create_chat(test_user.id, title="Чат A")
    await service.create_chat(test_user.id, title="Чат B")

    result = await service.get_all_previews(test_user.id)

    assert isinstance(result, list)
    titles = [c["title"] for c in result]
    assert "Чат A" in titles
    assert "Чат B" in titles


@pytest.mark.asyncio
async def test_get_history_returns_messages_with_all_fields(service: ChatService, test_chat) -> None:
    history = await service.get_history(test_chat.chat_id)

    assert isinstance(history, list)
    if history:
        assert {"role", "content", "sources", "created_at"} <= history[0].keys()


@pytest.mark.asyncio
async def test_rename_chat_raises_when_not_found(service: ChatService, test_user) -> None:
    with pytest.raises(UserNotFoundError):
        await service.rename_chat(test_user.id, uuid.uuid4(), "Новый заголовок")


@pytest.mark.asyncio
async def test_delete_chat_raises_when_not_found(service: ChatService, test_user) -> None:
    with pytest.raises(UserNotFoundError):
        await service.delete_chat(test_user.id, uuid.uuid4())