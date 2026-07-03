from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.utils.exceptions import AppError
from backend.utils.logger_config import setup_logger
from backend.infrastructure import build_backend_infrastructure

# Подключаем роутеры (используем абсолютные импорты)
from backend.api.auth_routes import router as auth_router
from backend.api.profile_routes import router as profile_router
from backend.api.chats_routes import router as chats_router
from backend.api.admin_routes import router as admin_router
from backend.api.websocket_router import websocket_router
from backend.api.messenger_routes import router as messenger_router
from backend.api.stub_routes import knowledge_router, projects_router
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Инициализируем логгер
setup_logger("backend")
logger = logging.getLogger("backend")


class _MetricsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/metrics" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(_MetricsFilter())

# Настройки CORS
origins = [
    "http://localhost:8080",
    "http://localhost:8081",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        logger.info(
            "%s %s status=%s duration=%.4fs",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up infrastructure...")
    container = build_backend_infrastructure()
    app.state.container = container

    from backend.services.messenger.websocket_handlers import register_handlers
    register_handlers(container.socket_manager)

    yield

    logger.info("Shutting down infrastructure...")
    await container.engine.dispose()


# Создаем приложение
app = FastAPI(
    title="My Backend API",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(chats_router)
app.include_router(admin_router)
app.include_router(websocket_router)
app.include_router(messenger_router)
app.include_router(knowledge_router)
app.include_router(projects_router)

# Метрики
REQUEST_COUNT = Counter(
    'app_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'app_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)


@app.middleware("http")
async def prometheus_middleware(request, call_next):
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



# Глобальный обработчик наших кастомных ошибок
@app.exception_handler(AppError)
async def global_app_error_handler(request: Request, exc: AppError):
    # Логируем ошибку, чтобы не гадать, что случилось
    logger.warning(f"AppError: {exc.__class__.__name__} - {exc.message}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.__class__.__name__,
            "message": exc.message
        }
    )


# Опционально: обработчик для всех остальных непредвиденных ошибок (500)
@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": "InternalServerError",
            "message": "An unexpected error occurred."
        }
    )
