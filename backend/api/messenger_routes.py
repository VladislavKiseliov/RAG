from uuid import UUID

from fastapi import APIRouter, Query

from backend.dependencies import CurrentUserDep, MessengerServiceDep
from backend.schemas.schemas import CreateDirectChatRequest
from backend.dependencies import WebSocketManagerDep
from backend.services.messenger.websocket_utils import send_new_chat_created_ws_message

router = APIRouter(prefix="/messenger", tags=["messenger"])


@router.post("/chats/direct")
async def create_direct_chat(
    body: CreateDirectChatRequest,
    current_user: CurrentUserDep,
    messenger_service: MessengerServiceDep,
    socket_manager: WebSocketManagerDep,
):
    chat = await messenger_service.create_direct_chat(
        user_id=current_user.id,
        friend_guid=body.friend_guid,
    )
    await send_new_chat_created_ws_message(socket_manager, current_user, chat)
    return chat


@router.get("/chats/")
async def get_user_chats(
    current_user: CurrentUserDep,
    messenger_service: MessengerServiceDep,
):
    return await messenger_service.get_user_chats(user_id=current_user.id)


@router.delete("/chats/{chat_guid}")
async def delete_direct_chat(
    chat_guid: UUID,
    current_user: CurrentUserDep,
    messenger_service: MessengerServiceDep,
    socket_manager: WebSocketManagerDep,
):
    member_guids = await messenger_service.delete_direct_chat(chat_guid, current_user.id)
    other_guids = [g for g in member_guids if g != str(current_user.guid)]
    await socket_manager.broadcast_to_users(other_guids, {
        "type": "chat_deleted",
        "chat_guid": str(chat_guid),
    })
    return {"ok": True}


@router.get("/chats/{chat_guid}/messages")
async def get_chat_messages(
    chat_guid: UUID,
    current_user: CurrentUserDep,
    messenger_service: MessengerServiceDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await messenger_service.get_chat_messages(
        chat_guid=chat_guid,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )