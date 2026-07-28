from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from langgraph.graph import END, StateGraph


from llm_service.ai_config import get_live_config
from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.llm_gateway import LLMGateway
from llm_service.tool_registry import build_tool_registry
from llm_service.application.lean_rag_models import LeanAgentState, QueryRouterProtocol, RetrievalResult, \
    FinalPromptData, RetrieveItem, PlanOutput
from llm_service.application.services.query_service import QueryExpansionService
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import  RetrievalService
from llm_service.utils.logger_config import setup_logger


logger = setup_logger("llm_service.lean_rag_agent")

# Дефолтный текст no_data - честный отказ вместо LLM-галлюцинации на пустом/слабом
# контексте (Принцип №4 "Честность важнее умности", ARCHITECTURE.md §3).
_NO_DATA_ANSWER = "В базе знаний нет информации по вашему запросу."

# Маркеры намерения действия для гейта post_actions - код-фильтр перед LLM-вызовом
# (см. ARCHITECTURE.md §3 post_actions). Проверяется по state.query (что попросил
# пользователь), не по сгенерированному ответу.
_ACTION_MARKERS_RE = re.compile(
    r"сохрани|закинь|запиши|создай задачу|добавь заметку|поправь заметку|обнови",
    re.IGNORECASE,
)

# Heartbeat между событиями SSE - забота EventSourceResponse (родной механизм FastAPI,
# см. agent_routers.py::answer_question_stream) - run_stream() сам больше не пингует ни
# основной токен-цикл, ни fallback. Раньше это делал _wait_with_heartbeat + asyncio.wait
# вручную - удалено вместе с миграцией на EventSourceResponse (см. историю в git).


class LeanRagAgent:
    def __init__(
        self,
        *,
        llm_provider: OpenAICompatLLMProvider,
        query_router: QueryRouterProtocol,
        retrieval_service: RetrievalService,
        reranker_service: RerankerService,
    ) -> None:
        self.llm_provider = llm_provider
        self.query_router = query_router
        self.retrieval_service = retrieval_service
        self.reranker_service = reranker_service
        self.tool_registry = build_tool_registry(retrieval_service=retrieval_service)
        self.llm_gateway = LLMGateway(llm_provider=llm_provider)
        self.app = self._build_graph()

        logger.info("Lean RAG agent initialized",)

    def _build_graph(self):
        """Собирает и компилирует LangGraph граф один раз при инициализации.

        Полный целевой граф из ARCHITECTURE.md §3 разложен целиком: где есть реальная
        реализация - подключена (search_docs, execute_subtasks-диспетчер, гейты-код);
        где нет - настоящая заглушка (см. комментарии у каждой *_node). Ветки
        personal/complex структурно присутствуют, но недостижимы живым трафиком -
        MLQueryRouter физически не может вернуть эти классы (нет обучающих примеров,
        см. ml_router/data/dataset.csv). Ветка domain_rag/smalltalk/out_of_domain
        проходит через новые ноды (rerank/extract_sources/post_actions-гейт), но
        каждая из них - доказуемый no-op на этом пути (см. docstring соответствующей
        ноды) - ответ не меняется ни на бит по сравнению со старым 5-нодовым графом.
        """
        workflow = StateGraph(LeanAgentState)

        workflow.add_node("router", self.route_node)
        workflow.add_node("expand_queries", self.expand_queries_node)
        workflow.add_node("retrieve_multi", self.retrieve_multi_node)
        workflow.add_node("rerank", self.rerank_node)
        workflow.add_node("reflect", self.reflect_node)
        workflow.add_node("no_data", self.no_data_node)
        workflow.add_node("personal_search", self.personal_search_node)
        workflow.add_node("resolve_docs", self.resolve_docs_node)
        workflow.add_node("clarify", self.clarify_node)
        workflow.add_node("background_report", self.background_report_node)
        workflow.add_node("gather_passports", self.gather_passports_node)
        workflow.add_node("plan", self.plan_node)
        workflow.add_node("execute_subtasks", self.execute_subtasks_node)
        workflow.add_node("build_prompt", self.build_prompt_node)
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("extract_sources", self.extract_sources_node)
        workflow.add_node("post_actions", self.post_actions_node)

        workflow.set_entry_point("router")
        workflow.add_conditional_edges(
            "router",
            self.decide_after_router,
            {
                "smalltalk": "build_prompt",
                "out_of_domain": "build_prompt",
                "expand": "expand_queries",
                "personal": "personal_search",
                "complex": "resolve_docs",
            },
        )
        workflow.add_edge("expand_queries", "retrieve_multi")
        workflow.add_edge("retrieve_multi", "rerank")
        workflow.add_conditional_edges(
            "rerank",
            self.decide_after_rerank,
            {"sufficient": "build_prompt", "grey_zone": "reflect", "empty": "no_data"},
        )
        workflow.add_conditional_edges(
            "reflect",
            self.decide_after_reflect,
            {"sufficient": "build_prompt", "need_more": "retrieve_multi", "not_in_corpus": "no_data"},
        )
        workflow.add_edge("no_data", END)

        workflow.add_edge("personal_search", "build_prompt")

        workflow.add_conditional_edges(
            "resolve_docs",
            self.decide_after_resolve_docs,
            {"clarify": "clarify", "background": "background_report", "gather_passports": "gather_passports"},
        )
        workflow.add_edge("clarify", END)
        workflow.add_edge("background_report", END)
        workflow.add_edge("gather_passports", "plan")
        workflow.add_edge("plan", "execute_subtasks")
        workflow.add_conditional_edges(
            "execute_subtasks",
            self.decide_after_execute_subtasks,
            {"rerank": "rerank", "build_prompt": "build_prompt"},
        )

        workflow.add_edge("build_prompt", "generate")
        workflow.add_edge("generate", "extract_sources")
        workflow.add_conditional_edges(
            "extract_sources",
            self.decide_after_generate,
            {"end": END, "post_actions": "post_actions"},
        )
        workflow.add_edge("post_actions", END)

        return workflow.compile()

    async def route_node(self, state: LeanAgentState) -> dict[str, str | list[str]]:
        """Определяет тип запроса: smalltalk / domain_rag / out_of_domain."""
        started = time.perf_counter()
        # .route() внутри синхронно гоняет SentenceTransformer.encode + predict_proba (CPU-bound) —
        # без to_thread это блокирует event loop на всё время эмбеддинга, стопоря остальные
        # параллельные запросы к сервису.
        route = await asyncio.to_thread(self.query_router.route, state.query)

        logger.info(
            "Router finished",
            extra={
                "route": route,
                "query": state.query,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"route": route}

    async def decide_after_router(self, state: LeanAgentState) -> str:
        """Выбирает следующий узел графа на основе route.

        personal/complex структурно смаршрутизированы, но MLQueryRouter физически
        не может их вернуть (нет обучающих примеров в ml_router/data/dataset.csv) -
        недостижимо живым трафиком, пока роутер не переобучен (см. ARCHITECTURE.md
        §10 шаг 1c).
        """
        if state.route in {"smalltalk", "out_of_domain", "personal", "complex"}:
            return state.route

        return "expand"

    async def expand_queries_node(self, state: LeanAgentState) -> dict[str, list[str]]:
        """Генерирует альтернативные формулировки запроса через LLM для улучшения recall."""
        started = time.perf_counter()
        query_expansion_prompt = get_live_config().prompts.query_expansion_prompt
        recent_history_str = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in state.messages
        )
        raw_expansion = (await self.llm_provider.generate_general(query=query_expansion_prompt.format(summary= state.summary,
                                                                                                      recent_history = recent_history_str,
                                                                                                      query = state.query),
                                                                  context="")).strip()
        expanded_pack = await QueryExpansionService.expand(original_query=state.query,
                                                           raw_query=raw_expansion)
        logger.info(
            "Expand queries finished",
            extra={
                "query": state.query,
                "expanded_queries_count": len(expanded_pack.queries),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"expanded_queries": expanded_pack.queries}

    async def retrieve_multi_node(self, state: LeanAgentState) -> dict[str, Any]:
        """Ищет релевантные чанки по всем формулировкам запроса и собирает контекст."""
        started = time.perf_counter()
        retrieval_result: RetrievalResult= await self.retrieval_service.retrieve(state.expanded_queries)

        logger.info(
            "Retrieve multi finished",
            extra={
                "query": state.query,
                "expanded_queries_count": len(state.expanded_queries),
                "retrieval_result": retrieval_result,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"retrieval_data": retrieval_result.items}

    async def rerank_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ rerank через TEI (bge-reranker-v2-m3, отдельный контейнер
        tei-reranker) - развёрнут 07.2026 как сознательное исключение из eval-ворот
        (ARCHITECTURE.md §1 п.3, второе исключение). Реранжирует по ЛУЧШЕМУ child-чанку
        каждого parent (то, что реально совпало с запросом при исходном векторном
        поиске - короткий точный фрагмент), не по parent_chunk целиком: тот может быть
        целой главой в тысячи символов - разбавляет сигнал кросс-энкодеру и рискует не
        влезть в его контекст. Сам parent_chunk (то, что уйдёт в промпт) не меняется -
        меняется только его новый score/позиция. Пустой retrieval_data - no-op, сетевой
        вызов не делается (RerankerService.rerank сам это обрабатывает).
        """
        if not state.retrieval_data:
            return {"retrieval_data": []}

        texts = [
            max(item.child_chunks, key=lambda c: c.score).text if item.child_chunks else item.parent_chunk
            for item in state.retrieval_data
        ]
        scored = await self.reranker_service.rerank(query=state.query, texts=texts)

        reordered: list[RetrieveItem] = []
        for entry in scored:
            original = state.retrieval_data[entry["index"]]
            new_metadata = original.metadata.model_copy(update={"score": entry["score"]})
            reordered.append(original.model_copy(update={"metadata": new_metadata}))
        return {"retrieval_data": reordered}

    async def decide_after_rerank(self, state: LeanAgentState) -> str:
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

    async def reflect_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: не вызывает LLM, не пересматривает выдачу (шаг 5 ARCHITECTURE.md,
        отдельный от rerank). Серая зона (см. decide_after_rerank) теперь реально сюда
        попадает, но не улучшает выдачу - просто пропускает в build_prompt как
        "sufficient", не отрезая ответ искусственно, пока reflect не реализован."""
        return {"reflect_rounds": state.reflect_rounds + 1, "reflect_verdict": "sufficient"}

    async def decide_after_reflect(self, state: LeanAgentState) -> str:
        """Захардкожен на "sufficient" - reflect (шаг 5) ещё не реализован, см. reflect_node."""
        return "sufficient"

    async def no_data_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНАЯ терминальная нода, достижима с сегодняшнего дня (см. decide_after_rerank) -
        честный отказ вместо LLM-галлюцинации на пустом/слабом контексте (Принцип №4)."""
        return {"retrieval_empty": True, "response_model": _NO_DATA_ANSWER}

    async def personal_search_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: search_notes/search_tasks ещё не реализованы (нет HTTP-клиента
        к backend, где живут заметки/задачи) - см. tool_registry.py. Недостижима живым
        трафиком - роутер не может вернуть route="personal" (нет обучающих примеров)."""
        return {"retrieval_data": []}

    async def resolve_docs_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: определение набора документов из attachment'ов сообщения или
        матча по названию/коду не реализовано - AskRequest несёт только одиночный
        doc_id, не список attachment'ов (см. ARCHITECTURE.md §3). Недостижима живым
        трафиком - роутер не может вернуть route="complex"."""
        return {"resolved_docs": []}

    async def decide_after_resolve_docs(self, state: LeanAgentState) -> str:
        """Реальный код-гейт (без внешних зависимостей) - корректен уже сегодня, хотя
        и недостижим (resolve_docs_node-заглушка всегда отдаёт пустой список)."""
        max_docs_interactive = get_live_config().gateway.max_docs_interactive
        if not state.resolved_docs:
            return "clarify"
        if len(state.resolved_docs) > max_docs_interactive:
            return "background"
        return "gather_passports"

    async def clarify_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА, терминальная нода - недостижима (см. resolve_docs_node)."""
        return {"response_model": "Уточните, пожалуйста, какие документы сравнить."}

    async def background_report_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА, терминальная нода - фоновый workflow для широкого сравнения
        (ARCHITECTURE.md §9/§10 шаг 8b) не реализован. Недостижима (см. resolve_docs_node)."""
        return {"response_model": "Широкое сравнение документов пока не реализовано."}

    async def gather_passports_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: get_document_passport ещё не реализован в реестре инструментов.
        Недостижима (см. resolve_docs_node/decide_after_resolve_docs)."""
        return {"document_passports": []}

    async def plan_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: не вызывает llm_gateway.generate_json - нет ни промпта, ни
        реальных паспортов документов, на основе которых строить план. Недостижима
        (route="complex" недостижим). Готовая инфраструктура (LLMGateway.generate_json)
        уже протестирована отдельно - подключение сюда после того, как появится промпт."""
        return {"plan": PlanOutput(subtasks=[], synthesis="")}

    async def execute_subtasks_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ универсальный диспетчер реестра (ARCHITECTURE.md §3/§8):
        находит tool по имени, валидирует args по args_schema, вызывает fn.
        Защитно отклоняет любой tool с access != "read", даже если plan (когда
        появится) ошибочно его предложит - вторая линия защиты сверх системного
        промпта plan. Недостижима сегодня - state.plan всегда None/subtasks=[]."""
        results: list[dict[str, Any]] = []
        subtasks = state.plan.subtasks if state.plan else []
        for subtask in subtasks:
            tool = self.tool_registry.get(subtask.tool)
            if tool is None:
                logger.warning("execute_subtasks: unknown tool '%s', skipping", subtask.tool)
                continue
            if tool.access != "read":
                logger.warning(
                    "execute_subtasks: refusing to auto-execute write tool '%s' - write only via post_actions",
                    subtask.tool,
                )
                continue
            args = tool.args_schema.model_validate(subtask.args)
            result = await tool.fn(**args.model_dump())
            results.append({"tool": subtask.tool, "result": result})
        return {"subtask_results": results}

    async def decide_after_execute_subtasks(self, state: LeanAgentState) -> str:
        """Реальный код-гейт: если среди подзадач были search_docs — маршрут в rerank
        (чтобы отранжировать document-поиск так же, как domain_rag), иначе прямо в
        build_prompt (search_notes/search_tasks ререйку не проходят, см. ARCHITECTURE.md §3)."""
        used_search_docs = any(r["tool"] == "search_docs" for r in state.subtask_results)
        return "rerank" if used_search_docs else "build_prompt"

    def _format_child_chunks_retrive_data(self, item: RetrieveItem) -> str:
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



    async def build_prompt_node(self, state: LeanAgentState) -> dict[str, Any]:
        started = time.perf_counter()

        context_str = "\n\n".join((self._format_child_chunks_retrive_data(item) for item in state.retrieval_data))
        history_str = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in state.messages
        )

        final_context = FinalPromptData(context=context_str,
                                        route=state.route,
                                        chat_history=history_str,
                                        summary=state.summary,
                                        current_query=state.query
                                        )

        logger.info(
            "Build prompt finished",
            extra={
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"final_context": final_context}

    async def generate_node(self, state: LeanAgentState) -> dict[str, str]:
        """Генерирует финальный ответ с учётом route, контекста и истории диалога."""
        started = time.perf_counter()
        answer = await self.llm_provider.generate(current_query=state.query,
                                                  data_prompt=state.final_context)


        logger.info(
            "Generate finished",
            extra={
                "route": state.route,
                "query": state.query,
                "answer_len": len(answer or ""),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"response_model": answer }

    @staticmethod
    def build_sources(retrieval_data: list[RetrieveItem]) -> list[dict[str, Any]]:
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

    async def extract_sources_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНАЯ нода: тот же build_sources, что раньше вызывался инлайново в
        run_stream()/agent_routers.py - вынесен в ноду графа, поведение не меняется."""
        return {"sources": self.build_sources(state.retrieval_data)}

    async def decide_after_generate(self, state: LeanAgentState) -> str:
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

    async def post_actions_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: настоящий no-op - не делает I/O, не вызывает LLM, proposed_action
        остаётся None. Нет ни промпта, ни write-инструментов с реальной реализацией
        (create_task/create_note/update_note - все NotImplementedError в реестре)."""
        return {"proposed_action": None}

    async def run_stream(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]],
    ):
        """SSE-вариант run(): стримит токены ответа вместо ожидания полного completion.

        Контракт событий: status -> token* -> sources -> done. Keep-alive между дельтами -
        забота EventSourceResponse (см. agent_routers.py), сам генератор ничего не пингует.
        Компилированный
        self.app.ainvoke() не даёт стримить токены generate без отдельной машинерии
        LangGraph (astream_events) - узлы до generate штатно быстрые (роутинг/поиск),
        поэтому здесь они вызываются напрямую в том же порядке, что и в графе
        (см. _build_graph), а стримится только сам LLM-вызов в generate.

        Ретраи/heartbeat/fallback (см. ниже) защищают ТОЛЬКО сам вызов LLM - осознанно,
        не route_node/expand_queries_node/retrieve_multi_node/build_prompt_node. Это
        внутренние, обычно быстрые вызовы (ML-роутер в процессе, Qdrant в той же
        docker-сети) - не тот класс ненадёжности, что внешний HTTP до стороннего шлюза,
        ради которого строилась вся защита ниже. Сбой в них сразу уходит в общий except
        в agent_routers.py::answer_question_stream как обычная ошибка, без ретрая.
        """
        started = time.perf_counter()

        state = LeanAgentState(
            query=query,
            messages=history_messages_db or [],
            summary=summary,
            route="domain_rag",
            expanded_queries=[query],
        )

        state = state.model_copy(update=await self.route_node(state))
        yield {"event": "status", "data": {"stage": "route", "route": state.route}}

        # Граф в _build_graph() уже поддерживает personal/complex - run_stream() пока
        # нет (см. ARCHITECTURE.md, план внедрения). Явный guard вместо тихого
        # рассинхрона: если роутер когда-нибудь реально вернёт один из этих классов
        # (после переобучения, шаг 1c), это должно упасть громко, а не молча
        # обработаться как domain_rag.
        if state.route not in {"smalltalk", "out_of_domain", "domain_rag"}:
            raise NotImplementedError(
                f"run_stream() has no SSE path for route={state.route!r} yet - "
                "see _build_graph() for the compiled-graph (non-stream) equivalent"
            )

        if await self.decide_after_router(state) == "expand":
            state = state.model_copy(update=await self.expand_queries_node(state))
            yield {"event": "status", "data": {"stage": "expand"}}

            state = state.model_copy(update=await self.retrieve_multi_node(state))
            yield {"event": "status", "data": {"stage": "retrieve", "count": len(state.retrieval_data)}}

            # rerank_node - реальный (развёрнут 07.2026, см. её docstring). decide_after_rerank
            # обязателен здесь же - иначе /llm/answer (граф, через no_data-ветку) и
            # /llm/answer/stream (этот метод) разошлись бы: граф корректно обрывается в
            # no_data при пустом/слабом retrieval, а этот метод раньше безусловно шёл в
            # generate дальше.
            state = state.model_copy(update=await self.rerank_node(state))

            rerank_decision = await self.decide_after_rerank(state)
            if rerank_decision == "grey_zone":
                state = state.model_copy(update=await self.reflect_node(state))
                rerank_decision = await self.decide_after_reflect(state)

            if rerank_decision == "empty":
                state = state.model_copy(update=await self.no_data_node(state))
                state = state.model_copy(update=await self.extract_sources_node(state))
                yield {"event": "token", "data": {"text": state.response_model}}
                yield {"event": "sources", "data": {"sources": state.sources}}
                yield {"event": "done", "data": {"answer": state.response_model}}
                logger.info(
                    "Lean agent run_stream finished (no_data)",
                    extra={
                        "query": query,
                        "route": state.route,
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                    },
                )
                return

        state = state.model_copy(update=await self.build_prompt_node(state))

        answer_parts: list[str] = []
        try:
            async for delta in self.llm_provider.generate_stream(
                current_query=state.query, data_prompt=state.final_context
            ):
                answer_parts.append(delta)
                yield {"event": "token", "data": {"text": delta}}
        except Exception as exc:
            if answer_parts:
                # Уже показали часть ответа - fallback невозможен, он создал бы вторую,
                # не связанную с первой генерацию поверх уже отданных токенов (см.
                # _stream_completion_with_retry). Помечаем обрыв и всё равно завершаем
                # sources/done, иначе backend сохранит в БД пустой ответ вместо уже
                # показанного текста.
                logger.warning("LLM stream interrupted mid-generation: %s", exc)
                note = "\n\n_[ответ прерван: обрыв соединения с LLM]_"
                answer_parts.append(note)
                yield {"event": "token", "data": {"text": note}}
            else:
                # Ни одного токена не дошло - стриминг сломан целиком (ретраи в
                # generate_stream() уже исчерпаны на этом этапе), а не просто сеть
                # моргнула. Именно так вело себя gatellm.ru, когда не умел релеить
                # SSE от OpenRouter (502 на 100% запросов с stream=true, при этом
                # stream=false работал нормально) - разовый fallback на обычный, не
                # потоковый вызов вместо немедленной сдачи в "прервано".
                logger.warning(
                    "LLM stream produced zero tokens, falling back to non-streaming generate(): %s", exc,
                )
                try:
                    answer = await self.llm_provider.generate(
                        current_query=state.query, data_prompt=state.final_context
                    )
                except Exception as fallback_exc:
                    logger.exception("Non-streaming fallback also failed")
                    note = f"_Не удалось получить ответ: {fallback_exc}_"
                    answer_parts.append(note)
                    yield {"event": "token", "data": {"text": note}}
                else:
                    answer_parts.append(answer)
                    yield {"event": "token", "data": {"text": answer}}

        answer = "".join(answer_parts)
        state = state.model_copy(update=await self.extract_sources_node(state))
        sources = state.sources

        # Гейт post_actions - см. decide_after_generate/post_actions_node. Не
        # добавляет нового SSE-события: post_actions_node сегодня настоящий no-op
        # (proposed_action остаётся None), это лишь та же точка, что и в
        # _build_graph(), защищённая от будущего рассинхрона графа/стрима.
        state = state.model_copy(update={"response_model": answer})
        if await self.decide_after_generate(state) == "post_actions":
            await self.post_actions_node(state)

        yield {"event": "sources", "data": {"sources": sources}}
        yield {"event": "done", "data": {"answer": answer}}

        logger.info(
            "Lean agent run_stream finished",
            extra={
                "query": query,
                "route": state.route,
                "sources_count": len(sources),
                "answer_len": len(answer),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

    async def run(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]]
    ) ->  dict[str, Any]:
        """Точка входа — собирает начальный стейт и запускает граф."""
        started = time.perf_counter()

        inputs = LeanAgentState(
            query=query,
            messages=history_messages_db or [],
            summary=summary,
            route="domain_rag",
            expanded_queries=[query],
        )

        final_state = await self.app.ainvoke(inputs)

        logger.info(
            "Lean agent run finished",
            extra={
                "query": query,
                "route": final_state.get("route"),
                "sources_count": len(final_state.get("sources", [])),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return final_state
