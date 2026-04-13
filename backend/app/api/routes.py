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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


import sys
import os

try:
    from backend.app.api.shemas import LoginRequest, RefreshRequest, LogoutRequest, IngestRequest, Message, ChatUpdate
    from backend.app.sevices.scripts import get_db, RAG_SERVICE_URL, parse_uuid, _call_rag_service
except ModuleNotFoundError:
    from backend.app.api.shemas import LoginRequest, RefreshRequest, LogoutRequest, IngestRequest, Message, ChatUpdate
    from backend.app.sevices.scripts import get_db, RAG_SERVICE_URL, parse_uuid, _call_rag_service

# Получаем путь к директории backend
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, backend_dir)

from backend.ServiceDataBase.app.implementations.PostgresAlchemy import PostgresAlchemy
# from ServiceDataBase.app.implementations.Qdrant import QdrantManager
from backend.ServiceDataBase.app.models.database_models import Chats

from backend.app.sevices.security import Auth, oauth2_scheme


# Создаем роутер для всех эндпоинтов
router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")  # Секретный ключ для подписи токена.
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # Время жизни токена.
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

engine = create_engine(DATABASE_URL, echo=True, connect_args={"options": "-c search_path=users_shema"})
SessionLocal = sessionmaker(bind=engine)
postgres = PostgresAlchemy()
auth = Auth(SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES)


def _ensure_admin_flags_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS users_shema.admin_user_flags (
              user_id uuid PRIMARY KEY REFERENCES users_shema.users(id) ON DELETE CASCADE,
              is_blocked boolean NOT NULL DEFAULT false,
              updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    db.commit()


def _is_user_blocked(db: Session, user_id: str) -> bool:
    _ensure_admin_flags_table(db)
    row = db.execute(
        text("SELECT is_blocked FROM users_shema.admin_user_flags WHERE user_id = CAST(:user_id AS uuid)"),
        {"user_id": user_id},
    ).first()
    return bool(row[0]) if row else False



# --- АВТОРИЗАЦИЯ ---

# Аутентификация и выдача JWT; при первом логине создаем пользователя.
@router.post("/auth/login")
def login(user_data: LoginRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
     Этот маршрут проверяет учетные данные пользователя и возвращает JWT токен, если данные правильные.
    """
    try:
        # Получить пользователя из БД.
        user = postgres.get_user_by_login(db, user_data.username)

        # Пытаемся получить токен
        if not user:
            # Если пользователя нет, создаем нового
            hashed_password = auth.get_password_hash(user_data.password)
            postgres.add_new_user(db, user_data.username, hashed_password)
            user = postgres.get_user_by_login(db, user_data.username)

        # Аутентифицируем пользователя
        if _is_user_blocked(db, str(user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is blocked",
            )

        jwt_token = auth.authenticate_user(str(user.id), user.password, user_data.password)
        if not jwt_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

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
    if _is_user_blocked(db, user_id):
        raise HTTPException(status_code=401, detail="User is blocked")

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
# @router.post("/api/ingest")
# def ingest_documents(
#     request: IngestRequest,
#     current_user: str = Depends(auth.get_user_from_token),
# ) -> Dict[str, Any]:
#     if not current_user:
#         raise HTTPException(status_code=401, detail="Unauthorized")
#     if not RAG_SERVICE_URL:
#         raise HTTPException(status_code=500, detail="RAG_SERVICE_URL is not set")
#
#     payload = {
#         "path": request.path,
#         "collection": request.collection,
#         "metadata": request.metadata,
#     }
#     url = f"{RAG_SERVICE_URL.rstrip('/')}/ingest"
#     data = json.dumps(payload).encode("utf-8")
#     req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})
#
#     try:
#         with urllib_request.urlopen(req, timeout=30) as response:
#             body = response.read().decode("utf-8")
#         return json.loads(body)
#     except urllib_error.HTTPError as e:
#         error_body = e.read().decode("utf-8") if e.fp else ""
#         raise HTTPException(
#             status_code=e.code,
#             detail=error_body or "Ingestion request failed",
#         )
#     except urllib_error.URLError as e:
#         raise HTTPException(
#             status_code=502,
#             detail=f"Ingestion service unreachable: {e.reason}",
#         )

# --- ЧАТЫ ---
# Создать пустой чат для авторизованного пользователя.
@router.post("/api/conversations")
def create_conversation(current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Создает новый пустой диалог и возвращает его ID, используя константный user_id."""

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
        # chat = postgres.get_chat_messages(db, chat_uuid, user_uuid)
        # if not chat:
        #     raise HTTPException(status_code=404, detail=f"Диалог {conversation_id} не найден")

        result = postgres.get_chat_messages(db, chat_uuid,user_uuid)
        return {"history": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Ошибка БД или диалог {conversation_id} не найден: {str(e)}")
# ---
# --- ОБНОВЛЕННЫЙ ЭНДПОИНТ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ---
@router.post("/api/conversations/{conversation_id}/messages")
def chat_endpoint(
        conversation_id: str,
        message: Message,
        current_user: str = Depends(auth.get_user_from_token),
        db: Session = Depends(get_db)
):
    """
    Обрабатывает новое сообщение пользователя в рамках диалога.

    Сохраняет сообщение пользователя → получает ответ от rag_service → сохраняет ответ ассистента.
    Возвращает сгенерированный ответ.
    """
    user_message = message.user_message

    try:
        # Парсим UUID для безопасности
        conv_uuid = parse_uuid(conversation_id, "conversation_id")
        user_uuid = parse_uuid(current_user, "user_id")
        print(1)
        # # Проверка существования диалога
        # if not postgres.does_conversation_exist(db, chat_id=conv_uuid, user_id=user_uuid):
        #     raise HTTPException(status_code=404, detail="Диалог не найден. Начните новый чат.")

        # Сохраняем сообщение пользователя в БД
        postgres.add_new_message(db, conv_uuid, role="user", content=user_message)

        # Получаем ответ от rag_service
        rag_result = _call_rag_service(user_message)
        assistant_response = rag_result["answer"]
        sources = rag_result["sources"]

        # Сохраняем ответ ассистента в БД
        postgres.add_new_message(db, conv_uuid, role="assistant", content=assistant_response)

        # Возвращаем ответ клиенту
        return {"response": assistant_response, "sources": sources}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Некорректный формат данных: {str(e)}")
    except Exception as e:
        print(e)
        # logger.error(f"Ошибка в диалоге {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")



# Эндпоинт управлением чатом
# Обновить заголовок чата для авторизованного пользователя.
@router.patch("/api/chats/{chat_id}/rename")
def update_title_chat(chat_id: str, title_data: ChatUpdate, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
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
    chat_uuid = parse_uuid(chat_id, 'chat_id')
    user_uuid = parse_uuid(current_user, 'user_id')

    # Пытаемся удалить. Метод в postgres должен возвращать True/False
    deleted = postgres.delete_chat(db, chat_id=chat_uuid, user_id=user_uuid)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Не удалось удалить чат. Возможно, он уже удален или доступ запрещен"
        )

    return {"status": "success", "message": "Чат успешно удален"}



