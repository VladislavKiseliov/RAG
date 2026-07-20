import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from rag_service.api.exception_handlers import register_exception_handlers
from rag_service.api.rag_routes import router as rag_router
from rag_service.api.note_routes import router as note_router
from rag_service.container import build_rag_infrastructure, RagContainer
from rag_service.utils.logger_config import setup_logger

setup_logger("rag_service")


class MetricsEndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/metrics" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(MetricsEndpointFilter())

REQUEST_COUNT = Counter(
    "rag_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_DURATION = Histogram(
    "rag_request_duration_seconds", "HTTP request duration", ["method", "endpoint"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container: RagContainer = await build_rag_infrastructure()
    app.state.container = container
    yield
    await container.engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(rag_router)
app.include_router(note_router)
register_exception_handlers(app)

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)
    method = request.method
    endpoint = request.url.path
    with REQUEST_DURATION.labels(method, endpoint).time():
        response = await call_next(request)
    REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
