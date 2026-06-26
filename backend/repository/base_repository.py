from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base repository class. Session is injected externally; transactions are managed by the service layer."""

    def __init__(self, session: AsyncSession):
        self._session = session