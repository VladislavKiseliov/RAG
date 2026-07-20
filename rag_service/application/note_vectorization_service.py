from __future__ import annotations

import uuid

from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.domain.chunking.chunk_builder import ChildChunkBuilder
from rag_service.domain.models.vector_point import VectorPoint
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider


class NoteVectorizationService:
    """Векторизация заметок: чанкинг + эмбеддинг + upsert в отдельную Qdrant-коллекцию.

    В отличие от IngestionService — не парсит документы (Docling) и не трогает S3/Postgres:
    заметка приходит уже готовым текстом, саму таблицу заметок хранит backend.
    """

    def __init__(
        self,
        vector_storage: VectorStorageProvider,
        vector_indexing_service: VectorIndexingService,
    ):
        self._vector_storage = vector_storage
        self._v_indexing = vector_indexing_service
        self._chunk_builder = ChildChunkBuilder()

    async def index_note(self, note_id: uuid.UUID, user_id: str, text: str) -> int:
        """Чанкует и векторизует текст заметки, заменяя её прежние точки.

        Returns:
            Число проиндексированных чанков.
        """
        # Ре-индексация должна быть идемпотентной — сносим старые точки заметки перед
        # вставкой новых, иначе повторное сохранение накапливает дубликаты в Qdrant.
        await self._vector_storage.delete_by_field("note_id", str(note_id))

        chunks = self._chunk_builder.build(text)
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        dense_vectors, sparse_vectors = await self._v_indexing.get_hybrid_vectors(texts)

        points = [
            VectorPoint(
                id=str(uuid.uuid4()),
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                text=chunk_text,
                payload={
                    "note_id": str(note_id),
                    "user_id": str(user_id),
                    "text": chunk_text,
                    "chunk_index": index,
                },
            )
            for index, (chunk_text, dense_vector, sparse_vector) in enumerate(
                zip(texts, dense_vectors, sparse_vectors, strict=True)
            )
        ]

        await self._vector_storage.upsert_vectors(points)
        return len(points)

    async def delete_note_vectors(self, note_id: uuid.UUID) -> None:
        await self._vector_storage.delete_by_field("note_id", str(note_id))