from fastapi import HTTPException, Request, status
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


def _client_ip(request: Request) -> str:
    # До аутентификации user_id ещё нет - лимитируем по IP. request.client.host
    # был бы IP nginx (единственный, кто напрямую коннектится к backend) -
    # берём X-Real-IP, который nginx.conf уже проставляет на весь server-блок.
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


# Логин - подбор пароля; регистрация - массовое создание фейковых аккаунтов.
# Регистрация лимитирована жёстче - легитимный пользователь регистрируется
# один раз, а не многократно, как логинится.
_LOGIN_RATE = Rate(10, Duration.SECOND * 60)
_login_limiter = Limiter(_LOGIN_RATE)

_REGISTER_RATE = Rate(5, Duration.SECOND * 60)
_register_limiter = Limiter(_REGISTER_RATE)


def enforce_login_rate_limit(request: Request) -> None:
    if not _login_limiter.try_acquire(_client_ip(request), blocking=False):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Slow down.",
        )


def enforce_register_rate_limit(request: Request) -> None:
    if not _register_limiter.try_acquire(_client_ip(request), blocking=False):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Slow down.",
        )
