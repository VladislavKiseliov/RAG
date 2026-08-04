"""AgentNodes - контейнер всех нод графа (живых и disabled-legacy), собранных
через миксины. Каждый *NodesMixin живёт в своём файле (SRP по типу ответственности:
planning/retrieval/generation/legacy), а состояние (DI-зависимости) общее - через
self, как обычно у смешиваемых классов."""

from __future__ import annotations

from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.agent.generation_nodes import GenerationNodesMixin
from llm_service.application.agent.legacy_disabled_nodes import LegacyDisabledNodesMixin
from llm_service.application.agent.planning_nodes import PlanningNodesMixin
from llm_service.application.agent.retrieval_nodes import RetrievalNodesMixin
from llm_service.application.lean_rag_models import QueryRouterProtocol
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.llm_gateway import LLMGateway
from llm_service.tool_registry import Tool


class AgentNodes(
    PlanningNodesMixin,
    RetrievalNodesMixin,
    GenerationNodesMixin,
    LegacyDisabledNodesMixin,
):
    def __init__(
        self,
        *,
        llm_provider: OpenAICompatLLMProvider,
        llm_gateway: LLMGateway,
        query_router: QueryRouterProtocol,
        retrieval_service: RetrievalService,
        reranker_service: RerankerService,
        tool_registry: dict[str, Tool],
    ) -> None:
        self.llm_provider = llm_provider
        self.llm_gateway = llm_gateway
        self.query_router = query_router
        self.retrieval_service = retrieval_service
        self.reranker_service = reranker_service
        self.tool_registry = tool_registry
