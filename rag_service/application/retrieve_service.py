from __future__ import annotations

import uuid
from typing import Any

from rag_service.application.document_service import DocumentQueryService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.providers.vector_storage_provider import  VectorStorageProvider


class RetrieveService:
    """Application service for retrieval flow over vector search and parent chunks.

    The service orchestrates the retrieval use case:
    1. Validates and normalizes the text query.
    2. Converts text query into a vector representation using VectorIndexingService.
    3. Executes vector search over child chunks via VectorProvider.
    4. Groups matched child chunks by their parent chunk ID.
    5. Loads full parent chunk data (text/metadata) from Postgres.
    6. Builds final retrieval items for API response.
    """

    def __init__(
            self,
            *,
            vector_storage: VectorStorageProvider,
            database: DocumentQueryService,
            v_indexing_service: VectorIndexingService
    ) -> None:
        """
        Initialize the retrieval service.

        Args:
            vector_storage: Provider for vector database operations (Qdrant, etc.).
            database: Service for querying relational data (Postgres).
            v_indexing_service: Service for text-to-vector transformation.
        """
        self.vector_storage = vector_storage
        self._document_service = database
        self.v_indexing_service = v_indexing_service

    async def _get_vector_query(self, query: str) -> list[float]:
        """
        Internal helper to transform string query into a vector.

        Args:
            query: Normalized search string.

        Returns:
            Vector representation (list of floats).
        """
        return await self.v_indexing_service.get_query_embedding(query)

    async def search(
            self,
            *,
            query: str,
            top_k: int = 5,
            doc_id: uuid.UUID | None = None,
            score_threshold: float | None = None,
    ) -> dict:
        """
        Execute the full retrieval pipeline: Text -> Vector -> Search -> Parent Loading.

        Args:
            query: User search query in natural language.
            top_k: Number of child chunks to retrieve from vector storage.
            doc_id: Optional UUID to restrict search to a specific document.
            score_threshold: Minimum similarity score (0.0 to 1.0).

        Returns:
            A dictionary containing the query, total items found, and a list of
            grouped retrieval items with parent text and child metadata.
        """
        clean_query = query.strip()
        if not clean_query:
            return {
                "query": "",
                "items": [],
                "total": 0,
            }

        # 1. Трансформируем текст в вектор
        query_vector = await self._get_vector_query(clean_query)

        # 2. Ищем похожие чанки в векторном хранилище по вектору
        hits = await self.vector_storage.search(
            query_vector=query_vector,  # Передаем вектор, а не текст
            top_k=max(1, top_k),
            doc_id=doc_id,
            score_threshold=score_threshold,
        )

        # 3. Группируем результаты (несколько детей могут принадлежать одному родителю)
        group_hits = group_hits_by_parent(hits=hits)

        if not group_hits:
            return {
                "query": clean_query,
                "items": [],
                "total": 0,
            }

        # 4. Извлекаем ID родительских чанков для загрузки из БД
        requested_parent_ids = [key[1] for key in group_hits.keys()]

        # 5. Загружаем полные данные родителей (текст запроса, заголовки и т.д.)
        parent_chunks = await self._document_service.get_parent_chunks(
            requested_parent_ids,
            doc_id=doc_id,
        )

        # 6. Формируем финальный объект ответа
        items = build_retrieved_items(
            group_hits=group_hits,
            rows=parent_chunks,
        )

        return {
            "query": clean_query,
            "items": items,
            "total": len(items),
        }

    async def batch_search(
            self,
            *,
            queries: list[str],
            top_k: int = 5,
    ) -> dict:
        """Execute a multi-query retrieval pipeline using a single Qdrant batch request.

        Embeds all queries in one model call, sends a single batch request to
        Qdrant, then deduplicates results by (doc_id, parent_id) keeping the
        highest-scoring child hit per parent block.

        Each result item contains a child chunk (focused hit) and its parent
        chunk text (context window) loaded from Postgres.

        Args:
            queries: List of natural language search queries.
            top_k: Number of child hits to request per query from Qdrant.

        Returns:
            Dict with 'items' (deduplicated focus-parent blocks) and 'total'.
        """
        # Все эмбеддинги за один вызов модели
        query_vectors = await self.v_indexing_service.get_embeddings(queries)

        # Один батч-запрос к Qdrant вместо N последовательных
        batch_hits = await self.vector_storage.batch_search(
            query_vectors=query_vectors,
            top_k=top_k,
        )

        # Flatten + дедупликация по (doc_id, parent_id), оставляем лучший score
        seen: dict[tuple[str, str], dict] = {}
        for hits in batch_hits:
            group_hits = group_hits_by_parent(hits)
            for key, group in group_hits.items():
                existing = seen.get(key)
                children = group.get("children", [])
                top_score = max((c["score"] for c in children), default=0.0)
                if existing is None or top_score > max(
                    (c["score"] for c in existing.get("children", [])), default=0.0
                ):
                    seen[key] = group

        if not seen:
            return {"items": [], "total": 0}

        requested_parent_ids = [key[1] for key in seen.keys()]
        parent_chunks = await self._document_service.get_parent_chunks(requested_parent_ids)

        items = build_retrieved_items(group_hits=seen, rows=parent_chunks)
        return {"items": items, "total": len(items)}

    async def retrieve(
            self,
            *,
            queries: list[str],
            top_k: int = 5,
    ) -> dict:
        """Entry point for all retrieval requests.

        Routes to `search` for a single query (avoids batch overhead) or
        to `batch_search` for multiple expanded queries.

        Args:
            queries: One or more search queries.
            top_k: Number of hits to retrieve per query.

        Returns:
            Dict with 'items' and 'total'.
        """
        if len(queries) == 1:
            return await self.search(query=queries[0], top_k=top_k)
        return await self.batch_search(queries=queries, top_k=top_k)


# --- Helpers for data transformation ---

def group_hits_by_parent(
        hits: list[Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Groups vector search hits by their parent chunk identity.

    This ensures that if multiple 'child' snippets belong to the same
    paragraph/page, they are combined into a single context item.
    """
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for hit in hits:
        # Учитываем, что hit может быть объектом (ScoredPoint) или словарем
        payload = getattr(hit, "payload", hit.get("payload") if isinstance(hit, dict) else {}) or {}
        score = getattr(hit, "score", hit.get("score") if isinstance(hit, dict) else 0.0)

        doc_id = str(payload.get("doc_id") or "").strip()
        parent_id = str(payload.get("parent_id") or "").strip()

        if not doc_id or not parent_id:
            continue

        key = (doc_id, parent_id)

        if key not in grouped:
            grouped[key] = {
                "doc_id": doc_id,
                "parent_id": parent_id,
                "page_num": payload.get("page_num"),
                "headers": payload.get("headers") or {},
                "children": [],
            }

        grouped[key]["children"].append(
            {
                "score": float(score or 0.0),
                "payload": payload,
            }
        )

    return grouped


def build_retrieved_items(
        *,
        group_hits: dict[tuple[str, str], dict[str, Any]],
        rows: list[Any],
) -> list[dict[str, Any]]:
    """
    Merges grouped vector hits with full text content from the database.
    """
    # Создаем мапу для быстрого поиска строк из БД
    row_by_key = {(str(row.doc_id), str(row.id)): row for row in rows}

    items: list[dict[str, Any]] = []

    for key, group in group_hits.items():
        row = row_by_key.get(key)
        if row is None:
            continue

        children = group.get("children", [])
        # Сортируем детей внутри группы по релевантности
        children = sorted(
            children,
            key=lambda child: child["score"],
            reverse=True,
        )

        top_score = children[0]["score"] if children else 0.0
        payload = children[0]["payload"] if children else {}

        items.append(
            {
                "doc_id": str(row.doc_id),
                "parent_id": str(row.id),
                "page_num": str(payload.get("page_num") or getattr(row, "page_num", "N/A")),
                "headers": payload.get("headers") or getattr(row, "headers", {}),
                "text": getattr(row, "content", ""),  # Предполагаем, что в БД колонка content
                "score": round(float(top_score), 6),
                "children": children,
            }
        )

    # Итоговая сортировка всех результатов по максимальному скору
    return sorted(items, key=lambda x: x["score"], reverse=True)