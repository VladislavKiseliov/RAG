from starlette import status

from rag_service.domain.errors.base import AppError


class VectorStoreError(AppError):
    """Base class for vector storage errors."""

    def __init__(self, message: str = "Vector store operation failed"):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VectorUpsertError(VectorStoreError):
    """Raised when vector upsert fails."""

    def __init__(self, message: str = "Failed to upsert vectors"):
        super().__init__(message=message)


class VectorSearchError(VectorStoreError):
    """Raised when vector search fails."""

    def __init__(self, message: str = "Failed to search vectors"):
        super().__init__(message=message)


class VectorDeleteError(VectorStoreError):
    """Raised when vector delete fails."""

    def __init__(self, message: str = "Failed to delete vectors"):
        super().__init__(message=message)


class VectorCollectionError(VectorStoreError):
    """Raised when vector collection setup fails."""

    def __init__(self, message: str = "Failed to ensure vector collection"):
        super().__init__(message=message)
