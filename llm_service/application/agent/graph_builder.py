"""Сборка и компиляция LangGraph графа - вынесена из LeanRagAgent, чтобы конструктор
графа не был перемешан с бизнес-логикой нод."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from llm_service.application.agent import routing_decisions as decisions
from llm_service.application.agent.agent_nodes import AgentNodes
from llm_service.application.lean_rag_models import LeanAgentState


def build_agent_graph(nodes: AgentNodes):
    """Собирает и компилирует LangGraph граф один раз при инициализации агента.

    ML-роутер отключён от графа в пользу planner-first схемы - каждый запрос идёт
    прямо в plan_node, который через LLM сам решает, нужен ли поиск (вплоть до
    пустого плана для smalltalk/оффтопика), вместо отдельного обученного
    классификатора. Сам классификатор (route_node/decide_after_router) удалён
    2026-08-06 - не просто отключён (см. legacy_disabled_nodes.py). Остальное -
    expand_queries_node/retrieve_multi_node/personal_search_node/resolve_docs_node/
    clarify_node/background_report_node/gather_passports_node - НЕ удалены, просто
    не добавлены в этот граф (`add_node`), можно вернуть, не трогая код нод.

    plan -> execute_subtasks (реальный диспетчер тулов, единственный рабочий тул -
    search_docs) -> rerank, если был поиск, иначе сразу build_prompt.
    """
    workflow = StateGraph(LeanAgentState)

    workflow.add_node("rerank", nodes.rerank_node)
    workflow.add_node("reflect", nodes.reflect_node)
    workflow.add_node("no_data", nodes.no_data_node)
    workflow.add_node("plan", nodes.plan_node)
    workflow.add_node("execute_subtasks", nodes.execute_subtasks_node)
    workflow.add_node("build_prompt", nodes.build_prompt_node)
    workflow.add_node("generate", nodes.generate_node)
    workflow.add_node("extract_sources", nodes.extract_sources_node)
    workflow.add_node("post_actions", nodes.post_actions_node)

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "execute_subtasks")
    workflow.add_conditional_edges(
        "execute_subtasks",
        decisions.decide_after_execute_subtasks,
        {"rerank": "rerank", "build_prompt": "build_prompt"},
    )
    workflow.add_conditional_edges(
        "rerank",
        decisions.decide_after_rerank,
        {"sufficient": "build_prompt", "grey_zone": "reflect", "empty": "reflect"},
    )
    workflow.add_conditional_edges(
        "reflect",
        decisions.decide_after_reflect,
        {"sufficient": "build_prompt", "need_more": "execute_subtasks", "not_in_corpus": "no_data"},
    )
    workflow.add_edge("no_data", END)

    workflow.add_edge("build_prompt", "generate")
    workflow.add_edge("generate", "extract_sources")
    workflow.add_conditional_edges(
        "extract_sources",
        decisions.decide_after_generate,
        {"end": END, "post_actions": "post_actions"},
    )
    workflow.add_edge("post_actions", END)

    return workflow.compile()
