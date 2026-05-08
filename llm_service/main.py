from contextlib import asynccontextmanager

from fastapi import FastAPI

from llm_service.api.agent_routes import router as llm_router
from llm_service.infrastructure import build_answer_service
from llm_service.utils.logger_config import setup_logger

setup_logger("llm_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_answer_service()
    app.state.container = container
    yield
    await container.engine.dispose()

app = FastAPI(lifespan=lifespan)
app.include_router(llm_router)
