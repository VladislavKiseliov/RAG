import asyncio
import logging
from json.decoder import JSONDecodeError

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from backend.dependencies import WebSocketManagerDep, AuthServiceDep, MessageServiceDep
from backend.utils.exceptions import AuthenticationError, UserNotFoundError
from fastapi_limiter.depends import WebSocketRateLimiter
from pyrate_limiter import Duration, Limiter, Rate

logger = logging.getLogger(__name__)

WS_AUTH_TIMEOUT_S = 10


class WebsocketTooManyRequests(Exception):
    pass


async def websocket_callback(ws, pexpire):
    raise WebsocketTooManyRequests("Too many requests")


websocket_router = APIRouter(prefix="/websocket", tags=["websocket"])

@websocket_router.websocket("/ws/")
async def websocket_endpoint(
    socket_manager:WebSocketManagerDep,
    websocket: WebSocket,
    auth_service:AuthServiceDep,
    message_service:MessageServiceDep,
):
    await socket_manager.connect_socket(websocket=websocket)
    logger.info("Websocket connection is established")

    # Токен больше не идёт query-параметром URL (?token=...) - он утекал в открытом
    # виде в access-логи nginx на каждое подключение, в историю браузера и в логи
    # промежуточных прокси. Вместо этого первое сообщение после рукопожатия обязано
    # быть {"type": "auth", "token": "..."} - до него сокет ничего не обрабатывает.
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_S)
        if auth_message.get("type") != "auth" or not auth_message.get("token"):
            raise ValueError("Expected auth message with token")
        current_user = await auth_service.get_user_from_token(auth_message["token"])
    except (asyncio.TimeoutError, JSONDecodeError, ValueError, AuthenticationError, UserNotFoundError):
        await websocket.close(code=1008)
        return
    except WebSocketDisconnect:
        return

    ratelimit = WebSocketRateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 10)))

    # add user's socket connection {user_guid: {ws1, ws2}}
    user_guid_str = str(current_user.guid)

    # Регистрируем сеть
    await socket_manager.add_user_socket_connection(user_guid_str, websocket)

    chats_cache: dict[str, int] = {}

    try:
        while True:
            try:
                incoming_message = await websocket.receive_json()
                # 2. Проверяем рейт-лимит в изолированном try-блокe
                try:
                    await ratelimit(websocket)
                except HTTPException:
                    # Если спамит — шлем ошибку и прерываем ТЕКУЩУЮ итерацию (цикл живет!)
                    await socket_manager.send_error("Too many messages. Slow down.", websocket)
                    continue

                message_type = incoming_message.get("type")
                if not message_type:
                    await socket_manager.send_error("You should provide message type", websocket)
                    continue

                handler = socket_manager.handlers.get(message_type)

                if not handler:
                    logger.error(f"No handler [{message_type}] exists")
                    await socket_manager.send_error(f"Type: {message_type} was not found", websocket)
                    continue

                await handler(
                    websocket=websocket,
                    socket_manager=socket_manager,
                    incoming_message=incoming_message,
                    chats=chats_cache,
                    current_user=current_user,
                    message_service=message_service,
                )

            except (JSONDecodeError, AttributeError) as excinfo:
                logger.exception(f"Websocket error, detail: {excinfo}")
                await socket_manager.send_error("Wrong message format", websocket)
                continue
            except ValueError as excinfo:
                logger.exception(f"Websocket error, detail: {excinfo}")
                await socket_manager.send_error("Could not validate incoming message", websocket)

            except WebsocketTooManyRequests:
                logger.exception(f"User: {current_user} sent too many ws requests")
                await socket_manager.send_error("You have sent too many requests", websocket)


    except WebSocketDisconnect:
        logger.info(f"Websocket disconnected for user: {user_guid_str}")
    finally:
        await socket_manager.remove_user_guid_to_websocket(user_guid=user_guid_str, websocket=websocket)
