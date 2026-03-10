from fastapi import FastAPI

from rag_service.api.agent_routes import router as agent_router
from rag_service.api.rag_routes import router as rag_router

from contextlib import asynccontextmanager
from fastapi import FastAPI
from rag_service.infrastructure import build_rag_infrastructure, _build_minio_provider
from rag_service.providers import minio_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, search_service, ingestion_service= build_rag_infrastructure()
    app.state.search_service = search_service
    app.state.ingestion_service = ingestion_service
    app.state.minio_provider = minio_provider
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(rag_router)
app.include_router(agent_router)