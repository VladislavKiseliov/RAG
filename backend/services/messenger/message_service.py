import uuid
from typing import Callable, List

from backend.models.database_models import Chats, Messages
from backend.services.unit_of_work import UnitOfWork


class ChatNotFoundError(Exception):
    def __init__(self, chat_guid: str):
        super().__init__(f"Chat {chat_guid} not found")
        self.chat_guid = chat_guid


class MessageService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self._uow_factory = uow_factory

    async def resolve_chat(self, chat_guid: str, chats: dict, user_id: int) -> tuple[int, bool]:
        if chat_guid in chats:
            return chats[chat_guid], False

        async with self._uow_factory() as uow:
            # get_chat_id_for_participant (не get_chat_id_by_guid) — иначе любой
            # аутентифицированный пользователь, знающий/угадавший chat_guid чужого
            # чата, резолвил бы его chat_id и писал/читал в этом чате.
            chat_id = await uow.chats.get_chat_id_for_participant(chat_guid, user_id)

        if not chat_id:
            raise ChatNotFoundError(chat_guid)

        chats[chat_guid] = chat_id
        return chat_id, True

    async def get_chat_member_guids(self, chat_id: int) -> List[str]:
        async with self._uow_factory() as uow:
            return await uow.chats.get_chat_member_guids(chat_id)

    async def save_message(
        self, content: str, chat_id: int, user_id: int, client_msg_id: uuid.UUID | None = None,
    ) -> tuple[Messages, Chats]:
        async with self._uow_factory() as uow:
            # Идемпотентность: outbox-очередь на фронте может повторить отправку того же
            # client_msg_id после реконнекта — не создаём дубль, отдаём уже сохранённое.
            if client_msg_id is not None:
                existing = await uow.messages.get_by_client_msg_id(chat_id, client_msg_id)
                if existing is not None:
                    chat = await uow.chats.touch(chat_id)
                    await uow.commit()
                    await uow.refresh(chat, ["users"])
                    return existing, chat

            message = await uow.messages.add_message(
                chat_id=chat_id, content=content, user_id=user_id, client_msg_id=client_msg_id,
            )
            chat = await uow.chats.touch(chat_id)
            await uow.commit()
            await uow.refresh(message, ["user", "chat"])
            await uow.refresh(chat, ["users"])
        return message, chat

    async def mark_message_read(
        self, message_guid: str, chat_guid: str, chats: dict, user_id: int
    ) -> Messages | None:
        chat_id, _ = await self.resolve_chat(chat_guid, chats, user_id)

        async with self._uow_factory() as uow:
            message = await uow.messenger.get_message_by_guid(uuid.UUID(message_guid))
            if not message:
                return None
            await uow.messenger.upsert_read_status(user_id, chat_id, message.id)
            await uow.commit()
            await uow.refresh(message)
        return message