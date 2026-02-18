from fastapi import FastAPI

from rag_service.api.rag_routes import router as rag_router
from rag_service.api.agent_routes import router as agent_router

app = FastAPI()
app.include_router(rag_router)
app.include_router(agent_router)
