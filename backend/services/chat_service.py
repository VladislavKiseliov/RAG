import uuid

import uuid6
from uuid import UUID
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.utils.exceptions import UserNotFoundError, AuthDatabaseError, ChatNotFoundError
from backend.repository.repository import ChatRepository, MessageRepository


class ChatService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def create_chat(self, user_id: UUID, title: str = "Новый чат") -> str:
        chat_id = uuid6.uuid7()
        async with self._sf() as session:
            async with session.begin():
                result = await ChatRepository(session).create_chat(
                    chat_id=chat_id, user_id=user_id, title=title
                )
        if not result:
            raise AuthDatabaseError("Не удалось создать чат")
        return str(chat_id)

    async def get_all_previews(self, user_id: UUID) -> List[Dict[str, Any]]:
        async with self._sf() as session:
            chats = await ChatRepository(session).get_all_chats(user_id)
            return [
                {"id": str(chat.chat_id), "title": chat.title or "Новый чат"}
                for chat in chats
            ]

    async def rename_chat(self, user_id: uuid.UUID, chat_id: uuid.UUID, new_title: str) -> bool:
        async with self._sf() as session:
            async with session.begin():
                updated = await ChatRepository(session).update_chat_title(chat_id, user_id, new_title)
        if not updated:
            raise UserNotFoundError("Чат не найден или доступ запрещен")
        return True

    async def delete_chat(self, user_id: UUID, chat_id: UUID) -> bool:
        async with self._sf() as session:
            async with session.begin():
                deleted = await ChatRepository(session).delete_chat(chat_id=chat_id, user_id=user_id)
        if not deleted:
            raise UserNotFoundError("Не удалось удалить чат")
        return True

    async def get_history(self, chat_id: uuid.UUID,user_id:uuid.UUID) -> List[Dict]:
        async with self._sf() as session:
            chat = await ChatRepository(session).get_chat(chat_id)
            if chat is None or chat.user_id != user_id:
                raise ChatNotFoundError()

            messages = await MessageRepository(session).get_history(chat_id=chat_id)
            return [
                {"role": msg.role, "content": msg.content, "sources": msg.sources, "created_at": msg.created_at}
                for msg in messages
            ]



