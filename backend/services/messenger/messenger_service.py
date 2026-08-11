from typing import Callable
from uuid import UUID

from backend.schemas.schemas import DirectChatItem
from backend.services.unit_of_work import UnitOfWork
from backend.utils.exceptions import UserNotFoundError, ChatNotFoundError


class MessengerService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self._uow_factory = uow_factory

    async def create_direct_chat(self, user_id: int, friend_guid: UUID) -> DirectChatItem:
        async with self._uow_factory() as uow:
            friend = await uow.auth.get_user_by_guid(friend_guid)
            if not friend:
                raise UserNotFoundError("Пользователь не найден")
            chat = await uow.chats.create_direct_chat(creator_id=user_id, friend_id=friend.id)
            await uow.commit()
            await uow.refresh(chat)

        return DirectChatItem(
            chat_guid=chat.guid,
            friend_guid=friend.guid,
            friend_login=friend.login,
            friend_first_name=friend.first_name,
            friend_last_name=friend.last_name,
            updated_at=chat.updated_at,
        )

    async def delete_direct_chat(self, chat_guid: UUID, user_id: int) -> list[str]:
        async with self._uow_factory() as uow:
            chat_id = await uow.chats.get_chat_id_for_participant(chat_guid, user_id)
            if not chat_id:
                raise ChatNotFoundError()
            member_guids = await uow.chats.get_chat_member_guids(chat_id)
            await uow.chats.delete_chat(chat_id)
            await uow.commit()
        return member_guids

    async def get_user_chats(self, user_id: int) -> list[dict]:
        async with self._uow_factory() as uow:
            return await uow.chats.get_user_chats_with_details(user_id)

    async def get_chat_messages(self, chat_guid: UUID, user_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
        async with self._uow_factory() as uow:
            chat_id = await uow.chats.get_chat_id_by_guid(chat_guid)
            if not chat_id:
                raise ChatNotFoundError()
            is_member = await uow.chats.is_chat_participant(chat_id, user_id)
            if not is_member:
                raise ChatNotFoundError()
            messages = await uow.messages.get_messages_paginated(chat_id=chat_id, limit=limit, offset=offset)
        return [
            {
                "guid": str(m.guid),
                "content": m.content,
                "user_guid": str(m.user.guid) if m.user else None,
                "created_at": m.created_at,
            }
            for m in messages
        ]