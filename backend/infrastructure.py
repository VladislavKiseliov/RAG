from dataclasses import dataclass

from backend.services.auth_handler import AuthHandler
from backend.services.ai.llm_client import LLMClient
from backend.services.messenger.websocket_manager import WebSocketManager
from backend.settings import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession


@dataclass(frozen=True)
class BackendContainer:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    auth_handler: AuthHandler
    llm_client: LLMClient
    socket_manager:WebSocketManager


def build_backend_infrastructure() -> BackendContainer:
    auth_handler = AuthHandler(
        secret_key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
        expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)

    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False
    )

    llm_client = LLMClient(service_url=settings.LLM_SERVICE_URL)
    socket_manager = WebSocketManager()

    return BackendContainer(
        engine=engine,
        session_factory=session_factory,
        auth_handler=auth_handler,
        llm_client=llm_client,
        socket_manager= socket_manager
    )
