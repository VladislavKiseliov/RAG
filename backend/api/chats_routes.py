import uuid

from fastapi import APIRouter
from starlette import status

from backend.models.database_models import ChatType
from backend.schemas.schemas import Message, ChatUpdate
from backend.dependencies import CurrentUserDep, ChatServiceDep, ConversationServiceDep

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    chat = await service.create_chat(user_id=current_user.id, chat_type=ChatType.AI_DIRECT)
    return {"conversation_id": chat.chat_guid}


@router.get("")
async def get_all_conversations(
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    conversations = await service.get_user_active_chats(user_id=current_user.id, chat_type=ChatType.AI_DIRECT)
    return {"conversations": conversations}


@router.get("/{chat_guid}")
async def get_conversation_history(
        chat_guid: uuid.UUID,
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    history = await service.get_history(chat_guid=chat_guid, user_id=current_user.id)
    return {"history": history}


@router.post("/{chat_guid}/messages")
async def chat_endpoint(
        chat_guid: uuid.UUID,
        message: Message,
        current_user: CurrentUserDep,
        service: ConversationServiceDep,
):
    return await service.process_message(
        user_id=current_user.id,
        chat_guid=chat_guid,
        content=message.user_message,
    )


@router.patch("/{chat_guid}/rename")
async def update_title_chat(
        chat_guid: uuid.UUID,
        title_data: ChatUpdate,
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    await service.update_chat_title(chat_guid=chat_guid, user_id=current_user.id, new_title=title_data.title)
    return {"status": "success"}


@router.delete("/{chat_guid}")
async def delete_chat(
        chat_guid: uuid.UUID,
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    await service.delete_chat(chat_guid=chat_guid, user_id=current_user.id)
    return {"status": "success"}