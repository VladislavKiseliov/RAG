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
