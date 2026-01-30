from fastapi import FastAPI

from .api.routes import router


app = FastAPI(title="Document Ingestion Service")
app.include_router(router)
