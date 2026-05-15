from fastapi import status


class LLMServiceError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# --- Network errors ---

class NetworkError(LLMServiceError):
    def __init__(self, message: str, status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE):
        super().__init__(message, status_code)


class RagUnavailableError(NetworkError):
    def __init__(self, message: str = "RAG service unavailable"):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE)


class RagResponseError(NetworkError):
    def __init__(self, message: str = "RAG service returned an error"):
        super().__init__(message, status.HTTP_502_BAD_GATEWAY)


# --- Processing errors ---

class ProcessingError(LLMServiceError):
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(message, status_code)


class RetrievalError(ProcessingError):
    def __init__(self, message: str = "Failed to process retrieval response"):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerationError(ProcessingError):
    def __init__(self, message: str = "Failed to generate answer"):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR)