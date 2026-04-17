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
from backend.api.routes import router

# Инициализируем логгер
setup_logger("backend")
logger = logging.getLogger("backend")

# Настройки CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
    # Сохраняем в sate для доступа через Depends(get_auth_service)
    app.state.container = container
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

# Подключаем роутеры
app.include_router(router)
#app.include_router(admin_router)

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
