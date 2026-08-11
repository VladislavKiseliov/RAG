from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.database_models import Chats
from backend.services.ai.conversation_service import SUMMARY_THRESHOLD, ConversationService
from backend.utils.exceptions import ChatNotFoundError


@pytest.fixture
def fake_llm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(session_factory, fake_llm) -> ConversationService:
    return ConversationService(session_factory=session_factory, llm_client=fake_llm)


async def test_process_message_rejects_non_participant(service, alice, test_direct_chat):
    with pytest.raises(ChatNotFoundError):
        await service.process_message(user_id=alice.id, chat_guid=test_direct_chat.guid, content="x")


async def test_process_message_persists_and_uses_llm(
    service, fake_llm, message_repository, test_user, test_ai_chat, monkeypatch
):
    monkeypatch.setattr(service, "_trigger_summary_in_background", MagicMock())
    fake_llm.get_answer.return_value = {"answer": "42", "sources": [{"doc": "x"}], "degraded": False}

    result = await service.process_message(user_id=test_user.id, chat_guid=test_ai_chat.guid, content="question")

    assert result == {"response": "42", "sources": [{"doc": "x"}]}
    fake_llm.get_answer.assert_awaited_once()
    service._trigger_summary_in_background.assert_called_once()

    history = await message_repository.get_history(test_ai_chat.id)
    contents = [m.content for m in history]
    assert "question" in contents
    assert "42" in contents


async def test_process_message_does_not_persist_degraded_response(
    service, fake_llm, message_repository, test_user, test_ai_chat, monkeypatch
):
    monkeypatch.setattr(service, "_trigger_summary_in_background", MagicMock())
    fake_llm.get_answer.return_value = {"answer": "degraded note", "sources": [], "degraded": True}

    result = await service.process_message(user_id=test_user.id, chat_guid=test_ai_chat.guid, content="q2")

    assert result["response"] == "degraded note"
    history = await message_repository.get_history(test_ai_chat.id)
    contents = [m.content for m in history]
    assert "q2" in contents
    assert "degraded note" not in contents


async def test_ensure_chat_exists_rejects_non_participant(service, alice, test_direct_chat):
    with pytest.raises(ChatNotFoundError):
        await service.ensure_chat_exists(test_direct_chat.guid, alice.id)


async def test_ensure_chat_exists_passes_for_participant(service, test_user, test_direct_chat):
    await service.ensure_chat_exists(test_direct_chat.guid, test_user.id)


async def test_get_context_chat(service, message_repository, test_user, test_ai_chat):
    await message_repository.add_message(test_ai_chat.id, content="hist", role="user")

    result = await service.get_context_chat(test_ai_chat.guid, test_user.id)

    assert result["summary"] is None
    assert any(m["content"] == "hist" for m in result["messages"])


async def test_update_summary_noop_when_no_new_messages(service, fake_llm, test_ai_chat):
    await service.update_summary(test_ai_chat.id)
    fake_llm.get_summary.assert_not_awaited()


async def test_update_summary_calls_llm_and_persists(
    service, fake_llm, message_repository, test_ai_chat, session_factory
):
    for i in range(3):
        await message_repository.add_message(test_ai_chat.id, content=f"m{i}", role="user")
    fake_llm.get_summary.return_value = "new summary text"

    await service.update_summary(test_ai_chat.id)

    fake_llm.get_summary.assert_awaited_once()
    async with session_factory() as session:
        chat = await session.get(Chats, test_ai_chat.id)
    assert chat.summary == "new summary text"
    assert chat.summary_link is not None


async def test_maybe_trigger_summary_below_threshold_skips_llm(service, fake_llm, message_repository, test_ai_chat):
    await message_repository.add_message(test_ai_chat.id, content="one")

    await service._maybe_trigger_summary(test_ai_chat.id, summary_link=None)

    fake_llm.get_summary.assert_not_awaited()


async def test_maybe_trigger_summary_at_threshold_triggers_update(
    service, fake_llm, message_repository, test_ai_chat
):
    for i in range(SUMMARY_THRESHOLD):
        await message_repository.add_message(test_ai_chat.id, content=f"m{i}")
    fake_llm.get_summary.return_value = "s"

    await service._maybe_trigger_summary(test_ai_chat.id, summary_link=None)

    fake_llm.get_summary.assert_awaited_once()
