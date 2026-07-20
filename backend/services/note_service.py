import uuid
from typing import List, Optional

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.schemas.schemas import NoteBaseSchema
from backend.services.unit_of_work import UnitOfWork
from backend.settings import settings
from backend.utils.exceptions import NoteNotFoundError


class NoteService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def create_note(self, user_id: int, **fields) -> NoteBaseSchema:
        async with UnitOfWork(self._sf) as uow:
            note = await uow.notes.create_note(user_id=user_id, **fields)
            await uow.commit()
        return NoteBaseSchema.model_validate(note)

    async def list_notes(self, user_id: int) -> List[NoteBaseSchema]:
        async with UnitOfWork(self._sf) as uow:
            notes = await uow.notes.list_notes_for_user(user_id)
            return [NoteBaseSchema.model_validate(n) for n in notes]

    async def get_note(self, note_guid: uuid.UUID, user_id: int) -> NoteBaseSchema:
        async with UnitOfWork(self._sf) as uow:
            note = await uow.notes.get_note_for_user(note_guid, user_id)
        if note is None:
            raise NoteNotFoundError()
        return NoteBaseSchema.model_validate(note)

    async def update_note(self, note_guid: uuid.UUID, user_id: int, data: dict) -> NoteBaseSchema:
        async with UnitOfWork(self._sf) as uow:
            note = await uow.notes.update_note(note_guid, user_id, data)
            if note is None:
                raise NoteNotFoundError()
            await uow.commit()
        return NoteBaseSchema.model_validate(note)

    async def delete_note(self, note_guid: uuid.UUID, user_id: int) -> bool:
        async with UnitOfWork(self._sf) as uow:
            deleted = await uow.notes.delete_note(note_guid, user_id)
            await uow.commit()
        if not deleted:
            raise NoteNotFoundError()

        # Best-effort: заметки полностью переиндексируются при каждом сохранении, точки без
        # владельца в чужой поиск не попадают (payload фильтруется по note_id) — не блокируем
        # удаление заметки сетевой ошибкой rag_service.
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                await client.delete(f"{settings.RAG_SERVICE_URL}/notes/{note_guid}/vectors")
        except httpx.HTTPError:
            pass
        return True

    async def trigger_index(self, note_guid: uuid.UUID, user_id: int) -> NoteBaseSchema:
        """Ставит статус indexing и просит rag_service векторизовать заметку через Celery."""
        async with UnitOfWork(self._sf) as uow:
            note = await uow.notes.update_note(note_guid, user_id, {"status": "indexing"})
            if note is None:
                raise NoteNotFoundError()
            content = note.content
            await uow.commit()

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                response = await client.post(
                    f"{settings.RAG_SERVICE_URL}/notes/{note_guid}/index",
                    json={"user_id": str(user_id), "text": content},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            async with UnitOfWork(self._sf) as uow:
                await uow.notes.update_note(note_guid, user_id, {"status": "error"})
                await uow.commit()
            raise

        return NoteBaseSchema.model_validate(note)

    async def mark_index_complete(self, note_guid: uuid.UUID, note_status: str, chunk_count: Optional[int]) -> None:
        """Колбэк от rag_service по завершении индексации.

        Без проверки владельца — вызов идёт от доверенного внутреннего сервиса, а не от
        аутентифицированного пользователя (см. POST /internal/notes/{id}/index-complete).
        """
        data: dict = {"status": note_status}
        if chunk_count is not None:
            data["chunk_count"] = chunk_count
        async with UnitOfWork(self._sf) as uow:
            await uow.notes.update_note_by_guid(note_guid, data)
            await uow.commit()