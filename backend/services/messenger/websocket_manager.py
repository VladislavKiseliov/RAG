import asyncio
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.handlers: dict = {}
        self.user_guid_to_websocket: dict[str, set[WebSocket]] = {}

    def handler(self, message_type: str):
        def decorator(func):
            self.handlers[message_type] = func
            return func
        return decorator

    async def connect_socket(self, websocket: WebSocket):
        await websocket.accept()

    async def add_user_socket_connection(self, user_guid: str, websocket: WebSocket):
        self.user_guid_to_websocket.setdefault(user_guid, set()).add(websocket)

    async def send_to_user(self, user_guid: str, message: str | dict) -> None:
        if isinstance(message, dict):
            message = json.dumps(message)
        sockets = self.user_guid_to_websocket.get(user_guid, set())
        if not sockets:
            return
        await asyncio.gather(
            *[socket.send_text(message) for socket in sockets],
            return_exceptions=True,
        )

    async def broadcast_to_users(self, user_guids: list[str], message: str | dict) -> None:
        if isinstance(message, dict):
            message = json.dumps(message)
        tasks = []
        for u_guid in user_guids:
            sockets = self.user_guid_to_websocket.get(u_guid, set())
            for socket in sockets:
                tasks.append(socket.send_text(message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def remove_user_guid_to_websocket(self, user_guid: str, websocket: WebSocket):
        if user_guid not in self.user_guid_to_websocket:
            return
        self.user_guid_to_websocket[user_guid].discard(websocket)
        if not self.user_guid_to_websocket[user_guid]:
            del self.user_guid_to_websocket[user_guid]

    async def send_error(self, message: str, websocket: WebSocket):
        await websocket.send_json({"status": "error", "message": message})