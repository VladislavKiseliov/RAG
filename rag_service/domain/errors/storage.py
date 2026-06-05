from starlette import status

from rag_service.domain.errors.base import AppError


class StorageError(AppError):
    """Base class for object storage errors."""

    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StorageReadError(StorageError):
    """Raised when a storage read operation fails."""

    def __init__(self, message: str = "Failed to read object from storage"):
        super().__init__(message=message)


class StorageWriteError(StorageError):
    """Raised when a storage write operation fails."""

    def __init__(self, message: str = "Failed to write object to storage"):
        super().__init__(message=message)


class StorageDeleteError(StorageError):
    """Raised when a storage delete operation fails."""

    def __init__(self, message: str = "Failed to delete object from storage"):
        super().__init__(message=message)


class StorageMetadataError(StorageError):
    """Raised when storage metadata operations fail."""

    def __init__(self, message: str = "Failed to process object metadata"):
        super().__init__(message=message)


class StorageNotFoundError(StorageError):
    """Raised when a requested object does not exist in storage."""

    def __init__(self, message: str = "Object not found in storage"):
        super().__init__(message=message)
