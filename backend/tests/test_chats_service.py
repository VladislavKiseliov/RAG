from __future__ import annotations

import pytest
import uuid6
from sqlalchemy import select

from backend.models.database_models import Chats, Users
from backend.repository.repository import ChatRepository


@pytest.mark.asyncio
async def test_create_chat(chat_repository: ChatRepository, session_factory, test_user: Users) -> None:
    chat_id = uuid6.uuid7()
    title = "Тестовый чат"

    result = await chat_repository.create_chat(chat_id, test_user.id, title)

    async with session_factory() as session:
        created = await session.scalar(select(Chats).where(Chats.chat_id == chat_id))

    assert isinstance(result, Chats)
    assert result.chat_id == chat_id
    assert result.user_id == test_user.id
    assert result.title == title
    assert created is not None
    assert created.chat_id == chat_id
    assert created.user_id == test_user.id
    assert created.title == title


@pytest.mark.asyncio
async def test_get_all_chats_returns_only_user_chats_in_desc_order(
    chat_repository: ChatRepository,
    session_factory,
    test_user: Users,
) -> None:
    first_chat = await chat_repository.create_chat(uuid6.uuid7(), test_user.id, "Первый чат")
    second_chat = await chat_repository.create_chat(uuid6.uuid7(), test_user.id, "Второй чат")

    other_user = Users(login=f"chat-test-other-{uuid6.uuid7()}", password="test-password")
    async with session_factory() as session:
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

    try:
        await chat_repository.create_chat(uuid6.uuid7(), other_user.id, "Чужой чат")

        result = await chat_repository.get_all_chats(test_user.id)

        assert isinstance(result, list)
        assert all(isinstance(chat, Chats) for chat in result)
        assert [chat.chat_id for chat in result] == [second_chat.chat_id, first_chat.chat_id]
        assert all(chat.user_id == test_user.id for chat in result)
    finally:
        async with session_factory() as session:
            await session.delete(other_user)
            await session.commit()


@pytest.mark.asyncio
async def test_delete_chat_removes_existing_chat(chat_repository: ChatRepository, session_factory, test_user: Users) -> None:
    chat_id = uuid6.uuid7()
    await chat_repository.create_chat(chat_id, test_user.id, "Чат на удаление")

    deleted = await chat_repository.delete_chat(chat_id, test_user.id)

    async with session_factory() as session:
        exists = await session.scalar(select(Chats).where(Chats.chat_id == chat_id))

    assert deleted is True
    assert exists is None


@pytest.mark.asyncio
async def test_update_chat_title_changes_title(chat_repository: ChatRepository, session_factory, test_user: Users) -> None:
    chat_id = uuid6.uuid7()
    await chat_repository.create_chat(chat_id, test_user.id, "Старый заголовок")

    updated = await chat_repository.update_chat_title(chat_id, test_user.id, "Новый заголовок")

    async with session_factory() as session:
        chat = await session.scalar(select(Chats).where(Chats.chat_id == chat_id))

    assert updated is True
    assert chat is not None
    assert chat.title == "Новый заголовок"
