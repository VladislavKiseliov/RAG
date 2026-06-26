import uuid
from typing import List, Dict, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.schemas.schemas import ChatBaseSchema
from backend.models.database_models import ChatType
from backend.services.unit_of_work import UnitOfWork
from backend.utils.exceptions import UserNotFoundError, AuthDatabaseError, ChatNotFoundError


class ChatService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def _resolve_chat_for_user(self, uow, chat_guid: uuid.UUID, user_id: int) -> int:
        chat_id = await uow.chats.get_chat_id_for_participant(chat_guid=chat_guid, user_id=user_id)
        if not chat_id:
            raise ChatNotFoundError()
        return chat_id

    async def create_chat(self, user_id: int, chat_type: Optional[ChatType], title: str = "Новый чат") -> ChatBaseSchema:
        async with UnitOfWork(self._sf) as uow:
            chat = await uow.chats.create_chat(user_id=user_id, chat_type=chat_type, title=title)
            await uow.commit()
        if not chat:
            raise AuthDatabaseError("Не удалось создать чат")
        return ChatBaseSchema.model_validate(chat)

    async def get_user_active_chats(self, user_id: int, chat_type: Optional[ChatType] = None) -> list[ChatBaseSchema]:
        async with UnitOfWork(self._sf) as uow:
            chats = await uow.chats.get_user_active_chats(user_id, chat_type)
            return [ChatBaseSchema.model_validate(c) for c in chats]

    async def update_chat_title(self, chat_guid: uuid.UUID, user_id: int, new_title: str) -> bool:
        async with UnitOfWork(self._sf) as uow:
            chat_id = await self._resolve_chat_for_user(uow, chat_guid, user_id)
            updated = await uow.chats.update_chat_title(chat_id=chat_id, new_title=new_title)
            await uow.commit()
        if not updated:
            raise UserNotFoundError("Чат не найден или доступ запрещен")
        return True

    async def delete_chat(self, chat_guid: uuid.UUID, user_id: int) -> bool:
        async with UnitOfWork(self._sf) as uow:
            chat_id = await self._resolve_chat_for_user(uow, chat_guid, user_id)
            deleted = await uow.chats.delete_chat(chat_id=chat_id)
            await uow.commit()
        if not deleted:
            raise UserNotFoundError("Не удалось удалить чат")
        return True

    async def get_history(self, chat_guid: uuid.UUID, user_id: int) -> List[Dict]:
        async with UnitOfWork(self._sf) as uow:
            chat_id = await self._resolve_chat_for_user(uow, chat_guid, user_id)
            messages = await uow.messages.get_history(chat_id=chat_id)
            return [
                {"role": msg.role, "content": msg.content, "sources": msg.sources, "created_at": msg.created_at}
                for msg in messages
            ]