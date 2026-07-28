from __future__ import annotations

from dataclasses import dataclass


from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.application.lean_rag_models import QueryRouterProtocol
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.LLM_provider import GroqLLMProvider, LLMProvider, OpenAICompatLLMProvider
from llm_service.settings import settings


@dataclass(frozen=True)
class LLMContainer:
    agent: LeanRagAgent


def _build_query_router() -> QueryRouterProtocol:
    model_path = settings.ML_ROUTER_MODEL_PATH
    import joblib
    from sentence_transformers import SentenceTransformer

    from llm_service.ml_router.router import MLQueryRouter

    clf = joblib.load(model_path)
    embedder = SentenceTransformer("intfloat/multilingual-e5-large")
    return MLQueryRouter(
        clf=clf,
        embedder=embedder,
        confidence_threshold=settings.ML_ROUTER_CONFIDENCE_THRESHOLD,
    )


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