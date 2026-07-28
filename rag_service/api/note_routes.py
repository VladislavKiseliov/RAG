from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from rag_service.api.schemas import NoteIndexRequest
from rag_service.celery_app import celery_app
from rag_service.dependencies import NotesVectorStorageDep

router = APIRouter(prefix="/notes", tags=["Notes Vectorization"])


@router.post("/{note_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def index_note(note_id: uuid.UUID, payload: NoteIndexRequest):
    """Queue note text for chunking + embedding + upsert into the notes Qdrant collection."""
    # По имени задачи, не прямым импортом `rag_service.workers.task` - см. комментарий
    # в TaskDispatcherService.dispatch_ingestion.
    celery_app.send_task("index_note", args=[str(note_id), payload.user_id, payload.text])
    return {"status": "queued"}


@router.delete("/{note_id}/vectors", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note_vectors(note_id: uuid.UUID, vector_storage: NotesVectorStorageDep):
    """Remove all vector points for a note (called on note delete)."""
    await vector_storage.delete_by_field("note_id", str(note_id))