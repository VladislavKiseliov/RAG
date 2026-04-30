from rag_service.domain.errors.base import AppError, UploadValidationError
from rag_service.domain.errors.postgres import (
    ChunkInsertError,
    DeadlockRetryExceeded,
    DocumentAlreadyExists,
    DocumentCreateError,
    DocumentDeleteError,
    DocumentNotFound,
    DocumentReadError,
    DocumentRepositoryError,
    DocumentUpdateError,
    PostgresError,
)
from rag_service.domain.errors.storage import (
    StorageDeleteError,
    StorageError,
    StorageMetadataError,
    StorageReadError,
    StorageWriteError,
)
from rag_service.domain.errors.vector import (
    VectorCollectionError,
    VectorDeleteError,
    VectorSearchError,
    VectorStoreError,
    VectorUpsertError,
)

__all__ = [
    "AppError",
    "UploadValidationError",
    "PostgresError",
    "DocumentAlreadyExists",
    "DocumentNotFound",
    "DocumentRepositoryError",
    "DocumentReadError",
    "DocumentCreateError",
    "DocumentUpdateError",
    "DocumentDeleteError",
    "ChunkInsertError",
    "DeadlockRetryExceeded",
    "StorageError",
    "StorageReadError",
    "StorageWriteError",
    "StorageDeleteError",
    "StorageMetadataError",
    "VectorStoreError",
    "VectorUpsertError",
    "VectorSearchError",
    "VectorDeleteError",
    "VectorCollectionError",
]
