import uuid

from sqlalchemy import select

from backend.models.database_models import Messages, ReadStatus
from backend.repository.base_repository import BaseRepository


class MessengerRepository(BaseRepository):

    async def get_message_by_guid(self, message_guid: uuid.UUID) -> Messages | None:
        stmt = select(Messages).where(Messages.guid == message_guid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_read_status(self, user_id: int, chat_id: int, message_id: int) -> ReadStatus:
        stmt = select(ReadStatus).where(
            ReadStatus.user_id == user_id,
            ReadStatus.chat_id == chat_id,
        )
        result = await self._session.execute(stmt)
        read_status = result.scalar_one_or_none()

        if read_status is None:
            read_status = ReadStatus(user_id=user_id, chat_id=chat_id, last_read_message_id=message_id)
            self._session.add(read_status)
        else:
            read_status.last_read_message_id = message_id

        await self._session.flush()
        return read_status