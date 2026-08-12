from __future__ import annotations

import pytest_asyncio

from backend.models.database_models import ChatType


@pytest_asyncio.fixture
async def foreign_chat(chat_repository, test_user_bob):
    """A chat `test_user` is deliberately NOT a participant of."""
    chat = await chat_repository.create_chat(
        user_id=test_user_bob.id, title="Bob's chat", chat_type=ChatType.AI_DIRECT
    )
    try:
        yield chat
    finally:
        await chat_repository.delete_chat(chat.id)


async def test_non_participant_gets_404_on_send_message(
    api_client, make_token, test_user, foreign_chat,
):
    """Regression for backend_critical_fixes_2026_08_03 (B2): ConversationService
    used to resolve chats via get_chat_by_guid (no participant check) - any
    authenticated user could message/stream into any chat by guessing/knowing its
    guid. Fixed via get_chat_by_guid_for_participant; this pins the fix at the
    real route, not just the service layer (already unit-tested separately)."""
    token = make_token(test_user)

    response = api_client.post(
        f"/api/chats/{foreign_chat.guid}/messages",
        json={"user_message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_non_participant_gets_404_on_stream_message(
    api_client, make_token, test_user, foreign_chat,
):
    """Same bug, streaming variant - guarded by _validate_stream_chat_exists
    (a Depends resolved before the route body, since the body is itself an
    async generator and can't raise cleanly after headers are sent)."""
    token = make_token(test_user)

    response = api_client.post(
        f"/api/chats/{foreign_chat.guid}/messages/stream",
        json={"user_message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
