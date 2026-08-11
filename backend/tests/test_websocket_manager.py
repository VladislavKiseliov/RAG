from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from backend.services.messenger.websocket_manager import WebSocketManager


def _fake_socket() -> MagicMock:
    socket = MagicMock()
    socket.accept = AsyncMock()
    socket.send_text = AsyncMock()
    socket.send_json = AsyncMock()
    return socket


async def test_connect_socket_accepts():
    manager = WebSocketManager()
    socket = _fake_socket()

    await manager.connect_socket(socket)

    socket.accept.assert_awaited_once()


async def test_add_user_socket_connection():
    manager = WebSocketManager()
    socket = _fake_socket()

    await manager.add_user_socket_connection("user-1", socket)

    assert socket in manager.user_guid_to_websocket["user-1"]


async def test_send_to_user_sends_to_all_sockets_for_user():
    manager = WebSocketManager()
    socket_a, socket_b = _fake_socket(), _fake_socket()
    await manager.add_user_socket_connection("user-1", socket_a)
    await manager.add_user_socket_connection("user-1", socket_b)

    await manager.send_to_user("user-1", {"type": "ping"})

    socket_a.send_text.assert_awaited_once_with(json.dumps({"type": "ping"}))
    socket_b.send_text.assert_awaited_once_with(json.dumps({"type": "ping"}))


async def test_send_to_user_noop_when_no_sockets():
    manager = WebSocketManager()
    # Should not raise even though "unknown-user" was never connected.
    await manager.send_to_user("unknown-user", "hi")


async def test_send_to_user_accepts_plain_string_message():
    manager = WebSocketManager()
    socket = _fake_socket()
    await manager.add_user_socket_connection("user-1", socket)

    await manager.send_to_user("user-1", "raw-text")

    socket.send_text.assert_awaited_once_with("raw-text")


async def test_broadcast_to_users_sends_to_each_users_sockets():
    manager = WebSocketManager()
    socket_a, socket_b = _fake_socket(), _fake_socket()
    await manager.add_user_socket_connection("user-1", socket_a)
    await manager.add_user_socket_connection("user-2", socket_b)

    await manager.broadcast_to_users(["user-1", "user-2"], {"type": "notice"})

    socket_a.send_text.assert_awaited_once_with(json.dumps({"type": "notice"}))
    socket_b.send_text.assert_awaited_once_with(json.dumps({"type": "notice"}))


async def test_remove_user_guid_to_websocket_removes_socket_and_cleans_empty_entry():
    manager = WebSocketManager()
    socket = _fake_socket()
    await manager.add_user_socket_connection("user-1", socket)

    await manager.remove_user_guid_to_websocket("user-1", socket)

    assert "user-1" not in manager.user_guid_to_websocket


async def test_remove_user_guid_to_websocket_noop_for_unknown_user():
    manager = WebSocketManager()
    # Should not raise even though "unknown-user" was never connected.
    await manager.remove_user_guid_to_websocket("unknown-user", _fake_socket())
