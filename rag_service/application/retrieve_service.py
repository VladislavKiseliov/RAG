from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.application.document_service import DocumentQueryService
from rag_service.domain.retrieval import build_retrieved_items, group_hits_by_parent
from rag_service.infrastructures.providers.vector_storage_provider import VectorProvider


class RetrieveService:
    """Application service for retrieval flow over vector search and parent chunks.

    The service orchestrates the retrieval use case:
    1. validates and normalizes the query,
    2. executes vector search over child chunks,
    3. groups matched child chunks by parent chunk,
    4. loads parent chunks from Postgres,
    5. builds final retrieval items for API response.

    This service does not generate LLM answers.
    It returns only retrieval context and metadata.
    """

    def __init__(
        self,
        *,
        vector_storage: VectorProvider,
        database: DocumentQueryService,
    ) -> None:
        """Create retrieval service with required infrastructure dependencies.

        Args:
            session_factory: SQLAlchemy async session factory.
                Currently passed as an infrastructure dependency for DB-related flows.
            vector_provider: Vector search provider used to search child chunks.
            database: Read-only document query service used to load parent chunks.
        """
        self.vector_storage = vector_storage
        self._document_service = database

    async def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> dict:
        """Execute retrieval pipeline and return grouped parent-based context.

        The method trims the incoming query, performs vector search over child chunks,
        groups hits by parent chunk, loads corresponding parent chunks from Postgres,
        and builds a response ready for the API layer.

        Args:
            query: User search query.
            top_k: Maximum number of vector hits to request from the vector provider.
            doc_id: Optional document filter. When provided, retrieval is limited
                to a single document.
            score_threshold: Optional minimum similarity score for vector search.

        Returns:
            A dictionary with the following structure:
                {
                    "query": "<normalized query>",
                    "items": [...],
                    "total": <number of returned items>,
                }

            If the query is empty after trimming, or if nothing relevant is found,
            the method returns an empty result:
                {
                    "query": "",
                    "items": [],
                    "total": 0,
                }
                or
                {
                    "query": "<normalized query>",
                    "items": [],
                    "total": 0,
                }
        """
        clean_query = query.strip()
        if not clean_query:
            return {
                "query": "",
                "items": [],
                "total": 0,
            }

        hits = await self.vector_storage.search(
            clean_query,
            top_k=max(1, top_k),
            doc_id=doc_id,
            score_threshold=score_threshold,
        )

        group_hits = group_hits_by_parent(hits=hits)

        if not group_hits:
            return {
                "query": clean_query,
                "items": [],
                "total": 0,
            }

        requested_parent_ids = [key[1] for key in group_hits.keys()]

        parent_chunks = await self._document_service.get_parent_chunks(
            requested_parent_ids,
            doc_id=doc_id,
        )

        items = build_retrieved_items(
            group_hits=group_hits,
            rows=parent_chunks,
        )

        return {
            "query": clean_query,
            "items": items,
            "total": len(items),
        }
