import uuid
from typing import List

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.models.database_models import Chats, Messages
from backend.services.unit_of_work import UnitOfWork


class ChatNotFoundError(Exception):
    def __init__(self, chat_guid: str):
        super().__init__(f"Chat {chat_guid} not found")
        self.chat_guid = chat_guid


class MessageService:
    def __init__(self, session_factory: async_sessionmaker):
        self._sf = session_factory

    async def resolve_chat(self, chat_guid: str, chats: dict) -> tuple[int, bool]:
        if chat_guid in chats:
            return chats[chat_guid], False

        async with UnitOfWork(self._sf) as uow:
            chat_id = await uow.chats.get_chat_id_by_guid(chat_guid)

        if not chat_id:
            raise ChatNotFoundError(chat_guid)

        chats[chat_guid] = chat_id
        return chat_id, True

    async def get_chat_member_guids(self, chat_id: int) -> List[str]:
        async with UnitOfWork(self._sf) as uow:
            return await uow.chats.get_chat_member_guids(chat_id)

    async def save_message(self, content: str, chat_id: int, user_id: int) -> tuple[Messages, Chats]:
        async with UnitOfWork(self._sf) as uow:
            message = await uow.messages.add_message(chat_id=chat_id, content=content, user_id=user_id)
            chat = await uow.chats.touch(chat_id)
            await uow.commit()
            await uow.refresh(message, ["user", "chat"])
            await uow.refresh(chat, ["users"])
        return message, chat

    async def mark_message_read(
        self, message_guid: str, chat_guid: str, chats: dict, user_id: int
    ) -> Messages | None:
        chat_id, _ = await self.resolve_chat(chat_guid, chats)

        async with UnitOfWork(self._sf) as uow:
            message = await uow.messenger.get_message_by_guid(uuid.UUID(message_guid))
            if not message:
                return None
            await uow.messenger.upsert_read_status(user_id, chat_id, message.id)
            await uow.commit()
            await uow.refresh(message)
        return message