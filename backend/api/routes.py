"""Маршруты API для авторизации, чата и прокси ingestion."""
import uuid

# --- ЭНДПОИНТЫ ---

from typing import Any, Dict

from fastapi import APIRouter, Depends
from starlette import status

from backend.services.chat_service import ChatService
from backend.services.ConversationService import ConversationService
from backend.dependencies import get_auth_service, get_current_user_from_token, get_chat_service, get_conversation_service
from backend.api.schemas import LoginRequest, RegisterRequest, RefreshRequest, LogoutRequest, Message, ChatUpdate
from backend.services.auth_service import AuthService
from backend.models.database_models import Users

# Создаем роутер для всех эндпоинтов
router = APIRouter()


# --- АВТОРИЗАЦИЯ ---

@router.post("/auth/register", status_code=201, response_model=Dict[str, Any])
async def register(
        user_data: RegisterRequest,
        service: AuthService = Depends(get_auth_service)
):
    """
    **Регистрация нового пользователя.**

    - Проверяет уникальность логина.
    - Хеширует пароль.
    - Создает запись в БД.
    """
    return await service.register(
        username=user_data.username,
        password=user_data.password
    )


@router.post("/auth/login", response_model=Dict[str, Any])
async def login(
        user_data: LoginRequest,
        service: AuthService = Depends(get_auth_service)
) -> Dict[str, Any]:
    """
    **Вход в систему.**

    - Проверяет учетные данные.
    - Выдает пару: Access Token и Refresh Token.
    """
    return await service.login(user_data.username, user_data.password)


@router.post("/auth/refresh", response_model=Dict[str, Any])
async def refresh_token(
        request: RefreshRequest,
        service: AuthService = Depends(get_auth_service)
) -> Dict[str, Any]:
    """
    **Обновление Access Token.**

    - Принимает старый Refresh Token.
    - Выдает новую пару токенов (Rotation).
    - Старый токен аннулируется.
    """
    return await service.refresh(request.refresh_token)


@router.post("/auth/logout", response_model=Dict[str, Any])
async def logout(
        request: LogoutRequest,
        service: AuthService = Depends(get_auth_service)
) -> Dict[str, Any]:
    """
    **Выход из системы.**

    - **refresh_token**: токен, который нужно отозвать.
    - **revoke_all**: если true, закроет все активные сессии пользователя.
    """
    return await service.logout(
        refresh_token=request.refresh_token,
        revoke_all=request.revoke_all
    )

# --- ЧАТЫ ---
@router.post(
    "/api/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый пустой чат",
    description="Инициализирует новую сессию диалога. Возвращает UUID созданного чата."
)
async def create_conversation(
        current_user: str = Depends(get_current_user_from_token),
        service: ChatService = Depends(get_chat_service)
):
    """
    Создает пустой диалог в базе данных.

    Args:
        current_user: ID пользователя (строка), извлеченный из токена.
        service: Сервис для управления логикой чатов.
    """
    chat_id = await service.create_chat(current_user.id)
    return {"conversation_id": chat_id}

@router.get(
    "/api/conversations",
    summary="Получить список чатов",
    description="Возвращает массив всех диалогов текущего пользователя для боковой панели."
)
async def get_all_conversations(
        current_user: Users = Depends(get_current_user_from_token),
        service: ChatService = Depends(get_chat_service)
):
    """
    Формирует список превью чатов (ID и заголовки).

    Returns:
        dict: Объект со списком 'conversations'.
    """
    conversations = await service.get_all_previews(current_user.id)
    return {"conversations": conversations}

@router.patch(
    "/api/chats/{chat_id}/rename",
    summary="Переименовать чат",
    description="Обновляет заголовок (title) конкретного чата. Требуется владение этим чатом."
)
async def update_title_chat(
        chat_id: uuid.UUID,
        title_data: ChatUpdate,
        current_user: Users = Depends(get_current_user_from_token),
        service: ChatService = Depends(get_chat_service)
):
    """
    Изменяет название существующего чата.

    Args:
        chat_id: UUID чата (автоматически валидируется FastAPI).
        title_data: Pydantic-модель с новым заголовком.
    """
    await service.rename_chat(user_id=current_user.id, chat_id = chat_id, new_title= title_data.title)
    return {
        "status": "success",
        "message": "Chat title updated successfully"
    }

@router.delete(
    "/api/chats/{chat_id}",
    summary="Удалить чат",
    description="Безвозвратно удаляет чат и всю историю сообщений из базы данных."
)
async def delete_chat(
        chat_id: uuid.UUID,
        current_user: str = Depends(get_current_user_from_token),
        service: ChatService = Depends(get_chat_service)
):
    """
    Удаляет запись чата, если она принадлежит текущему пользователю.
    """
    await service.delete_chat(current_user.id, chat_id)
    return {"status": "success", "message": "Чат успешно удален"}


# --- ИСТОРИЯ СООБЩЕНИЙ ---

@router.get("/api/conversations/{conversation_id}", summary="Получить историю сообщений")
async def get_conversation_history(
    conversation_id: uuid.UUID, # Авто-валидация UUID
    current_user: str = Depends(get_current_user_from_token),
    service: ChatService = Depends(get_chat_service)
):
    """Возвращает историю сообщений для конкретного диалога."""
    history = await service.get_history(conversation_id)
    return {"history": history}


@router.post(
    "/api/conversations/{conversation_id}/messages",
    summary="Отправить сообщение"
)
async def chat_endpoint(
    conversation_id: uuid.UUID,
    message: Message,
    current_user: str = Depends(get_current_user_from_token),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    Обрабатывает новое сообщение:
    1. Сохраняет ввод пользователя.
    2. Получает ответ от RAG.
    3. Сохраняет ответ ассистента.
    """
    result = await service.process_message(
        user_id=current_user,
        chat_id=conversation_id,
        content=message.user_message
    )
    return result




