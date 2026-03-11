"""Retriever service for query embedding, vector search, context assembly, and LLM answer."""

from __future__ import annotations

import os
import uuid
from typing import Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.providers.LLM_provider import GeminiLLMProvider
from rag_service.providers.vector_provider import VectorProvider
from rag_service.repositories.document_repository import DocumentRepository


class SearchService:
    """Orchestrates retrieval pipeline and produces answer + sources response."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        vector_provider: VectorProvider,
        llm_provider: GeminiLLMProvider,
        max_context_chars: int = 12000,
    ) -> None:
        self._session_factory = session_factory
        self._vector_provider = vector_provider
        self._llm_provider = llm_provider
        self._max_context_chars = max(500, max_context_chars)

    def _deduplication_chunks(
            self,
            hits: list[dict],
            doc_id: uuid.UUID | None = None,
    ) -> tuple[dict[tuple[str, str], dict], list[tuple[str, str]]] | None:
        """Дедуплицирует child чанки по parent_id, оставляя лучший score.

        Qdrant может вернуть несколько child чанков одного parent.
        Метод оставляет только один — с наивысшим score, сохраняя
        порядок по релевантности.

        Args:
            hits: Список результатов из Qdrant. Каждый hit содержит
                  поля `payload` (dict) и `score` (float).
            doc_id: Опциональный ID документа для фильтрации.
                    Используется как fallback если doc_id отсутствует в payload.

        Returns:
            Кортеж (best_by_key, ordered_keys):
                - best_by_key: словарь (doc_id, parent_id) → лучший hit
                - ordered_keys: ключи в порядке убывания релевантности
            None если релевантных фрагментов не найдено.
        """
        best_by_key: dict[tuple[str, str], dict] = {}
        ordered_keys: list[tuple[str, str]] = []

        for hit in hits:
            payload: dict = hit.get("payload") or {}

            parent_id = str(payload.get("parent_id") or "").strip()
            if not parent_id:
                continue

            # Берём doc_id из payload, fallback на переданный doc_id
            payload_doc_id = str(
                payload.get("doc_id") or (str(doc_id) if doc_id else "")
            ).strip()

            key: tuple[str, str] = (payload_doc_id, parent_id)
            score: float = float(hit.get("score") or 0.0)

            if key not in best_by_key:
                # Первый раз видим этот parent — добавляем и запоминаем порядок
                ordered_keys.append(key)
                best_by_key[key] = {"score": score, "payload": payload}
            elif score > best_by_key[key]["score"]:
                # Уже видели этот parent — обновляем если score лучше
                best_by_key[key] = {"score": score, "payload": payload}

        if not best_by_key:
            return None

        return best_by_key, ordered_keys

    async def _fetch_parents(
            self,
            best_by_key: dict[tuple[str, str], dict],
            ordered_keys: list[tuple[str, str]],
            doc_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Достаёт полные тексты parent чанков из Postgres.

        Args:
            best_by_key: Дедуплицированные hits (doc_id, parent_id) → hit.
            ordered_keys: Ключи в порядке релевантности.
            doc_id: Опциональный фильтр по документу.

        Returns:
            Список sources в порядке релевантности с полным текстом из Postgres.
        """
        # Берём parent_id в порядке релевантности
        requested_parent_ids: list[str] = [key[1] for key in ordered_keys]

        # Идём в Postgres за полными текстами
        async with self._session_factory() as session:
            repo = DocumentRepository(session)
            rows = await repo.get_parents_by_ids(requested_parent_ids, doc_id=doc_id)

        # Индексируем строки для быстрого поиска
        row_by_key = {(str(row.doc_id), str(row.id)): row for row in rows}

        # Собираем sources в порядке релевантности
        sources: list[dict] = []
        for key in ordered_keys:
            item = best_by_key[key]
            row = row_by_key.get(key)

            # Fallback если doc_id не совпал точно
            if row is None and doc_id is not None:
                row = row_by_key.get((str(doc_id), key[1]))
            if row is None:
                continue

            payload = item["payload"]
            print(f"{row=}")
            sources.append({
                "parent_id": str(row.id),
                "page_num": str(payload.get("page_num") or row.page_num or "N/A"),
                "headers": payload.get("headers") or row.headers or {},
                "text": row.content,  # ← полный текст из Postgres
                "score": round(float(item["score"]), 6),
            })

        return sources

    def _build_context(self, sources: list[dict]) -> str:
        """Собирает строку контекста из sources с лимитом по символам."""
        parts: list[str] = []
        current_size = 0

        for src in sources:
            part = (
                f"[parent_id={src['parent_id']}; page={src['page_num']}; score={src['score']}]\n"
                f"{src['text']}"
            )
            if current_size + len(part) > self._max_context_chars:
                break
            parts.append(part)
            current_size += len(part)

        return "\n\n".join(parts)

    async def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> dict:
        """Run full search pipeline and return answer with source chunks."""
        clean_query = query.strip()
        if not clean_query:
            return {"answer": "Пустой запрос.", "sources": []}

        hits = await self._vector_provider.search(
            clean_query,
            top_k=max(1, top_k),
            doc_id=doc_id,
            score_threshold=score_threshold,
        )

        # дедупликация возвращает кортеж или None
        dedup_result = self._deduplication_chunks(hits, doc_id)
        if dedup_result is None:
            return {"answer": "Релевантные фрагменты не найдены.", "sources": []}

        best_by_key, ordered_keys = dedup_result  # ← вот здесь распаковка

        sources = await self._fetch_parents(best_by_key, ordered_keys, doc_id)

        context = self._build_context(sources)
        answer = await self._llm_provider.generate(query=query, context=context)
        # return {"query": query, "context": context}
        return {"answer": answer, "sources": sources}
