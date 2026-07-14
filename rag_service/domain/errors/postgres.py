from starlette import status

from rag_service.domain.errors.base import AppError


class PostgresError(AppError):
    """Base class for Postgres-backed models errors."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentAlreadyExists(PostgresError):
    """Raised when creating a duplicate document."""

    def __init__(self, file_hash: str):
        self.file_hash = file_hash
        super().__init__(message=f"Document with hash '{file_hash}' already exists")
        self.status_code = status.HTTP_409_CONFLICT


class DocumentNotFound(PostgresError):
    """Raised when a requested document does not exist."""

    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        super().__init__(message=f"Document '{doc_id}' not found")
        self.status_code = status.HTTP_404_NOT_FOUND


class DocumentByStorageKeyNotFound(PostgresError):
    """Raised when a document cannot be found by storage key."""

    def __init__(self, s3key: str):
        self.s3key = s3key
        super().__init__(message=f"Document with storage key '{s3key}' not found")
        self.status_code = status.HTTP_404_NOT_FOUND


class DocumentRepositoryError(PostgresError):
    """Generic repository failure in document models."""


class DocumentReadError(DocumentRepositoryError):
    """Raised when a read operation fails."""

    def __init__(self, message: str = "Failed to read document data"):
        super().__init__(message=message)


class DocumentCreateError(DocumentRepositoryError):
    """Raised when a create operation fails."""

    def __init__(self, message: str = "Failed to create document"):
        super().__init__(message=message)


class DocumentUpdateError(DocumentRepositoryError):
    """Raised when an update operation fails."""

    def __init__(self, message: str = "Failed to update document"):
        super().__init__(message=message)


class DocumentDeleteError(DocumentRepositoryError):
    """Raised when a delete operation fails."""

    def __init__(self, message: str = "Failed to delete document"):
        super().__init__(message=message)


class ChunkInsertError(DocumentRepositoryError):
    """Raised when parent chunk bulk insert fails."""

    def __init__(self, message: str = "Failed to insert parent chunks"):
        super().__init__(message=message)


class DeadlockRetryExceeded(ChunkInsertError):
    """Raised when deadlock retries are exhausted."""

    def __init__(self, message: str = "Deadlock retries exhausted during chunk insert"):
        super().__init__(message=message)
