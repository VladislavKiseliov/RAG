"""Маршруты API для авторизации, чата и прокси ingestion."""
# --- ЭНДПОИНТЫ ---
import os
import secrets
from datetime import datetime, timedelta, timezone
import json
from urllib import request as urllib_request
from urllib import error as urllib_error
import uuid
import uuid6
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


try:
    from ServiceDataBase.app.implementations.PostgresAlchemy import PostgresAlchemy
    from ServiceDataBase.app.implementations.Qdrant import QdrantManager
    from ServiceDataBase.app.models.database_models import Chats
except ModuleNotFoundError as exc:
    if exc.name != "ServiceDataBase":
        raise
    from backend.ServiceDataBase.app.implementations.PostgresAlchemy import PostgresAlchemy
    from backend.ServiceDataBase.app.implementations.Qdrant import QdrantManager
    from backend.ServiceDataBase.app.models.database_models import Chats

try:
    from app.config import INGESTION_SERVICE_URL, QDRANT_URL, COLLECTION_NAME
    from app.core.initialization import (
        initialization_llm,
        initialization_embenddings_model,
        initialization_prompt_template,
    )
    from app.core.rag_pipeline import setup_rag_chain, answer_question
    from app.sevices.security import Auth, oauth2_scheme
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
    from backend.app.config import INGESTION_SERVICE_URL, QDRANT_URL, COLLECTION_NAME
    from backend.app.core.initialization import (
        initialization_llm,
        initialization_embenddings_model,
        initialization_prompt_template,
    )
    from backend.app.core.rag_pipeline import setup_rag_chain, answer_question
    from backend.app.sevices.security import Auth, oauth2_scheme


# Создаем роутер для всех эндпоинтов
router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")  # Секретный ключ для подписи токена.
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))  # Время жизни токена.
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)
postgres = PostgresAlchemy()
auth = Auth(SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES)
_qa_chain = None


def get_qa_chain():
    global _qa_chain
    if _qa_chain is not None:
        return _qa_chain

    if not QDRANT_URL:
        raise HTTPException(status_code=500, detail="QDRANT_URL is not set")

    embeddings = initialization_embenddings_model()
    llm = initialization_llm()
    prompt_template = initialization_prompt_template()

    qdrant_manager = QdrantManager(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        qdrant_url=QDRANT_URL,
    )
    retriever = qdrant_manager.get_retriever()

    _qa_chain = setup_rag_chain(llm=llm, retriever=retriever, prompt_template=prompt_template)
    return _qa_chain

def parse_uuid(value: str, field_name: str) -> uuid.UUID:
    # Единая проверка UUID и возврат 400 при ошибке.
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

def get_db():
    # Зависимость FastAPI, возвращающая сессию БД.
    db = SessionLocal()  # Сессия БД.
    try:
        yield db       # Передаем наружу.
    finally:
        db.close()    # Закрываем сессию.


# --- Модели (Pydantic) ---


# Данные для логина.
class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    user_message: str

class ChatUpdate(BaseModel):
    title: str


class IngestRequest(BaseModel):
    path: str
    collection: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
    revoke_all: bool = False


# # Пример дополнительных моделей.

# class WalletOperation(BaseModel):
#     operation_type: str = Field(pattern="^(DEPOSIT|WITHDRAW)$")
#     amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
# Ответ по кошельку (пример).
# class WalletResponse(BaseModel):
#     uuid: UUID
#     balance: Decimal



# --- АВТОРИЗАЦИЯ ---


# Аутентификация и выдача JWT; при первом логине создаем пользователя.
@router.post("/auth/login")
def login(user_data: LoginRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
     Этот маршрут проверяет учетные данные пользователя и возвращает JWT токен, если данные правильные.
    """

    print(f"Пользователь {user_data.username} и пароль {user_data.password}")
    try:
        # Получить пользователя из БД.
        user = postgres.get_user_by_login(db, user_data.username)
        print(f"Пользователь {user_data.username} и пароль {user_data.password}")

        # Пытаемся получить токен
        if not user:
            # Если пользователя нет, создаем нового
            hashed_password = auth.get_password_hash(user_data.password)
            postgres.add_new_user(db, user_data.username, hashed_password)
            user = postgres.get_user_by_login(db, user_data.username)

        # Аутентифицируем пользователя
        jwt_token = auth.authenticate_user(str(user.id), user.password, user_data.password)
        print(jwt_token)
        if not jwt_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(jwt_token)
        print(f"ID из токена = {auth.get_user_from_token(jwt_token)}")
        refresh_token = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        postgres.add_refresh_token(db, user.id, refresh_token, refresh_expires)

        return {
            "message": "Login successful",
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except Exception as e:
        print(f"Login error: {e}")
        # Возвращаем HTTP-код 401 Unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# Обновить access token на основе refresh token.
@router.post("/auth/refresh")
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    stored = postgres.get_refresh_token(db, request.refresh_token)
    if not stored or stored.revoked:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user_id = str(stored.user_id)
    new_access = auth._create_jwt_token({"sub": user_id})

    postgres.revoke_refresh_token(db, request.refresh_token)
    new_refresh = secrets.token_urlsafe(48)
    refresh_expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    postgres.add_refresh_token(db, stored.user_id, new_refresh, refresh_expires)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


# Отозвать refresh токен (или все токены пользователя).
@router.post("/auth/logout")
def logout(request: LogoutRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    stored = postgres.get_refresh_token(db, request.refresh_token)
    if not stored:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if request.revoke_all:
        revoked = postgres.revoke_all_refresh_tokens(db, stored.user_id)
        return {"status": "success", "revoked": revoked}

    if not postgres.revoke_refresh_token(db, request.refresh_token):
        raise HTTPException(status_code=404, detail="Refresh token not found")

    return {"status": "success"}


# Прокси в Document_Ingestion_Service для постановки задач на индексацию.
@router.post("/api/ingest")
def ingest_documents(
    request: IngestRequest,
    current_user: str = Depends(auth.get_user_from_token),
) -> Dict[str, Any]:
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not INGESTION_SERVICE_URL:
        raise HTTPException(status_code=500, detail="INGESTION_SERVICE_URL is not set")

    payload = {
        "path": request.path,
        "collection": request.collection,
        "metadata": request.metadata,
    }
    url = f"{INGESTION_SERVICE_URL.rstrip('/')}/ingest"
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib_request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
        return json.loads(body)
    except urllib_error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise HTTPException(
            status_code=e.code,
            detail=error_body or "Ingestion request failed",
        )
    except urllib_error.URLError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ingestion service unreachable: {e.reason}",
        )

# # Защищённый маршрут, который возвращает информацию о пользователе,
# # если токен в запросе действителен.
# @app.get("/about_me")
# async def about_me(current_user: str = Depends(get_user_from_token)):
#     """
#     Этот маршрут защищен и требует токен. Если токен действителен, мы возвращаем информацию о пользователе.
#     """
#     user = get_user(current_user)
#     if user:
#         return user
#     # Если пользователь не найден, возвращаем ошибку
#     return {"error": "User not found"}


# --- ЧАТЫ ---
# Создать пустой чат для авторизованного пользователя.
@router.post("/api/conversations")
def create_conversation(current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Создает новый пустой диалог и возвращает его ID, используя константный user_id."""
    # user_id = current_user

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    chat_id = uuid6.uuid7()
    result = postgres.add_new_chat(db, chat_id, parse_uuid(current_user, 'user_id'), 'Новый чат')
    if not result:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    print(f"Создан новый диалог: {chat_id} для user: {current_user}")
    return {"conversation_id": str(chat_id)}

# Вернуть список чатов для авторизованного пользователя.
@router.get("/api/conversations")
def get_all_conversations(current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Возвращает список всех ID диалогов для константного user_id."""
    previews = []

    # Используем константный user_id для получения чатов
    chats = postgres.get_all_chats(db, parse_uuid(current_user, 'user_id'))
    for chat in chats:
        first_message = chat.get("title", "Новый чат")
        previews.append({"id": chat["chat_id"], "title": first_message})

    return {"conversations": sorted(previews, key=lambda x: x['id'], reverse=True)}


# --- ИСТОРИЯ СООБЩЕНИЙ ---
# Вернуть историю сообщений для выбранного чата.
@router.get("/api/conversations/{conversation_id}")
def get_conversation_history(conversation_id: str, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Возвращает историю сообщений для конкретного диалога (conversation_id)."""
    # Здесь мы используем conversation_id, переданный в URL, для получения истории
    # Если вы хотите убедиться, что этот чат принадлежит user_id,
    # вам нужно изменить postgres.get_chat_messages так, чтобы он также принимал user_id.

    # Пытаемся загрузить историю из БД. Для пустых чатов возвращаем пустой список, а не 404.
    try:
        chat_uuid = parse_uuid(conversation_id, 'conversation_id')
        user_uuid = parse_uuid(current_user, 'user_id')

        chat = (
            db.query(Chats)
            .filter(Chats.chat_id == chat_uuid, Chats.user_id == user_uuid)
            .first()
        )
        if not chat:
            raise HTTPException(status_code=404, detail=f"Диалог {conversation_id} не найден")

        result = postgres.get_chat_messages(db, chat_uuid)
        return {"history": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Ошибка БД или диалог {conversation_id} не найден: {str(e)}")
# ---
# --- ОБНОВЛЕННЫЙ ЭНДПОИНТ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ---
@router.post("/api/conversations/{conversation_id}/messages")
# Сохраняем сообщения пользователя и ассистента вокруг генерации ответа.
def chat_endpoint(conversation_id: str, message: Message, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Обрабатывает сообщение в рамках конкретного диалога (conversation_id)."""

    # # Проверка существования диалога
    # if conversation_id not in conversations:
    #     # В реальной ситуации здесь нужно проверить БД
    #     raise HTTPException(status_code=404, detail="Диалог не найден. Начните новый чат.")

    user_message = message.user_message

    # 1. Сохраняем сообщение пользователя в локальный словарь
    # user_msg_entry = {"role": "user", "content": user_message}
    # conversations[conversation_id].append(user_msg_entry)

    # 2. Сохраняем сообщение пользователя в БД
    # Используем динамический conversation_id
    postgres.add_new_message(db, parse_uuid(conversation_id, 'conversation_id'), "user", user_message)

    # 3. Получаем ответ от RAG-системы
    qa_chain = get_qa_chain()
    if not qa_chain:
        raise HTTPException(status_code=500, detail="RAG chain is not initialized")
    response_text = answer_question(user_message, qa_chain)

    # 4. Сохраняем ответ ассистента в локальный словарь
    # assistant_msg_entry = {"role": "assistant", "content": response_text}
    # conversations[conversation_id].append(assistant_msg_entry)

    # 5. Сохраняем ответ ассистента в БД
    # Используем динамический conversation_id
    postgres.add_new_message(db, parse_uuid(conversation_id, 'conversation_id'), "assistant", response_text)

    return {"response": response_text}
# ---
# ---

# Эндпоинт управлением чатом
# Обновить заголовок чата для авторизованного пользователя.
@router.patch("/api/chats/{chat_id}/rename")
def update_title_chat(chat_id: str, title_data: ChatUpdate, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    print(f"Updating title for chat_id: {chat_id}")
    print(f"New title: {title_data.title}")
    result = postgres.update_chat_title(
        db,
        parse_uuid(chat_id, 'chat_id'),
        parse_uuid(current_user, 'user_id'),
        title_data.title,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return {
        "status": "success",
        "message": "Chat title updated successfully"
    }


# Удалить чат и его сообщения для авторизованного пользователя.
@router.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    result = postgres.delete_chat(
        db,
        parse_uuid(chat_id, 'chat_id'),
        parse_uuid(current_user, 'user_id'),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Chat not found or unauthorized")
        
    return {
        "status": "success",
        "message": "Chat deleted successfully"
    }

