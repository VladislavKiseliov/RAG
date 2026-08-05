from __future__ import annotations

from dataclasses import dataclass


from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.application.lean_rag_models import QueryRouterProtocol
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.LLM_provider import GroqLLMProvider, LLMProvider, OpenAICompatLLMProvider
from llm_service.settings import settings
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.infrastructure")


@dataclass(frozen=True)
class LLMContainer:
    agent: LeanRagAgent


def _build_query_router() -> QueryRouterProtocol | None:
    """route_node (единственный вызывающий .route()) отключён от живого графа
    (planner-first переход, см. legacy_disabled_nodes.py) - построенный роутер
    сегодня никем не используется. Раньше сбой здесь (отсутствующий/битый
    intent_model.pkl, несовместимая версия joblib/sklearn) валил весь build_container()
    и не давал сервису подняться вообще - из-за компонента, который по факту мёртв.
    Теперь best-effort: неудача не фатальна, agent просто получает None вместо роутера
    (безопасно - ничего живое его не вызывает)."""
    try:
        model_path = settings.ML_ROUTER_MODEL_PATH
        import joblib

        from llm_service.ml_router.router import MLQueryRouter
        from llm_service.ml_router.tei_embedder import TeiSyncEmbedder

        clf = joblib.load(model_path)
        embedder = TeiSyncEmbedder(base_url=settings.TEI_URL)
        return MLQueryRouter(
            clf=clf,
            embedder=embedder,
            confidence_threshold=settings.ML_ROUTER_CONFIDENCE_THRESHOLD,
        )
    except Exception:
        logger.warning(
            "Failed to build ML query router (dead code on the live graph, see "
            "legacy_disabled_nodes.py) - continuing startup without it", exc_info=True,
        )
        return None


def _build_llm_provider() -> LLMProvider:

    if settings.LLM_PROVIDER == "groq":
        return GroqLLMProvider(
            api_key=settings.HF_TOKEN,
        )
    return OpenAICompatLLMProvider(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )


def build_rag_client() -> RetrievalService:
    return RetrievalService(
        base_url=settings.RAG_SERVICE_URL,
        timeout=settings.LLM_RAG_TIMEOUT,
    )


def build_reranker_client() -> RerankerService:
    return RerankerService(
        base_url=settings.RERANKER_TEI_URL,
        timeout=settings.LLM_RERANK_TIMEOUT,
    )


def build_container() -> LLMContainer:
    retrieve_service = build_rag_client()
    llm_provider = _build_llm_provider()
    agent = LeanRagAgent(llm_provider = llm_provider,
                        query_router=_build_query_router(),
                        retrieval_service=retrieve_service,
                        reranker_service=build_reranker_client(),
                        )
    return LLMContainer(agent=agent)