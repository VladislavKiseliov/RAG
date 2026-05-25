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
    first = await message_repository.add_message(test_chat.chat_id, "user", "Первое")
    second = await message_repository.add_message(test_chat.chat_id, "assistant", "Второе")
    third = await message_repository.add_message(test_chat.chat_id, "user", "Третье")

    history = await message_repository.get_history(test_chat.chat_id)

    ids = [m.id for m in history]
    assert first.id in ids
    assert ids.index(first.id) < ids.index(second.id) < ids.index(third.id)


@pytest.mark.asyncio
async def test_get_history_respects_limit(message_repository: MessageRepository, test_chat) -> None:
    for i in range(5):
        await message_repository.add_message(test_chat.chat_id, "user", f"Сообщение {i}")

    history = await message_repository.get_history(test_chat.chat_id, limit=3)

    assert len(history) == 3


# --- get_recent ---

@pytest.mark.asyncio
async def test_get_recent_returns_last_n_in_ascending_order(message_repository: MessageRepository, test_chat) -> None:
    msgs = []
    for i in range(5):
        m = await message_repository.add_message(test_chat.chat_id, "user", f"Msg {i}")
        msgs.append(m)

    recent = await message_repository.get_recent(test_chat.chat_id, limit=3)

    assert len(recent) == 3
    # последние 3 из 5
    assert recent[0].id == msgs[2].id
    assert recent[1].id == msgs[3].id
    assert recent[2].id == msgs[4].id
    # хронологический порядок (asc)
    assert recent[0].id < recent[1].id < recent[2].id


@pytest.mark.asyncio
async def test_get_recent_returns_all_when_fewer_than_limit(message_repository: MessageRepository, test_chat) -> None:
    await message_repository.add_message(test_chat.chat_id, "user", "Одно сообщение")

    recent = await message_repository.get_recent(test_chat.chat_id, limit=10)

    assert len(recent) == 1


@pytest.mark.asyncio
async def test_get_recent_empty_chat(message_repository: MessageRepository, test_chat) -> None:
    recent = await message_repository.get_recent(test_chat.chat_id, limit=10)

    assert recent == []


# --- count_after ---

@pytest.mark.asyncio
async def test_count_after_without_anchor_counts_all(message_repository: MessageRepository, test_chat) -> None:
    for i in range(4):
        await message_repository.add_message(test_chat.chat_id, "user", f"Msg {i}")

    count = await message_repository.count_after(test_chat.chat_id, after_id=None)

    assert count == 4


@pytest.mark.asyncio
async def test_count_after_with_anchor_counts_only_newer(message_repository: MessageRepository, test_chat) -> None:
    first = await message_repository.add_message(test_chat.chat_id, "user", "Первое")
    await message_repository.add_message(test_chat.chat_id, "assistant", "Второе")
    await message_repository.add_message(test_chat.chat_id, "user", "Третье")

    count = await message_repository.count_after(test_chat.chat_id, after_id=first.id)

    assert count == 2


@pytest.mark.asyncio
async def test_count_after_anchor_at_last_message_returns_zero(message_repository: MessageRepository, test_chat) -> None:
    await message_repository.add_message(test_chat.chat_id, "user", "Первое")
    last = await message_repository.add_message(test_chat.chat_id, "assistant", "Последнее")

    count = await message_repository.count_after(test_chat.chat_id, after_id=last.id)

    assert count == 0


# --- get_messages_after ---

@pytest.mark.asyncio
async def test_get_messages_after_without_anchor_returns_first_n(message_repository: MessageRepository, test_chat) -> None:
    msgs = []
    for i in range(5):
        m = await message_repository.add_message(test_chat.chat_id, "user", f"Msg {i}")
        msgs.append(m)

    result = await message_repository.get_messages_after(test_chat.chat_id, after_id=None, limit=3)

    assert len(result) == 3
    assert result[0].id == msgs[0].id
    assert result[1].id == msgs[1].id
    assert result[2].id == msgs[2].id


@pytest.mark.asyncio
async def test_get_messages_after_with_anchor_skips_anchor_and_older(message_repository: MessageRepository, test_chat) -> None:
    first = await message_repository.add_message(test_chat.chat_id, "user", "Первое")
    second = await message_repository.add_message(test_chat.chat_id, "assistant", "Второе")
    third = await message_repository.add_message(test_chat.chat_id, "user", "Третье")

    result = await message_repository.get_messages_after(test_chat.chat_id, after_id=first.id, limit=10)

    ids = [m.id for m in result]
    assert first.id not in ids
    assert second.id in ids
    assert third.id in ids


@pytest.mark.asyncio
async def test_get_messages_after_respects_limit(message_repository: MessageRepository, test_chat) -> None:
    anchor = await message_repository.add_message(test_chat.chat_id, "user", "Anchor")
    for i in range(5):
        await message_repository.add_message(test_chat.chat_id, "user", f"After {i}")

    result = await message_repository.get_messages_after(test_chat.chat_id, after_id=anchor.id, limit=3)

    assert len(result) == 3
