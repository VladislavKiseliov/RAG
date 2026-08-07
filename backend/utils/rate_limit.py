from fastapi import HTTPException, status
from pyrate_limiter import Duration, Limiter, Rate

from backend.dependencies import CurrentUserDep

# Сообщения в AI-чат запускают дорогой RAG-пайплайн (retrieval + LLM) - лимит
# per-пользователь (JWT-идентичность), не per-IP - см. websocket_router.py для
# того же паттерна (in-memory pyrate_limiter, без Redis/FastAPILimiter.init).
_CHAT_MESSAGE_RATE = Rate(10, Duration.SECOND * 60)
_chat_message_limiter = Limiter(_CHAT_MESSAGE_RATE)


def enforce_chat_rate_limit(current_user: CurrentUserDep) -> None:
    if not _chat_message_limiter.try_acquire(str(current_user.id), blocking=False):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages. Slow down.",
        )
