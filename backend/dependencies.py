from typing import AsyncGenerator

from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.database_models import Users
from backend.services.auth_service import AuthService
from backend.services.chat_service import ChatService
from rag_service.application.document_orchestrator import DocumentUploadService
from backend.services.user_service import UserService
from backend.repository.repository import AuthRepository, ChatRepository, MessageRepository, UserRepository, \
    DocumentRepository
from backend.infrastructure import BackendContainer


def get_container(request: Request) -> BackendContainer:
    return request.app.state.container


# 1. Получаем сессию базы
async def get_session(container: BackendContainer = Depends(get_container)) -> AsyncGenerator[AsyncSession, None]:
    engine = container.engine
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        yield session

# 2. Собираем AuthService "на лету"
def get_auth_service(container: BackendContainer = Depends(get_container)) -> AuthService:

    # Собираем всё из контейнера
    repo = AuthRepository(container.session_factory)
    return AuthService(repo=repo, auth_handler=container.auth_handler)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user_from_token(
    token: str = Depends(oauth2_scheme),
    service: AuthService = Depends(get_auth_service)
) -> Users:
    """
    Эта функция — мост между HTTP и бизнес-логикой.
    """
    # Сервис сам проверит токен и найдет юзера в БД
    return await service.get_user_from_token(token)


def get_chat_service(container: BackendContainer = Depends(get_container)) -> ChatService:

    # Создаем репозитории, передавая им фабрику сессий из контейнера
    chat_repo = ChatRepository(container.session_factory)
    message_repo = MessageRepository(container.session_factory)

    # Собираем сервис
    return ChatService(chat_repo=chat_repo, message_repo=message_repo)


def get_user_service(container: BackendContainer = Depends(get_container)) -> UserService:
    user_repo = UserRepository(container.session_factory)
    return UserService(user_repo=user_repo)


def get_storage_service(container: BackendContainer = Depends(get_container),)->DocumentUploadService:


    return DocumentUploadService(document_service=DocumentRepository(container.session_factory),
                                 strage_repository=container.storage_repository
                                 )
