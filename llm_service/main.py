from fastapi import FastAPI

from llm_service.api.agent_routes import router as llm_router
from llm_service.utils.logger_config import setup_logger

setup_logger("llm_service")

app = FastAPI()
app.include_router(llm_router)
