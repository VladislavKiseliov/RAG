from contextlib import asynccontextmanager
from fastapi import FastAPI

from rag_service.api.rag_routes import router as rag_router
from rag_service.infrastructure import build_rag_infrastructure


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_rag_infrastructure()

    app.state.retrieve_service = container.retrieve_service
    app.state.ingestion_service = container.ingestion_service
    app.state.minio_provider = container.minio_provider
    app.state.document_service = container.document_service
    app.state.document_query_service = container.document_query_service

    yield

    await container.engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(rag_router)