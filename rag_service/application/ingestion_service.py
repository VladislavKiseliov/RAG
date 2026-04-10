from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from dataclasses import dataclass

from rag_service.application.chunking_pipeline import DocumentChunkingPipeline
from rag_service.application.document_service import DocumentService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.providers.vector_provider import VectorProvider
from rag_service.models import DocumentStatus


@dataclass(frozen=True)
class IngestionResult:
    doc_id: uuid.UUID
    status: DocumentStatus


class IngestionService:
    """Orchestrates document ingestion and child chunk upload into vector DB."""

    def __init__(
        self,
        document_service: DocumentService,
        vector_provider: VectorProvider,
        vector_indexing_service: VectorIndexingService,
        *,
        vector_timeout_seconds: float = 60.0,
        minio_provider,
    ) -> None:
        self._document_service = document_service
        self._vector_provider = vector_provider
        self._vector_indexing_service = vector_indexing_service
        self._vector_timeout_seconds = vector_timeout_seconds
        self._chunker = DocumentChunkingPipeline()
        self.minio_provider = minio_provider

    @property
    def vector_provider(self) -> VectorProvider:
        return self._vector_provider

    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    async def ingest_path(
        self,
        file_path: str,
        *,
        doc_id: uuid.UUID | None = None,
        meta: dict | None = None,
    ) -> IngestionResult:
        """Entry point for worker: ingest a file from disk."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            content = f.read()

        if not content:
            raise ValueError("Empty file")

        file_hash = self.calculate_file_hash(content)

        return await self._run_pipeline(
            file_path=file_path,
            filename=filename,
            file_hash=file_hash,
            doc_id=doc_id,
            meta=meta,
        )

    async def _run_pipeline(
        self,
        *,
        file_path: str,
        filename: str,
        file_hash: str,
        doc_id: uuid.UUID | None,
        meta: dict | None,
    ) -> IngestionResult:
        """Run full ingestion pipeline without holding one long DB transaction."""
        created_id: uuid.UUID | None = None

        try:
            created_id = await self._document_service.create_doc(
                filename=filename,
                file_hash=file_hash,
                meta=meta,
                doc_id=doc_id,
            )

            parents, children = self._chunker.process(file_path)

            if not parents:
                raise ValueError("No parent chunks produced")
            if not children:
                raise ValueError("No child chunks produced")

            await self._document_service.add_parent_chunks(created_id, parents)

            points = [
                {
                    "id": child.get("id") or str(uuid.uuid4()),
                    "text": child["text"],
                    "payload": {
                        "parent_id": child["parent_id"],
                        "headers": child.get("headers") or {},
                        "source": child.get("source", ""),
                        "doc_id": str(created_id),
                    },
                }
                for child in children
            ]

            await asyncio.wait_for(
                self._vector_indexing_service.upsert_points(points),
                timeout=self._vector_timeout_seconds,
            )

            await self._document_service.set_status(
                created_id,
                DocumentStatus.completed,
                chunk_count=len(points),
            )

            return IngestionResult(created_id, DocumentStatus.completed)

        except Exception:
            if created_id is not None:
                await self._mark_error(created_id)
            raise

    async def _mark_error(self, doc_id: uuid.UUID) -> None:
        """Best-effort error status update after pipeline failure."""
        try:
            await self._document_service.set_status(doc_id, DocumentStatus.error)
        except Exception:
            pass
