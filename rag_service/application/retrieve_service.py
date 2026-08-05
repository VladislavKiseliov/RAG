from __future__ import annotations

import asyncio
import csv
import io
import re
import uuid
from typing import Any

from rag_service.api.schemas import RetrieveResponse, RetrieveItem
from rag_service.application.abbreviation_expander import AbbreviationExpander
from rag_service.application.document_service import DocumentQueryService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import  VectorStorageProvider
from rag_service.models import ParentChunks

# Тот же маркер, что _LinkingTableSerializer вставляет в markdown при извлечении таблицы
# (см. docling_conversion_repository.py) и что читалка (rag_routes.py) разрешает для UI —
# здесь разрешаем его же для retrieval-пути, которым пользуется llm_service.
_TABLE_LINK_RE = re.compile(r"\[→\s*Таблица\s+(\d+)\]\([^)]*\)")


def _csv_bytes_to_markdown_table(csv_bytes: bytes) -> str:
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    if not rows:
        return ""
    header, *data = rows
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in data]
    return "\n".join(lines)


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
            v_indexing_service: VectorIndexingService,
            s3_storage: BucketStorageProvider,
            abbreviation_expander: AbbreviationExpander,
    ) -> None:
        """
        Initialize the retrieval service.

        Args:
            vector_storage: Provider for vector database operations (Qdrant, etc.).
            database: Service for querying relational data (Postgres).
            v_indexing_service: Service for text-to-vector transformation.
            s3_storage: Provider for reading table CSVs referenced by [→ Таблица N] markers.
            abbreviation_expander: Conditionally expands queries containing known
                document abbreviations (A11 MVP, see ISSUES.md).
        """
        self.vector_storage = vector_storage
        self._document_service = database
        self.v_indexing_service = v_indexing_service
        self._s3_storage = s3_storage
        self._abbreviation_expander = abbreviation_expander

    async def _resolve_tables_in_items(self, items: list[dict]) -> list[dict]:
        """Заменяет маркеры [→ Таблица N] в parent_chunk на настоящую Markdown-таблицу.

        Без этого LLM видит нерасшифрованную ссылку вместо содержимого таблицы. Собирает
        все нужные (doc_id, table_index) со всех items разом — один поход в БД/S3 на батч,
        а не по одному на item.
        """
        needed: dict[str, set[int]] = {}
        for item in items:
            doc_id = item["metadata"].get("doc_id")
            indices = {int(m) for m in _TABLE_LINK_RE.findall(item["parent_chunk"])}
            if doc_id and indices:
                needed.setdefault(doc_id, set()).update(indices)

        if not needed:
            return items

        markdown_by_key: dict[tuple[str, int], str] = {}
        for doc_id_str, indices in needed.items():
            tables = await self._document_service.get_tables_by_doc_id(uuid.UUID(doc_id_str))
            matched = [t for t in tables if t.table_index in indices]
            if not matched:
                continue
            csv_blobs = await asyncio.gather(
                *(self._s3_storage.get_file(t.s3_csv_path) for t in matched)
            )
            for t, csv_bytes in zip(matched, csv_blobs):
                markdown_by_key[(doc_id_str, t.table_index)] = _csv_bytes_to_markdown_table(csv_bytes)

        for item in items:
            doc_id = item["metadata"].get("doc_id")

            def _replace(match: re.Match, _doc_id: str = doc_id) -> str:
                table_markdown = markdown_by_key.get((_doc_id, int(match.group(1))))
                return table_markdown if table_markdown is not None else match.group(0)

            item["parent_chunk"] = _TABLE_LINK_RE.sub(_replace, item["parent_chunk"])

        return items

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
            query_vector=query_vector,
            query_text= clean_query,
            top_k=max(1, top_k),
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
        requested_parent_ids = [uuid.UUID(key) for key in group_hits.keys()]

        # 5. Загружаем полные данные родителей
        parent_chunks = await self._document_service.get_parent_chunks(
            requested_parent_ids,
            doc_id=doc_id,
        )
        result = build_retrieved_items(
            group_hits=group_hits,
            parent_chunks=parent_chunks,
        )
        result["items"] = await self._resolve_tables_in_items(result["items"])
        return result

    async def batch_search(
            self,
            *,
            queries: list[str],
            top_k: int = 5,
    ) -> dict:
        """Execute a multi-query retrieval pipeline using a single Qdrant batch request.

        Embeds all queries in one models call, sends a single batch request to
        Qdrant, then deduplicates results by parent_id (globally unique primary
        key of parent_chunks, not scoped per document) keeping the highest-scoring
        child hit per parent block.

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
            query_texts=queries,
            top_k=top_k,
        )

        # Flatten + дедупликация по parent_id (глобально уникальный PK, не составной), оставляем лучший score
        seen: dict[str, dict] = {}
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

        requested_parent_ids = [uuid.UUID(key) for key in seen.keys()]
        parent_chunks = await self._document_service.get_parent_chunks(requested_parent_ids)

        result = build_retrieved_items(group_hits=seen, parent_chunks=parent_chunks)
        result["items"] = await self._resolve_tables_in_items(result["items"])
        return result

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
        # AbbreviationExpander.expand - синхронная pymorphy3-лемматизация (чистый
        # Python, не C-расширение), считается для каждого слова запроса безусловно
        # (см. _build_canonical). Без to_thread этот CPU-bound вызов держит event
        # loop процесса на всё время разбора - под конкурентной нагрузкой стопорит
        # остальные retrieve/health-check запросы того же процесса.
        queries = await asyncio.to_thread(self._abbreviation_expander.expand, queries)

        if len(queries) == 1:
            return await self.search(query=queries[0], top_k=top_k)

        return await self.batch_search(queries=queries, top_k=top_k)


# --- Helpers for data transformation ---

def group_hits_by_parent(
        hits: list[Any],
) -> dict[str, dict[str, Any]]:
    """
    Groups vector search hits by their parent chunk identity.

    This ensures that if multiple 'child' snippets belong to the same
    paragraph/page, they are combined into a single context item.
    """
    grouped: dict[str, dict[str, Any]] = {}

    for hit in hits:
        # Учитываем, что hit может быть объектом (ScoredPoint) или словарем
        payload = getattr(hit, "payload", hit.get("payload") if isinstance(hit, dict) else {}) or {}
        score = float(getattr(hit, "score", hit.get("score") if isinstance(hit, dict) else 0.0))

        doc_id = str(payload.get("doc_id") or "").strip()
        parent_id = str(payload.get("parent_id") or "").strip()

        if not doc_id or not parent_id:
            continue

        key = parent_id

        if key not in grouped:
            grouped[key] = {
                "metadata":
                    {
                    "doc_id": doc_id,
                    "parent_id": parent_id,
                    "page_num": payload.get("page_num"),
                    "score": score,
                    "headers": payload.get("headers") or {},
                    "source": payload.get("source") or "",
                    },
                "children": [],
            }

        child_text = payload.get("text") or payload.get("child_text") or ""

        grouped[key]["children"].append(
            {
                "score": score,
                "text": child_text,
            }
        )
        if score > grouped[key]["metadata"]["score"]:
            grouped[key]["metadata"]["score"] = score

    return grouped


def build_retrieved_items(
        *,
        group_hits: dict[str, dict[str, Any]],
        parent_chunks:  list[ParentChunks],
) -> RetrieveResponse:
    """
    Merges grouped vector hits with full text content from the database.
    """
    # Создаем мапу для быстрого поиска строк из БД
    parent_key = {str(parent.id): parent for parent in parent_chunks}

    items: list[RetrieveItem] = []
    for key, group in group_hits.items():
        row = parent_key.get(key)
        if row is None:
            continue

        children = group.get("children", [])
        # Сортируем детей внутри группы по релевантности
        children = sorted(
            children,
            key=lambda child: child["score"],
            reverse=True,
        )

        items.append(
            {
                "child_chunks":children,
                "parent_chunk": getattr(row, "content", ""),
                "metadata":group.get("metadata", {}),

            }
        )
    # Итоговая сортировка всех результатов по максимальному скору
    items = sorted(items, key=lambda x: x["metadata"]["score"], reverse=True)

    result = {"items": items, "total": len(items)}

    return result