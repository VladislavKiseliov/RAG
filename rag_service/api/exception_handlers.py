from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rag_service.domain.errors import AppError, PostgresError, StorageError, VectorStoreError
from rag_service.utils.logger_config import setup_logger

logger = setup_logger("rag_service.errors")


def _build_error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.__class__.__name__,
            "message": exc.message,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PostgresError)
    async def postgres_error_handler(request: Request, exc: PostgresError):
        logger.warning("PostgresError: %s - %s", exc.__class__.__name__, exc.message)
        return _build_error_response(exc)

    @app.exception_handler(StorageError)
    async def storage_error_handler(request: Request, exc: StorageError):
        logger.warning("StorageError: %s - %s", exc.__class__.__name__, exc.message)
        return _build_error_response(exc)

    @app.exception_handler(VectorStoreError)
    async def vector_error_handler(request: Request, exc: VectorStoreError):
        logger.warning("VectorStoreError: %s - %s", exc.__class__.__name__, exc.message)
        return _build_error_response(exc)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.warning("AppError: %s - %s", exc.__class__.__name__, exc.message)
        return _build_error_response(exc)

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception):
        logger.error("Unexpected error: %s", str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": "InternalServerError",
                "message": "An unexpected error occurred.",
            },
        )
