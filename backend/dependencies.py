from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer

from backend.models.database_models import Users
from backend.services.auth_service import AuthService
from backend.services.chat_service import ChatService
from backend.services.user_service import UserService
from backend.infrastructure import BackendContainer


def get_container(request: Request) -> BackendContainer:
    return request.app.state.container


def get_auth_service(container: BackendContainer = Depends(get_container)) -> AuthService:
    return AuthService(session_factory=container.session_factory, auth_handler=container.auth_handler)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user_from_token(
    token: str = Depends(oauth2_scheme),
    service: AuthService = Depends(get_auth_service)
) -> Users:
    return await service.get_user_from_token(token)


def get_chat_service(container: BackendContainer = Depends(get_container)) -> ChatService:
    return ChatService(session_factory=container.session_factory)


def get_user_service(container: BackendContainer = Depends(get_container)) -> UserService:
    return UserService(session_factory=container.session_factory)