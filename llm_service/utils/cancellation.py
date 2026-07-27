from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, Coroutine, TypeVar

from fastapi import HTTPException, Request

from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.cancellation")

T = TypeVar("T")


async def _watch_disconnect(request: Request) -> None:
    """Ждёт ASGI-событие http.disconnect.

    request.is_disconnected() тут не годится - стабильно возвращает False при наличии
    BaseHTTPMiddleware (баг Starlette с 0.21.0, у backend в проекте такой middleware есть -
    RequestLoggingMiddleware). Вызывать await request.receive() напрямую безопасно: к
    моменту выполнения обработчика FastAPI уже полностью прочитал тело запроса, второго
    сообщения от receive() не будет, кроме итогового http.disconnect при разрыве.
    """
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


def with_cancellation(handler: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
    """Оборачивает non-streaming ручку отменой генерации при обрыве клиента.

    Starlette сам не реагирует на дисконнект для обычного request-response (в отличие
    от StreamingResponse) - обработчик доработает до конца "в пустоту", даже если никто
    уже не читает ответ. Реальный риск: таймаут фронта короче времени генерации -> клиент
    ретраит -> на сервере одновременно доживают старый (уже никому не нужный) и новый
    запрос на один и тот же вопрос, удваивая нагрузку на LLM. Адаптировано из vLLM
    (@with_cancellation).

    Оборачиваемая функция должна принимать `http_request: Request` - FastAPI подставит
    его как обычную зависимость.
    """
    @functools.wraps(handler)
    async def wrapper(*args: Any, http_request: Request, **kwargs: Any) -> T:
        handler_task = asyncio.ensure_future(handler(*args, http_request=http_request, **kwargs))
        disconnect_task = asyncio.ensure_future(_watch_disconnect(http_request))
        try:
            done, _pending = await asyncio.wait(
                {handler_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED,
            )
            if handler_task in done:
                return handler_task.result()

            logger.warning("Client disconnected mid-request, cancelling in-flight LLM generation")
            handler_task.cancel()
            try:
                await handler_task
            except asyncio.CancelledError:
                pass
            raise HTTPException(status_code=499, detail="Client disconnected")
        finally:
            disconnect_task.cancel()

    return wrapper