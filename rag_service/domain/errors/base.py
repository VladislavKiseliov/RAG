from starlette import status


class AppError(Exception):
    """Base application exception with HTTP status metadata."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UploadValidationError(AppError):
    """Raised when upload-link request metadata is invalid."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST)


class WebhookAuthorizationError(AppError):
    """Raised when webhook authorization token is invalid or missing."""

    def __init__(self, message: str = "Invalid notification token"):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class InvalidDocumentIdError(AppError):
    """Raised when document id has invalid UUID format."""

    def __init__(self, message: str = "Invalid doc_id format"):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST)


class ChapterNotFound(AppError):
    """Raised when the requested chapter index is out of range for a document."""

    def __init__(self, doc_id: str, chapter_idx: int):
        super().__init__(
            message=f"Chapter {chapter_idx} not found for document '{doc_id}'",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidIngestionStateError(AppError):
    """Raised when a document state transition is not allowed."""

    def __init__(self, current: str, attempted: str):
        super().__init__(
            message=f"Cannot transition from '{current}' to '{attempted}'",
            status_code=status.HTTP_409_CONFLICT,
        )


class DuplicateFileError(AppError):
    """Raised when a file with the same hash already exists in the system."""

    def __init__(self, file_hash: str):
        self.file_hash = file_hash
        super().__init__(
            message=f"File with hash '{file_hash}' already exists",
            status_code=status.HTTP_409_CONFLICT,
        )


class DuplicateFilenameError(AppError):
    """Raised when an active document with the same filename already exists."""

    def __init__(self, filename: str):
        super().__init__(
            message=f"Документ '{filename}' уже существует",
            status_code=status.HTTP_409_CONFLICT,
        )