"""Чистые функции форматирования/трансформации данных - без состояния, без I/O."""

from __future__ import annotations

from typing import Any

from llm_service.application.lean_rag_models import RetrieveItem


_ROLE_LABELS = {"user": "Пользователь", "assistant": "Ассистент"}


def format_chat_history(messages: list[dict[str, str]]) -> str:
    """Нумерованные реплики с явной границей (двойной перенос) и меткой у последней.

    Живой баг: старое форматирование ("role: content", одинарный \\n между репликами,
    без нумерации) визуально сливало соседние реплики, если ответ ассистента сам
    многострочный (списки/таблицы - обычное дело для RAG-ответов) - модель иногда
    путала, к какой реплике относится текущий вопрос (пример: "ты откуда это взял?"
    после многострочного ответа получило ответ про сообщение двумя ходами раньше).
    Явная метка "последняя реплика" - тот же "attention anchor", что и нумерация
    сообщений/таймстампы в промпт-инжиниринге для длинного контекста.
    """
    if not messages:
        return ""
    last_index = len(messages) - 1
    lines = []
    for i, m in enumerate(messages):
        role = _ROLE_LABELS.get(m.get("role", "user"), m.get("role", "user"))
        marker = " (последняя реплика перед текущим вопросом)" if i == last_index else ""
        lines.append(f"[{i + 1}]{marker} {role}: {m.get('content', '')}")
    return "\n\n".join(lines)


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


def merge_appendix_result(subtask_results: list[dict[str, Any]]) -> str | None:
    """Достаёт текст приложения из get_appendix-подзадачи, если она была и что-то нашла.

    В отличие от merge_search_docs_results - не список (нет score, нечего ранжировать),
    первый непустой результат и есть ответ. Несколько get_appendix-подзадач в одном
    plan - маловероятный, но не запрещённый случай; берём первую удачную."""
    for entry in subtask_results:
        if entry["tool"] != "get_appendix":
            continue
        text = entry["result"].get("text")
        if text:
            return text
    return None
