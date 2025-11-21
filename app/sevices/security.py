# security.py
import jwt
import datetime
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
from dotenv import load_dotenv
import os
load_dotenv()
# OAuth2PasswordBearer извлекает токен из заголовка "Authorization: Bearer <token>"
# Параметр tokenUrl указывает маршрут, по которому клиенты смогут получить токен
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = os.getenv("SECRET_KEY")  # В реальной практике генерируйте ключ, например, с помощью 'openssl rand -hex 32', и храните его в безопасности
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Время жизни токена

# Функция для создания JWT токена с заданным временем жизни
def create_jwt_token(data: Dict):
    """
    Функция для создания JWT токена. Мы копируем входные данные, добавляем время истечения и кодируем токен.
    """
    to_encode = data.copy()  # Копируем данные, чтобы не изменить исходный словарь
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)  # Задаем время истечения токена
    to_encode.update({"exp": expire})  # Добавляем время истечения в данные токена
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # Кодируем токен с использованием секретного ключа и алгоритма

# Функция для получения пользователя из токена
def get_user_from_token(token: str = Depends(oauth2_scheme)):
    """
    Функция для извлечения информации о пользователе из токена. Проверяем токен и извлекаем утверждение о пользователе.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # Декодируем токен с помощью секретного ключа
        return payload.get("sub")  # Возвращаем утверждение о пользователе (subject) из полезной нагрузки
    except jwt.ExpiredSignatureError:
        pass  # Обработка ошибки истечения срока действия токена
    except jwt.InvalidTokenError:
        pass  # Обработка ошибки недействительного токена

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

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password):
        return password_hash.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

    def authenticate_user(fake_db, username: str, password: str):
        user = get_user(fake_db, username)
        if not user:
            return False
        if not verify_password(password, user.hashed_password):
            return False
        return user


    async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except InvalidTokenError:
            raise credentials_exception
        user = get_user(fake_users_db, username=token_data.username)
        if user is None:
            raise credentials_exception
        return user

    async def get_current_active_user(
            current_user: Annotated[User, Depends(get_current_user)],
    ):
        if current_user.disabled:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    @app.post("/token")
    async def login_for_access_token(
            form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    ) -> Token:
        user = authenticate_user(fake_users_db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return Token(access_token=access_token, token_type="bearer")

    @app.get("/users/me/", response_model=User)
    async def read_users_me(
            current_user: Annotated[User, Depends(get_current_active_user)],
    ):
        return current_user

    @app.get("/users/me/items/")
    async def read_own_items(
            current_user: Annotated[User, Depends(get_current_active_user)],
    ):
        return [{"item_id": "Foo", "owner": current_user.username}]