"""Чистые функции форматирования/трансформации данных - без состояния, без I/O."""

from __future__ import annotations

from typing import Any

from llm_service.application.lean_rag_models import RetrieveItem


def format_retrieval_item_for_prompt(item: RetrieveItem) -> str:
    """[Документ: <filename> | Раздел <title>]\n<текст родительского чанка>.

    Раньше сюда шёл сырой Python-repr headers (`f"Раздел {item.metadata.headers}:..."`,
    то есть буквально "Раздел {'chapter_number': '2', 'title': '...'}" в промпте) и список
    child-чанков со скорами через запятую — не нужен LLM, только раздувал контекст.
    `title` уже содержит номер раздела впереди (напр. "2 Нормативные ссылки"), отдельно
    chapter_number не дублируем — та же логика, что в Message.jsx::formatName на фронте.
    """
    title = (item.metadata.headers or {}).get("title") or "без названия"
    doc_name = item.metadata.source or item.metadata.doc_id
    return f"[Документ: {doc_name} | Раздел {title}]\n{item.parent_chunk}"


def build_sources_payload(retrieval_data: list[RetrieveItem]) -> list[dict[str, Any]]:
    """Общий маппинг RetrieveItem -> плоский dict источника для API-ответа.

    Используется и обычным /llm/answer (agent_routers.py), и SSE-веткой
    (событие 'sources' в run_stream) - раньше эта логика была продублирована
    прямо в agent_routers.py.
    """
    return [
        {
            "doc_id": item.metadata.doc_id,
            "parent_id": item.metadata.parent_id,
            "page_num": item.metadata.page_num,
            "score": item.metadata.score,
            "text": item.parent_chunk,
            "child_chunks": [c.text for c in item.child_chunks],
            "headers": item.metadata.headers,
            "source": item.metadata.source,
        }
        for item in retrieval_data
    ]


def merge_search_docs_results(subtask_results: list[dict[str, Any]]) -> list[RetrieveItem]:
    """Сливает items из ВСЕХ search_docs-подзадач в один retrieval_data.

    plan_node может выдать несколько search_docs-подзадач с разными формулировками
    (аналог старого multi-query из expand_queries_node), но каждая идёт отдельным
    вызовом retrieval_service.retrieve([query]) - в отличие от старого
    retrieve_multi_node, дедупликация между несколькими вызовами тут не
    происходит на стороне rag_service. Дедуплицируем по parent_id тем же
    принципом, что и RetrieveService.batch_search в rag_service: оставляем
    версию с максимальным score.
    """
    merged: dict[str, RetrieveItem] = {}
    for entry in subtask_results:
        if entry["tool"] != "search_docs":
            continue
        for item_dict in entry["result"].get("items", []):
            item = RetrieveItem.model_validate(item_dict)
            key = item.metadata.parent_id
            existing = merged.get(key)
            if existing is None or item.metadata.score > existing.metadata.score:
                merged[key] = item
    return sorted(merged.values(), key=lambda item: item.metadata.score, reverse=True)
