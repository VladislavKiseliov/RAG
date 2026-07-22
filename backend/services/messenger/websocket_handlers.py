import logging

from fastapi import WebSocket

from backend.services.auth_service import CurrentUser
from backend.schemas.websocket_schemas import (
    AddUserToChatSchema,
    MessageReadSchema,
    NotifyChatRemovedSchema,
    ReceiveMessageSchema,
    SendMessageSchema,
    UserTypingSchema,
)
from backend.services.messenger.message_service import ChatNotFoundError, MessageService
from backend.services.messenger.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


async def new_message_handler(
    websocket: WebSocket,
    socket_manager: WebSocketManager,
    incoming_message: dict,
    chats: dict,
    current_user: CurrentUser,
    message_service: MessageService,
    **kwargs,
):
    incoming_message["user_guid"] = current_user.guid
    message_schema = ReceiveMessageSchema(**incoming_message)
    chat_guid = str(message_schema.chat_guid)

    try:
        chat_id, is_new_chat = await message_service.resolve_chat(chat_guid, chats)
    except ChatNotFoundError:
        await socket_manager.send_error("Chat has not been added", websocket)
        return

    try:
        message, chat = await message_service.save_message(
            content=message_schema.content,
            chat_id=chat_id,
            user_id=current_user.id,
        )
    except Exception:
        logger.exception("[new_message] Failed to save message")
        await socket_manager.send_error("Failed to save message", websocket)
        return

    member_guids = await message_service.get_chat_member_guids(chat_id)
    outgoing = SendMessageSchema(
        message_guid=message.guid,
        chat_guid=chat.guid,
        user_guid=current_user.guid,
        content=message.content,
        created_at=message.created_at,
        is_read=False,
        is_new=True,
    ).model_dump_json()

    await socket_manager.broadcast_to_users(member_guids, outgoing)



async def message_read_handler(
    websocket: WebSocket,
    socket_manager: WebSocketManager,
    incoming_message: dict,
    chats: dict,
    current_user: CurrentUser,
    message_service: MessageService,
    **kwargs,
):
    message_read_schema = MessageReadSchema(**incoming_message)
    chat_guid = str(message_read_schema.chat_guid)
    message_guid = str(message_read_schema.message_guid)

    try:
        message = await message_service.mark_message_read(
            message_guid=message_guid,
            chat_guid=chat_guid,
            chats=chats,
            user_id=current_user.id,
        )
    except ChatNotFoundError:
        await socket_manager.send_error(f"Chat {chat_guid} does not exist", websocket)
        return

    if not message:
        await socket_manager.send_error(f"Message {message_guid} does not exist", websocket)
        return

    chat_id = chats[chat_guid]
    member_guids = await message_service.get_chat_member_guids(chat_id)

    outgoing = {
        "type": "message_read",
        "user_guid": str(current_user.guid),
        "chat_guid": chat_guid,
        "last_read_message_guid": str(message.guid),
        "last_read_message_created_at": str(message.created_at),
    }
    await socket_manager.broadcast_to_users(member_guids, outgoing)


async def user_typing_handler(
    websocket: WebSocket,
    socket_manager: WebSocketManager,
    incoming_message: dict,
    chats: dict,
    current_user: CurrentUser,
    message_service: MessageService,
    **kwargs,
):
    user_typing_schema = UserTypingSchema(**incoming_message)
    chat_guid = str(user_typing_schema.chat_guid)

    try:
        chat_id, _ = await message_service.resolve_chat(chat_guid, chats)
    except ChatNotFoundError:
        await socket_manager.send_error(f"Chat {chat_guid} does not exist", websocket)
        return
    member_guids = await message_service.get_chat_member_guids(chat_id)
    await socket_manager.broadcast_to_users(member_guids, user_typing_schema.model_dump_json())


async def add_user_to_chat_handler(
    websocket: WebSocket,
    socket_manager: WebSocketManager,
    incoming_message: dict,
    chats: dict,
    **kwargs,
):
    add_user_to_chat_schema = AddUserToChatSchema(**incoming_message)
    chats[add_user_to_chat_schema.chat_guid] = add_user_to_chat_schema.chat_id


async def chat_deleted_handler(
    websocket: WebSocket,
    socket_manager: WebSocketManager,
    incoming_message: dict,
    chats: dict,
    current_user: CurrentUser,
    message_service: MessageService,
    **kwargs,
):
    notify_chat_removed_schema = NotifyChatRemovedSchema(**incoming_message)
    chat_guid = notify_chat_removed_schema.chat_guid

    if chat_guid not in chats:
        await socket_manager.send_error(f"Chat {chat_guid} does not exist", websocket)
        return

    chat_id = chats[chat_guid]
    member_guids = await message_service.get_chat_member_guids(chat_id)
    sender_guid = str(current_user.guid)

    outgoing = {
        "type": "chat_deleted",
        "user_guid": sender_guid,
        "user_name": current_user.first_name,
        "chat_guid": chat_guid,
    }

    recipients = [g for g in member_guids if g != sender_guid]
    await socket_manager.broadcast_to_users(recipients, outgoing)


def register_handlers(socket_manager: WebSocketManager) -> None:
    socket_manager.handlers["new_message"] = new_message_handler
    socket_manager.handlers["message_read"] = message_read_handler
    socket_manager.handlers["user_typing"] = user_typing_handler
    socket_manager.handlers["add_user_to_chat"] = add_user_to_chat_handler
    socket_manager.handlers["chat_deleted"] = chat_deleted_handler