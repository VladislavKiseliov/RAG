from contextlib import asynccontextmanager
from fastapi import FastAPI

from rag_service.api.exception_handlers import register_exception_handlers
from rag_service.api.rag_routes import router as rag_router
from rag_service.infrastructure import build_rag_infrastructure, RagContainer
from rag_service.utils.logger_config import setup_logger

setup_logger("rag_service")


@asynccontextmanager
async def lifespan(app: FastAPI):

    container: RagContainer = build_rag_infrastructure()
    app.state.container = container

    yield

    await container.engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(rag_router)
register_exception_handlers(app)
