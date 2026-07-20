import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from llm_service.api.agent_routers import router as llm_router
from llm_service.exceptions import LLMServiceError
from llm_service.infrastructure import build_container
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service")


class MetricsEndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/metrics" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(MetricsEndpointFilter())

REQUEST_COUNT = Counter(
    "llm_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds", "HTTP request duration", ["method", "endpoint"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.container = build_container()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(llm_router)


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


@app.exception_handler(LLMServiceError)
async def llm_error_handler(request: Request, exc: LLMServiceError):
    logger.warning(f"LLMServiceError: {exc.__class__.__name__} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.__class__.__name__,
            "message": exc.message,
        },
    )