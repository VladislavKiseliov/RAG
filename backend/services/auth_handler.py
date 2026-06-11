# auth_handler.py
from datetime import datetime,timezone,timedelta

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from typing import Optional
from pwdlib import PasswordHash

from backend.utils.exceptions import AccessTokenExpiredError, AuthenticationError


class AuthHandler:
    """Хеширование паролей и генерация JWT. Инжектируется через BackendContainer."""

    def __init__(self, secret_key: str, algorithm: str, expire_minutes: int, refresh_expire_days: int):
        self.SECRET_KEY = secret_key
        self.ALGORITHM = algorithm
        self.EXPIRE_MINUTES = expire_minutes
        self.REFRESH_EXPIRE_DAYS = refresh_expire_days
        self.password_hash = PasswordHash.recommended()

    def create_access_token(self, user_id: str) -> str:
        """
        Создает JWT токен.
        В 'sub' (subject) записываем ID пользователя.
        """
        payload = {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) +
                   timedelta(minutes=self.EXPIRE_MINUTES),
            "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)

    def decode_token(self, token: str) -> Optional[str]:
        """
        Декодирует токен и возвращает user_id (sub).
        Если токен невалиден или просрочен — возвращает None.
        Логику 'raise HTTPException' мы вынесли в AuthService/Middleware.
        """
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except ExpiredSignatureError:
            # Вот тут мы кидаем наше кастомное исключение
            raise AccessTokenExpiredError()
        except InvalidTokenError:
            # Для всех остальных проблем с токеном (битый, чужой)
            raise AuthenticationError()

    def get_password_hash(self, password: str) -> str:
        """Генерация хеша пароля."""
        return self.password_hash.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверка соответствия пароля хешу."""
        return self.password_hash.verify(plain_password, hashed_password)

    def authenticate_user(self, user_id: str, hashed_password: str, provided_password: str) -> Optional[str]:
        """
        Комплексная проверка: если пароль верный — возвращает токен, иначе None.
        """
        if not self.verify_password(provided_password, hashed_password):
            return None
        return self.create_access_token(user_id)




























































