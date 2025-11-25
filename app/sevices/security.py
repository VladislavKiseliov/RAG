# security.py
import jwt
import datetime
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from pwdlib import PasswordHash

load_dotenv()
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

# OAuth2PasswordBearer извлекает токен из заголовка "Authorization: Bearer <token>"
# Параметр tokenUrl указывает маршрут, по которому клиенты смогут получить токен
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class Auth:
    """
    Класс авторизации пользователя
    """
    _instance = None  # Приватная переменная для хранения единственного экземпляра

    def __new__(cls, *args, **kwargs):
        # 1. Проверяем, существует ли уже экземпляр
        if cls._instance is None:
            # 2. Если нет, создаем его через базовый класс object
            cls._instance = super(Auth, cls).__new__(cls)
            print("Создан новый экземпляр!")
        # 3. Возвращаем существующий (или только что созданный) экземпляр
        return cls._instance

    def __init__(self,secret_key:str,algorithm:str,token_expire:int,settings=None):
        if not hasattr(self, 'initialized'):
            self.settings = settings
            self.SECRET_KEY = secret_key
            self.ALGORITHM = algorithm
            self.ACCESS_TOKEN_EXPIRE_MINUTES = token_expire
            self.password_hash = PasswordHash.recommended()
            self.initialized = True

    def _create_jwt_token(self,data: Dict):
        """
        Функция для создания JWT токена. Мы копируем входные данные, добавляем время истечения и кодируем токен.
        """
        to_encode = data.copy()  # Копируем данные, чтобы не изменить исходный словарь
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)  # Задаем время истечения токена
        to_encode.update({"exp": expire})  # Добавляем время истечения в данные токена
        return jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)  # Кодируем токен с использованием секретного ключа и алгоритма

    # Функция для получения пользователя из токена
    def get_user_from_token(self,token: str = Depends(oauth2_scheme))->str:
        """
        Функция для извлечения информации о пользователе из токена. Проверяем токен и извлекаем утверждение о пользователе.
        """
        try:
            print(f" Зашли в функция {token}")
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])  # Декодируем токен с помощью секретного ключа
            return payload.get("sub")  # Возвращаем утверждение о пользователе (subject) из полезной нагрузки
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")  # Обработка ошибки истечения срока действия токена
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")  # Обработка ошибки недействительного токена

    def _verify_password(self,plain_password, hashed_password):
        return self.password_hash.verify(plain_password, hashed_password)

    def get_password_hash(self,password):
        return self.password_hash.hash(password)

    def authenticate_user(self,user_id: str, password: str,password_db:str):
        password_db_hash = self.get_password_hash(password_db)
        if not self._verify_password(password, password_db_hash):
            return False
        jwt_token = self._create_jwt_token({"sub": user_id})
        return jwt_token


if __name__ == '__main__':
    SECRET_KEY = os.getenv(
        "SECRET_KEY")  # В реальной практике генерируйте ключ, например, с помощью 'openssl rand -hex 32', и храните его в безопасности
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Время жизни токена

    Auth(SECRET_KEY,ALGORITHM,ACCESS_TOKEN_EXPIRE_MINUTES)











