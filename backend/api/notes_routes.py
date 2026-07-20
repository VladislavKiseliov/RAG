import uuid

from fastapi import APIRouter
from starlette import status

from backend.dependencies import CurrentUserDep, NoteServiceDep
from backend.schemas.schemas import NoteCreateRequest, NoteUpdateRequest, NoteIndexCompleteRequest

router = APIRouter(prefix="/api/notes", tags=["notes"])

# Колбэк от rag_service по завершении Celery-индексации — без CurrentUserDep, доверенный
# внутренний вызов из docker-сети (тот же паттерн, что у MinIO-вебхука в rag_service).
internal_router = APIRouter(prefix="/internal/notes", tags=["notes-internal"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_note(
        payload: NoteCreateRequest,
        current_user: CurrentUserDep,
        service: NoteServiceDep,
):
    note = await service.create_note(user_id=current_user.id, **payload.model_dump())
    return note


@router.get("")
async def list_notes(
        current_user: CurrentUserDep,
        service: NoteServiceDep,
):
    notes = await service.list_notes(user_id=current_user.id)
    return {"notes": notes}


@router.get("/{note_guid}")
async def get_note(
        note_guid: uuid.UUID,
        current_user: CurrentUserDep,
        service: NoteServiceDep,
):
    return await service.get_note(note_guid=note_guid, user_id=current_user.id)


@router.patch("/{note_guid}")
async def update_note(
        note_guid: uuid.UUID,
        payload: NoteUpdateRequest,
        current_user: CurrentUserDep,
        service: NoteServiceDep,
):
    data = payload.model_dump(exclude_unset=True)
    return await service.update_note(note_guid=note_guid, user_id=current_user.id, data=data)


@router.delete("/{note_guid}")
async def delete_note(
        note_guid: uuid.UUID,
        current_user: CurrentUserDep,
        service: NoteServiceDep,
):
    await service.delete_note(note_guid=note_guid, user_id=current_user.id)
    return {"status": "deleted", "note_guid": str(note_guid)}


@router.post("/{note_guid}/index")
async def index_note(
        note_guid: uuid.UUID,
        current_user: CurrentUserDep,
        service: NoteServiceDep,
):
    return await service.trigger_index(note_guid=note_guid, user_id=current_user.id)


@internal_router.post("/{note_guid}/index-complete", status_code=status.HTTP_204_NO_CONTENT)
async def index_complete(
        note_guid: uuid.UUID,
        payload: NoteIndexCompleteRequest,
        service: NoteServiceDep,
):
    await service.mark_index_complete(note_guid=note_guid, note_status=payload.status, chunk_count=payload.chunk_count)