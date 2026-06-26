import logging

from backend.schemas.schemas import DirectChatItem, NewChatCreated
from backend.services.auth_service import CurrentUser
from backend.services.messenger.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


async def send_new_chat_created_ws_message(
    socket_manager: WebSocketManager,
    current_user: CurrentUser,
    chat: DirectChatItem,
) -> None:
    schema = NewChatCreated(
        chat_guid=chat.chat_guid,
        friend_guid=current_user.guid,
        friend_login=current_user.login,
        friend_first_name=current_user.first_name,
        friend_last_name=current_user.last_name,
    )
    await socket_manager.send_to_user(str(chat.friend_guid), schema.model_dump_json())