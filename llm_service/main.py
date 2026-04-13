from fastapi import FastAPI

from llm_service.api.agent_routes import router as llm_router

app = FastAPI()
app.include_router(llm_router)
