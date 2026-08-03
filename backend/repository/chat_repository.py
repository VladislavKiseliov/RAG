import enum
from typing import List, Dict, Optional
import uuid
from datetime import datetime


from sqlalchemy import select, update, delete, insert, func

from backend.models.database_models import Chats, Messages, ReadStatus, Users, ChatType, chat_participant
from backend.repository.base_repository import BaseRepository
from backend.schemas.schemas import DirectChatItem


class ChatRepository(BaseRepository):
    """Управление чатами (создание, переименование, удаление)."""

    async def create_chat(self, user_id: int, title: str, chat_type: Optional[ChatType]) -> Chats:
        chat = Chats(chat_type=chat_type, title=title, created_by_id=user_id)
        self._session.add(chat)
        await self._session.flush()
        await self._session.execute(
            insert(chat_participant).values({"user_id": user_id, "chat_id": chat.id})
        )
        await self._session.flush()
        return chat

    async def delete_chat(self, chat_id: int) -> bool:
        stmt = delete(Chats).where(Chats.id == chat_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def update_chat_title(self, chat_id: int, new_title: str) -> bool:
        stmt = (
            update(Chats)
            .where(Chats.id == chat_id)
            .values(title=new_title, updated_at=datetime.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_chat(self,chat_id: int) -> Chats:
        stmt = select(Chats).where(Chats.id == chat_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_active_chats(self,user_id:int, chat_type: Optional[ChatType] = None) -> list[Chats]:
        """
        Достает чаты пользователя. Если задан chat_type — фильтрует по нему.
        Если chat_type == None — отдает всё.
        """
        query = (
            select(Chats)
            .join(chat_participant, Chats.id == chat_participant.c.chat_id)
            .where(
                chat_participant.c.user_id == user_id
            )
            .order_by(Chats.updated_at.desc())
        )
        if chat_type is not None:
            query = query.where(Chats.chat_type == chat_type)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_chat_member_guids(self, chat_id: int) -> list[str]:
        """
        Супер-быстрый запрос: получает строковые UUID участников чата по его числовому ID.
        """
        query = (
            select(Users.guid)
            .join(chat_participant, chat_participant.c.user_id == Users.id)
            .where(chat_participant.c.chat_id == chat_id)
        )

        result = await self._session.execute(query)

        return [str(guid) for guid in result.scalars().all()]

    async def get_chat_by_guid(self, chat_guid: uuid.UUID) -> Chats | None:
        stmt = select(Chats).where(Chats.guid == chat_guid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chat_by_guid_for_participant(self, chat_guid: uuid.UUID, user_id: int) -> Chats | None:
        """Как get_chat_by_guid, но только если user_id — участник чата.

        Использовать вместо get_chat_by_guid везде, где chat_guid приходит от клиента
        и нужно вернуть чат конкретному пользователю (не просто проверить, что чат
        существует) — иначе любой аутентифицированный пользователь, узнавший чужой
        chat_guid, читает/пишет в чужой чат (см. ConversationService).
        """
        stmt = (
            select(Chats)
            .join(chat_participant, Chats.id == chat_participant.c.chat_id)
            .where(Chats.guid == chat_guid)
            .where(chat_participant.c.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chat_id_by_guid(self, chat_guid: uuid.UUID) -> int | None:
        query = select(Chats.id).where(Chats.guid == chat_guid)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_chat_id_for_participant(self, chat_guid: uuid.UUID, user_id: int) -> int | None:
        stmt = (
            select(Chats.id)
            .join(chat_participant, Chats.id == chat_participant.c.chat_id)
            .where(Chats.guid == chat_guid)
            .where(chat_participant.c.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_direct_chat(self, creator_id: int, friend_id: int) -> Chats:
        chat = Chats(chat_type=ChatType.DIRECT, created_by_id=creator_id)
        self._session.add(chat)
        await self._session.flush()
        await self._session.execute(
            insert(chat_participant).values([
                {"user_id": creator_id, "chat_id": chat.id},
                {"user_id": friend_id, "chat_id": chat.id},
            ])
        )
        await self._session.flush()
        return chat

    async def get_user_chats_with_details(self, user_id: int) -> list[dict]:
        # Subquery: последнее сообщение в каждом чате
        last_msg_subq = (
            select(Messages.chat_id, func.max(Messages.id).label("max_id"))
            .group_by(Messages.chat_id)
            .subquery()
        )
        # Алиас для участника-собеседника
        cp_friend = chat_participant.alias("cp_friend")

        stmt = (
            select(
                Chats.guid,
                Chats.updated_at,
                Messages.content.label("last_message_content"),
                Messages.created_at.label("last_message_at"),
                Users.guid.label("friend_guid"),
                Users.login.label("friend_login"),
                Users.first_name.label("friend_first_name"),
                Users.last_name.label("friend_last_name"),
                ReadStatus.last_read_message_id,
            )
            .join(chat_participant, (chat_participant.c.chat_id == Chats.id) & (chat_participant.c.user_id == user_id))
            .join(cp_friend, (cp_friend.c.chat_id == Chats.id) & (cp_friend.c.user_id != user_id))
            .join(Users, Users.id == cp_friend.c.user_id)
            .outerjoin(last_msg_subq, last_msg_subq.c.chat_id == Chats.id)
            .outerjoin(Messages, Messages.id == last_msg_subq.c.max_id)
            .outerjoin(ReadStatus, (ReadStatus.chat_id == Chats.id) & (ReadStatus.user_id == user_id))
            .where(Chats.chat_type == ChatType.DIRECT)
            .order_by(Chats.updated_at.desc())
        )

        result = await self._session.execute(stmt)
        return [
            DirectChatItem(
                chat_guid=row.guid,
                friend_guid=row.friend_guid,
                friend_login=row.friend_login,
                friend_first_name=row.friend_first_name,
                friend_last_name=row.friend_last_name,
                last_message_content=row.last_message_content,
                updated_at=row.updated_at,
            )
            for row in result.all()
        ]

    async def is_chat_participant(self, chat_id: int, user_id: int) -> bool:
        stmt = select(chat_participant.c.user_id).where(
            (chat_participant.c.chat_id == chat_id) & (chat_participant.c.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def touch(self, chat_id: int) -> Chats:
        chat = await self._session.get(Chats, chat_id)
        chat.updated_at = datetime.now()
        return chat
