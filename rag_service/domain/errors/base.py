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
