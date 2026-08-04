"""Чистые гейты графа (LangGraph add_conditional_edges) - живой путь.

Ничего не хранят и не трогают self - каждая функция детерминирована по одному
только state (+ live-конфигу). Гейты disabled-веток (decide_after_router,
decide_after_resolve_docs) - в legacy_disabled_nodes.py рядом с их нодами.
"""

from __future__ import annotations

import re

from llm_service.ai_config import get_live_config
from llm_service.application.lean_rag_models import LeanAgentState

# Маркеры намерения действия для гейта post_actions - код-фильтр перед LLM-вызовом
# (см. ARCHITECTURE.md §3 post_actions). Проверяется по state.query (что попросил
# пользователь), не по сгенерированному ответу.
_ACTION_MARKERS_RE = re.compile(
    r"сохрани|закинь|запиши|создай задачу|добавь заметку|поправь заметку|обнови",
    re.IGNORECASE,
)


async def decide_after_execute_subtasks(state: LeanAgentState) -> str:
    """Реальный код-гейт: если среди подзадач были search_docs — маршрут в rerank
    (чтобы отранжировать document-поиск так же, как domain_rag), иначе прямо в
    build_prompt (search_notes/search_tasks ререйку не проходят, см. ARCHITECTURE.md §3)."""
    used_search_docs = any(r["tool"] == "search_docs" for r in state.subtask_results)
    return "rerank" if used_search_docs else "build_prompt"


async def decide_after_rerank(state: LeanAgentState) -> str:
    """РЕАЛЬНЫЙ гейт, развёрнут вместе с rerank_node (то же сознательное исключение,
    см. там же). Пороги - из конфига (`gateway.rerank_no_data_threshold`/
    `rerank_grey_zone_threshold`), стартовые оценки, не откалиброванные eval'ом -
    пересмотр после появления eval-контура (ARCHITECTURE.md §10 шаг 1).
    """
    if not state.retrieval_data:
        return "empty"

    top_score = state.retrieval_data[0].metadata.score
    gateway_config = get_live_config().gateway
    if top_score < gateway_config.rerank_no_data_threshold:
        return "empty"
    if top_score < gateway_config.rerank_grey_zone_threshold:
        return "grey_zone"
    return "sufficient"


async def decide_after_reflect(state: LeanAgentState) -> str:
    """РЕАЛЬНЫЙ гейт - читает вердикт, который реально выставил reflect_node
    (LLM-решение sufficient/need_more/not_in_corpus, см. retrieval_nodes.py)."""
    return state.reflect_verdict or "sufficient"


async def decide_after_generate(state: LeanAgentState) -> str:
    """РЕАЛЬНЫЙ код-гейт перед post_actions (ARCHITECTURE.md §3): smalltalk_ood -
    пропуск всегда; иначе LLM-вызов post_actions только при совпадении
    эвристики-маркера в исходном вопросе пользователя (не в сгенерированном
    ответе) - экономит LLM-вызов на подавляющем большинстве сообщений без
    намерения действия."""
    if state.route in {"smalltalk", "out_of_domain"}:
        return "end"
    if _ACTION_MARKERS_RE.search(state.query):
        return "post_actions"
    return "end"
