from typing import List

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from backend.models.database_models import Messages
from backend.repository.base_repository import BaseRepository


class MessageRepository(BaseRepository):
    """Работа с сообщениями внутри чатов."""

    async def add_message(
        self,
        chat_id: int,
        content: str,
        role: str | None = None,
        user_id: int | None = None,
        sources: list | None = None,
    ) -> Messages:
        message = Messages(chat_id=chat_id, content=content, role=role, user_id=user_id, sources=sources)
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_history(self, chat_id: int, limit: int = 50) -> List[Messages]:
        # ASC + LIMIT брал первые N сообщений (самые старые), а не последние N -
        # в чате длиннее limit новые сообщения (в т.ч. только что отправленное)
        # никогда не попадали в ответ, хотя были в БД. DESC + reverse - тот же
        # паттерн, что уже верно сделан в get_recent() ниже.
        stmt = (
            select(Messages)
            .where(Messages.chat_id == chat_id)
            .order_by(Messages.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def get_recent(self, chat_id: int, limit: int = 10) -> List[Messages]:
        stmt = (
            select(Messages)
            .where(Messages.chat_id == chat_id)
            .order_by(Messages.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def count_after(self, chat_id: int, after_id: int | None = None) -> int:
        stmt = select(func.count()).where(Messages.chat_id == chat_id)
        if after_id is not None:
            stmt = stmt.where(Messages.id > after_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_messages_after(self, chat_id: int, after_id: int | None = None, limit: int = 10) -> List[Messages]:
        stmt = select(Messages).where(Messages.chat_id == chat_id)
        if after_id is not None:
            stmt = stmt.where(Messages.id > after_id)
        stmt = stmt.order_by(Messages.id.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_messages_paginated(self, chat_id: int, limit: int = 50, offset: int = 0) -> List[Messages]:
        stmt = (
            select(Messages)
            .where(Messages.chat_id == chat_id)
            .options(selectinload(Messages.user))
            .order_by(Messages.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows