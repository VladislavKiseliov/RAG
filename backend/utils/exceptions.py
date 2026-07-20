from starlette import status


class AppError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidCredentialsError(AppError):
    def __init__(self, message: str = "Incorrect username or password"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class UserAlreadyExistsError(AppError):
    def __init__(self, message: str = "User with this login already exists"):
        super().__init__(message, status.HTTP_409_CONFLICT)


class UserNotFoundError(AppError):
    def __init__(self, message: str = "User does not exist"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class SelfActionForbiddenError(AppError):
    def __init__(self, message: str = "Cannot perform this action on your own account"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class LastAdminError(AppError):
    def __init__(self, message: str = "Cannot remove the last remaining admin"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Invalid or missing token"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class AccessTokenExpiredError(AuthenticationError):
    def __init__(self, message: str = "Access token has expired"):
        super().__init__(message)


class RefreshTokenError(AppError):
    def __init__(self, message: str = "Invalid refresh token"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class RefreshTokenExpiredError(RefreshTokenError):
    def __init__(self, message: str = "Refresh token has expired"):
        super().__init__(message)


class TokenRevokedError(RefreshTokenError):
    def __init__(self, message: str = "Refresh token has been revoked"):
        super().__init__(message)


class AuthDatabaseError(AppError):
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR)



class TokenExpiredError(AppError):
    def __init__(self, message: str = "Токен истек"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ChatNotFoundError(AppError):
    def __init__(self, message: str = "Chat not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class NoteNotFoundError(AppError):
    def __init__(self, message: str = "Note not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class LLMUnavailableError(AppError):
    def __init__(self, message: str = "LLM service is unavailable"):
        super().__init__(message, status.HTTP_502_BAD_GATEWAY)


class LLMError(AppError):
    def __init__(self, message: str = "LLM service returned an error"):
        super().__init__(message, status.HTTP_502_BAD_GATEWAY)
