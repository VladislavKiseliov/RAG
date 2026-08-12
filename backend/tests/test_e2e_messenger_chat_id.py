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


def test_auth_handshake_keeps_connection_open(api_client, make_token, test_user):
    """Sanity check the WS auth handshake itself before testing the actual bug below:
    the first frame must be {"type": "auth", "token": ...} (websocket_router.py) - if
    that's rejected the socket closes immediately (code 1008) and every later assertion
    would be meaningless. Confirmed alive by dispatching an unknown message type and
    getting the router's own "not found" error back, not a disconnect."""
    token = make_token(test_user)

    with api_client.websocket_connect("/websocket/ws/") as ws:
        ws.send_json({"type": "auth", "token": token})

        ws.send_json({"type": "__no_such_type__"})
        response = ws.receive_json()

    assert response == {"status": "error", "message": "Type: __no_such_type__ was not found"}


def test_add_user_to_chat_rejects_non_participant(api_client, make_token, test_user, foreign_chat):
    """Regression for backend_critical_fixes_2026_08_03 (B1): MessageService.resolve_chat
    used to resolve chat_guid->chat_id via get_chat_id_by_guid (no participant check), and
    add_user_to_chat_handler accepted a client-supplied chat_id directly with zero
    validation. Fixed by requiring user_id in resolve_chat() and using
    get_chat_id_for_participant; the trusted client chat_id field was removed from
    AddUserToChatSchema entirely - this pins the fix at the real WS message-loop, not
    just the service layer (already unit-tested separately)."""
    token = make_token(test_user)

    with api_client.websocket_connect("/websocket/ws/") as ws:
        ws.send_json({"type": "auth", "token": token})

        ws.send_json({"type": "add_user_to_chat", "chat_guid": str(foreign_chat.guid)})
        response = ws.receive_json()

    assert response == {
        "status": "error",
        "message": f"Chat {foreign_chat.guid} does not exist",
    }
