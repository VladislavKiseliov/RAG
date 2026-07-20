import uuid
from typing import Optional

from sqlalchemy import select, delete

from backend.models.database_models import Notes
from backend.repository.base_repository import BaseRepository


class NoteRepository(BaseRepository):
    """CRUD для личных заметок пользователя."""

    async def create_note(self, user_id: int, **fields) -> Notes:
        note = Notes(user_id=user_id, **fields)
        self._session.add(note)
        await self._session.flush()
        return note

    async def get_note_by_guid(self, note_guid: uuid.UUID) -> Optional[Notes]:
        stmt = select(Notes).where(Notes.guid == note_guid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_note_for_user(self, note_guid: uuid.UUID, user_id: int) -> Optional[Notes]:
        stmt = select(Notes).where(Notes.guid == note_guid, Notes.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_notes_for_user(self, user_id: int) -> list[Notes]:
        stmt = select(Notes).where(Notes.user_id == user_id).order_by(Notes.updated_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_note(self, note_guid: uuid.UUID, user_id: int, data: dict) -> Optional[Notes]:
        note = await self.get_note_for_user(note_guid, user_id)
        if note is None:
            return None
        for field, value in data.items():
            setattr(note, field, value)
        return note

    async def update_note_by_guid(self, note_guid: uuid.UUID, data: dict) -> Optional[Notes]:
        """Без проверки владельца — используется только внутренним колбэком index-complete от rag_service."""
        note = await self.get_note_by_guid(note_guid)
        if note is None:
            return None
        for field, value in data.items():
            setattr(note, field, value)
        return note

    async def delete_note(self, note_guid: uuid.UUID, user_id: int) -> bool:
        stmt = delete(Notes).where(Notes.guid == note_guid, Notes.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0