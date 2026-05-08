from __future__ import annotations

import operator
import os
import time
from typing import Annotated, List, TypedDict, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph

from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.context_builder import build_context
from llm_service.application.rag_client import RagClient
from llm_service.promt.promts import ANALIZE_NODE_PROMT, REWRITE_OPTIMIZE_PROMPT, REWRITE_EXPAND_PROMPT, \
    REWRITE_SIMPLIFY_PROMPT, GRADE_DOCUMENTS_PROMPT
from llm_service.utils.logger_config import setup_logger




class AgentState(TypedDict):
    query: str
    original_query: str
    needs_retrieval: bool
    is_relevant: bool
    answer: str
    search_attempts: int
    messages: Annotated[List[BaseMessage], operator.add]
    summary: str
    context: List[str]


logger = setup_logger("llm_service.agent_service")

llm_provider = OpenAICompatLLMProvider(
    base_url=os.getenv("LLM_BASE_URL", "https://gatellm.ru/v1"),
    model=os.getenv("LLM_MODEL", "qwen/qwen3.5-9b"),
)

class LlmLangGraphAgent:
    def __init__(
        self,
        llm_provider: OpenAICompatLLMProvider,
        rag_client: RagClient,
    ) -> None:
        self.llm_provider = llm_provider
        self._rag_client = rag_client
        self.app = self._build_graph()
        self._max_context_chars: int = 12000
        logger.info("LangGraph agent initialized", extra={"max_context_chars": self._max_context_chars})

    def _build_graph(self):

        logger.info("Building LangGraph workflow")
        workflow = StateGraph(AgentState)

        # Добавляем все узлы из схемы
        workflow.add_node("analyzer", self.analyzer_node)
        workflow.add_node("rewriter", self.rewrite_node)
        workflow.add_node("retriever", self.retrieve_node)
        workflow.add_node("grader", self.grade_node)
        workflow.add_node("agent", self.call_model_node)
        workflow.add_node("summarizer", self.summarize_node)

        # Логика переходов
        workflow.set_entry_point("analyzer")

        # 1. Analyzer -> Rewriter или Agent
        workflow.add_conditional_edges(
            "analyzer",
            self.decide_retrieval,
            {True: "rewriter", False: "agent"}
        )

        # 2. Поиск
        workflow.add_edge("rewriter", "retriever")
        workflow.add_edge("retriever", "grader")

        # 3. Grader -> Rewriter (цикл) или Agent
        workflow.add_conditional_edges(
            "grader",
            self.decide_search_quality,
            {"rewrite": "rewriter", "generate": "agent"}
        )

        # 4. Финал и суммаризация
        workflow.add_conditional_edges(
            "agent",
            self.should_summarize,
            {"summarize": "summarizer", "end": END}
        )
        workflow.add_edge("summarizer", END)
        logger.info("Build LangGraph workflow ok")

        return workflow.compile()


    async def analyzer_node(self, state: AgentState):
        """Решает, нужен ли поиск в базе знаний"""
        logger.info("Analyzer: Assessing if RAG is needed")

        # Подставляешь переменные через .format()
        prompt = ANALIZE_NODE_PROMT.format(
            context=state.get("summary", "Нет контекста"),
            query=state["query"]
        )

        response = await self.llm_provider.generate_general(query=prompt, context="")
        decision = response.strip().upper()
        needs_retrieval = decision.startswith("YES")

        logger.info(f"Analyzer decision: needs_retrieval={needs_retrieval}")

        return {
            "needs_retrieval": needs_retrieval,
            "search_attempts": 0
        }

    async def rewrite_node(self, state: AgentState):
        """Перефразирует запрос для улучшения поиска"""

        logger.info(f"Rewrite: Reformulating query (attempt #{state['search_attempts']})")

        original_query = state["query"]
        search_attempts = state.get("search_attempts", 0)

        # Определяем стратегию
        if search_attempts == 0:
            strategy = "optimize"
            prompt_template = REWRITE_OPTIMIZE_PROMPT
        elif search_attempts == 1:
            strategy = "expand"
            prompt_template = REWRITE_EXPAND_PROMPT
        else:
            strategy = "simplify"
            prompt_template = REWRITE_SIMPLIFY_PROMPT

        # Формируем промпт
        prompt = prompt_template.format(
            query=original_query,
            attempt=search_attempts + 1
        )

        # Вызов модели
        rewritten = await self.llm_provider.generate_general(query=prompt, context="")
        rewritten = rewritten.strip()

        logger.info(f"Rewrite [{strategy}]: '{original_query}' -> '{rewritten}'")
        print(f"Rewrite'{original_query}' -> '{rewritten}'")
        return {
            "query": rewritten,
            "original_query": original_query if "original_query" not in state else state["original_query"]
        }

    async def retrieve_node(self, state: AgentState) -> dict[str, List[str]]:
        started = time.perf_counter()
        logger.info(
            "Retriever started",
            extra={
                "query": state.get("query"),
                "history_len": len(state.get("messages", [])),
            },
        )

        result = await self._rag_client.retrieve(query=state.get("query"))
        sources = result.get("items") or []
        context = build_context(sources, self._max_context_chars)

        logger.info(
            "Retriever finished",
            extra={
                "sources_count": len(sources),
                "context_len": len(context),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"context": [f"Technical extract for query: {context}"]}

    async def grade_node(self, state: AgentState):
        """Оценивает релевантность найденного контекста"""
        logger.info("Grade: Evaluating document relevance")

        documents = state.get("context", [])
        query = state.get("original_query", state["query"])  # Используем оригинальный запрос

        # Если документов нет — сразу не релевантно
        if not documents:
            logger.info("Grade: No documents found -> not relevant")
            return {"is_relevant": False}

        # Формируем контекст из документов
        context = "\n\n---\n\n".join(documents[:5])  # Берём топ-5 документов

        prompt = GRADE_DOCUMENTS_PROMPT.format(
            query=query,
            context=context
        )

        response = await self.llm_provider.generate_general(query=prompt, context="")
        decision = response.strip().upper()

        is_relevant = decision.startswith("YES")

        logger.info(f"Grade: is_relevant={is_relevant}, documents_count={len(documents)}")

        return {"is_relevant": is_relevant}


    async def call_model_node(self, state: AgentState) -> dict[str, List[AIMessage]]:
        started = time.perf_counter()
        full_context = f"History summary: {state['messages']}\n\nContext: " + "\n".join(state["context"])

        logger.info(
            "Model generation started",
            extra={
                "query": state["query"],
                "history_len": len(state.get("messages", [])),
                "context_entries": len(state.get("context", [])),
                "full_context_len": len(full_context),
            },
        )

        answer = await self.llm_provider.generate_general(
            query=state["query"],
            context=full_context,
        )

        logger.info(
            "Model generation finished",
            extra={
                "answer_len": len(answer or ""),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"messages": [AIMessage(content=answer)]}

    async def summarize_node(self, state: AgentState) -> dict[str, str]:
        logger.info(
            "Summarizer executed",
            extra={"history_len": len(state.get("messages", []))},
        )
        return {"summary": "Conversation summary was updated."}



    # --- ЛОГИКА ПЕРЕХОДОВ (EDGES) ---

    def decide_retrieval(self, state: AgentState) -> bool:
        return state.get("needs_retrieval", False)

    def decide_search_quality(self, state: AgentState) -> Literal["rewrite", "generate"]:
        if state.get("is_relevant"):
            return "generate"

        if state.get("search_attempts", 0) < 3:
            return "rewrite"


        return "generate"


    def should_summarize(self, state: AgentState) -> str:
        history_len = len(state.get("messages", []))
        decision = "end"
        if history_len > 2:
            decision = "end"

        logger.info(
            "Summarize decision",
            extra={"history_len": history_len, "decision": decision},
        )
        return decision

    @staticmethod
    def convert_db_to_langgraph(history_messages_db):
        logger.info(
            "Converting DB history to LangGraph messages",
            extra={"history_db_len": len(history_messages_db or [])},
        )
        lg_messages = []
        for message in history_messages_db or []:
            role = message.get("role")
            content = message.get("content", "")
            if role == "user":
                lg_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lg_messages.append(AIMessage(content=content))
        logger.info(
            "History converted",
            extra={"history_langgraph_len": len(lg_messages)},
        )
        return lg_messages

    async def run(
        self,
        *,
        query: str,
        history_messages_db,
        summary: str = "User is a PLC programmer.",
        context: List[str] | None = None,
    ) -> AgentState:
        started = time.perf_counter()
        logger.info(
            "Agent run started",
            extra={
                "query": query,
                "history_db_len": len(history_messages_db or []),
                "summary_len": len(summary or ""),
                "context_len": len(context or []),
            },
        )


        history_messages = self.convert_db_to_langgraph(history_messages_db)
        inputs: AgentState = {
            "query": query,
            "original_query":query,
            "messages": history_messages,
            "summary": summary,
            "context": context or [],
        }

        final_state = await self.app.ainvoke(inputs)

        logger.info(
            "Agent run finished",
            extra={
                "final_messages_len": len(final_state.get("messages", [])),
                "final_context_len": len(final_state.get("context", [])),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return final_state
