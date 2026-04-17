from dataclasses import dataclass

from backend.services.auth_handler import AuthHandler
from backend.settings import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession


@dataclass(frozen=True)
class BackendContainer:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession] # Добавляем фабрику
    auth_handler: AuthHandler

def build_backend_infrastructure() -> BackendContainer:
    # 1. Настройки безопасности (Singleton)
    auth_handler = AuthHandler(
        secret_key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
        expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    # 1. Движок
    engine = create_async_engine(settings.DATABASE_URL, future=True, echo=True)

    # 2. Фабрика (создаем один раз!)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False
    )

    return BackendContainer(
        engine=engine,
        session_factory=session_factory,
        auth_handler=auth_handler
    )
