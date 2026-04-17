from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.models.database_models import Messages
from backend.repository.repository import MessageRepository


@pytest.mark.asyncio
async def test_add_message_persists_message(message_repository: MessageRepository, session_factory, test_chat) -> None:
    result = await message_repository.add_message(
        chat_id=test_chat.chat_id,
        role="user",
        content="Первое сообщение",
    )

    async with session_factory() as session:
        stored = await session.scalar(select(Messages).where(Messages.id == result.id))

    assert isinstance(result, Messages)
    assert result.id is not None
    assert result.chat_id == test_chat.chat_id
    assert result.role == "user"
    assert result.content == "Первое сообщение"
    assert stored is not None
    assert stored.id == result.id
    assert stored.chat_id == test_chat.chat_id


@pytest.mark.asyncio
async def test_get_history_returns_messages_in_ascending_order(message_repository: MessageRepository, test_chat) -> None:
    first = await message_repository.add_message(test_chat.chat_id, "user", "Первое сообщение")
    second = await message_repository.add_message(test_chat.chat_id, "assistant", "Второе сообщение")
    third = await message_repository.add_message(test_chat.chat_id, "user", "Третье сообщение")

    history = await message_repository.get_history(test_chat.chat_id)

    assert isinstance(history, list)
    assert all(isinstance(message, Messages) for message in history)
    assert [message.id for message in history] == [first.id, second.id, third.id]
    assert [message.content for message in history] == [
        "Первое сообщение",
        "Второе сообщение",
        "Третье сообщение",
    ]


@pytest.mark.asyncio
async def test_get_history_respects_limit(message_repository: MessageRepository, test_chat) -> None:
    await message_repository.add_message(test_chat.chat_id, "user", "Первое сообщение")
    await message_repository.add_message(test_chat.chat_id, "assistant", "Второе сообщение")
    await message_repository.add_message(test_chat.chat_id, "user", "Третье сообщение")

    history = await message_repository.get_history(test_chat.chat_id, limit=2)

    assert len(history) == 2
    assert [message.content for message in history] == [
        "Первое сообщение",
        "Второе сообщение",
    ]
