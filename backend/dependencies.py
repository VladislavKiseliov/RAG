from typing import Annotated

from fastapi import Request, Depends, Query, HTTPException
from fastapi.security import OAuth2PasswordBearer
from starlette.websockets import WebSocket

from backend.services.messenger.message_service import MessageService
from backend.services.auth_service import AuthService, CurrentUser
from backend.services.chat_service import ChatService
from backend.services.ai.conversation_service import ConversationService
from backend.services.user_service import UserService
from backend.services.messenger.messenger_service import MessengerService
from backend.infrastructure import BackendContainer
from backend.services.messenger.websocket_manager import WebSocketManager
from starlette.requests import HTTPConnection


def get_container(conn: HTTPConnection) -> BackendContainer:
    return conn.app.state.container

def get_auth_service(container: BackendContainer = Depends(get_container)) -> AuthService:
    return AuthService(session_factory=container.session_factory, auth_handler=container.auth_handler)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user_from_token(
    token: str = Depends(oauth2_scheme),
    service: AuthService = Depends(get_auth_service)
) -> CurrentUser:
    return await service.get_user_from_token(token)

async def get_current_from_token_user_ws(
    websocket: WebSocket,
    token: str = Query(...),
    auth_service: AuthService = Depends(get_auth_service)
) -> CurrentUser:
    return await auth_service.get_user_from_token(token)

async def require_admin_user(current_user: CurrentUser = Depends(get_current_user_from_token)) -> CurrentUser:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_chat_service(container: BackendContainer = Depends(get_container)) -> ChatService:
    return ChatService(session_factory=container.session_factory)

def get_conversation_service(container: BackendContainer = Depends(get_container)) -> ConversationService:
    return ConversationService(session_factory=container.session_factory, llm_client=container.llm_client)

def get_user_service(container: BackendContainer = Depends(get_container)) -> UserService:
    return UserService(session_factory=container.session_factory)

def get_websocket_manager(container: BackendContainer = Depends(get_container)) -> WebSocketManager:
    return container.socket_manager

def get_message_service(container: BackendContainer = Depends(get_container)) -> MessageService:
    return MessageService(session_factory=container.session_factory)

def get_messenger_service(container: BackendContainer = Depends(get_container)) -> MessengerService:
    return MessengerService(session_factory=container.session_factory)

ContainerDep = Annotated[BackendContainer, Depends(get_container)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user_from_token)]
CurrentUserWsDep = Annotated[CurrentUser, Depends(get_current_from_token_user_ws)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
MessengerServiceDep = Annotated[MessengerService, Depends(get_messenger_service)]
WebSocketManagerDep = Annotated[WebSocketManager, Depends(get_websocket_manager)]

