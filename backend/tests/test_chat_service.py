from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.chat_service import ChatService
from backend.utils.exceptions import AuthDatabaseError, UserNotFoundError


@pytest.fixture
def chat_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def message_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(chat_repo: AsyncMock, message_repo: AsyncMock) -> ChatService:
    return ChatService(chat_repo=chat_repo, message_repo=message_repo)


@pytest.mark.asyncio
async def test_create_chat_returns_created_chat_id(service: ChatService, chat_repo: AsyncMock) -> None:
    user_id = uuid.uuid4()
    chat_repo.create_chat.return_value = SimpleNamespace(chat_id=uuid.uuid4())

    result = await service.create_chat(user_id, title='Новый чат')

    assert isinstance(result, str)
    chat_repo.create_chat.assert_awaited_once()
    args = chat_repo.create_chat.await_args.args
    assert args[1] == user_id
    assert args[2] == 'Новый чат'


@pytest.mark.asyncio
async def test_create_chat_raises_when_repository_returns_empty(service: ChatService, chat_repo: AsyncMock) -> None:
    chat_repo.create_chat.return_value = None

    with pytest.raises(AuthDatabaseError):
        await service.create_chat(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_all_previews_maps_repository_result(service: ChatService, chat_repo: AsyncMock) -> None:
    chat_repo.get_all_chats.return_value = [
        SimpleNamespace(chat_id=uuid.uuid4(), title='Первый'),
        SimpleNamespace(chat_id=uuid.uuid4(), title=''),
    ]

    result = await service.get_all_previews(uuid.uuid4())

    assert result == [
        {'id': str(chat_repo.get_all_chats.return_value[0].chat_id), 'title': 'Первый'},
        {'id': str(chat_repo.get_all_chats.return_value[1].chat_id), 'title': 'Новый чат'},
    ]


@pytest.mark.asyncio
async def test_rename_chat_raises_when_chat_not_found(service: ChatService, chat_repo: AsyncMock) -> None:
    chat_repo.update_chat_title.return_value = False

    with pytest.raises(UserNotFoundError):
        await service.rename_chat(uuid.uuid4(), uuid.uuid4(), 'Новый заголовок')


@pytest.mark.asyncio
async def test_delete_chat_raises_when_chat_not_found(service: ChatService, chat_repo: AsyncMock) -> None:
    chat_repo.delete_chat.return_value = False

    with pytest.raises(UserNotFoundError):
        await service.delete_chat(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_get_history_maps_messages(service: ChatService, message_repo: AsyncMock) -> None:
    created_at = datetime.utcnow()
    message_repo.get_history.return_value = [
        SimpleNamespace(role='user', content='Привет', created_at=created_at),
        SimpleNamespace(role='assistant', content='Ответ', created_at=created_at),
    ]

    result = await service.get_history(uuid.uuid4())

    assert result == [
        {'role': 'user', 'content': 'Привет', 'created_at': created_at},
        {'role': 'assistant', 'content': 'Ответ', 'created_at': created_at},
    ]


@pytest.mark.asyncio
async def test_process_message_saves_user_and_assistant_messages(monkeypatch: pytest.MonkeyPatch, service: ChatService, message_repo: AsyncMock) -> None:
    monkeypatch.setattr(
        'backend.app.services.ChatService.get_llm_answer',
        AsyncMock(return_value={'answer': 'Готовый ответ', 'sources': [{'doc_id': '1'}]}),
    )
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()

    result = await service.process_message(user_id, chat_id, 'Вопрос')

    assert result == {
        'response': 'Готовый ответ',
        'sources': [{'doc_id': '1'}],
    }
    assert message_repo.add_message.await_count == 2
    first_call = message_repo.add_message.await_args_list[0].args
    second_call = message_repo.add_message.await_args_list[1].args
    assert first_call == (chat_id, 'user', 'Вопрос')
    assert second_call == (chat_id, 'assistant', 'Готовый ответ')
