import uuid

from fastapi import APIRouter
from starlette import status

from backend.api.schemas import Message, ChatUpdate
from backend.dependencies import CurrentUserDep, ChatServiceDep, ConversationServiceDep

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    """Create a new empty chat session.

    Initializes a new dialog in the database for the authenticated user.

    Returns:
        Dict with conversation_id (UUID of the created chat).
    """
    chat_id = await service.create_chat(current_user.id)
    return {"conversation_id": chat_id}

@router.get("")
async def get_all_conversations(
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    """Return all chats for the authenticated user.

    Returns:
        Dict with conversations list (id and title for each chat), ordered by last update.
    """
    conversations = await service.get_all_previews(current_user.id)
    return {"conversations": conversations}


@router.get("/{chat_id}")
async def get_conversation_history(
        chat_id: uuid.UUID,
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    """Return the full message history for a specific chat.

    Returns:
        Dict with history list of messages (id, role, content, sources).
    """
    history = await service.get_history(chat_id = chat_id,user_id = current_user.id)
    return {"history": history}


@router.post("/{chat_id}/messages")
async def chat_endpoint(
        chat_id: uuid.UUID,
        message: Message,
        current_user: CurrentUserDep,
        service: ConversationServiceDep,
):
    """Send a user message and receive an AI response.

    Saves the user message, calls the LLM pipeline via llm_service,
    saves the assistant response, and returns it with source references.

    Returns 502 if llm_service is unavailable or returns an error.
    """
    return await service.process_message(
        user_id=current_user.id,
        chat_id=chat_id,
        content=message.user_message,
    )


@router.patch("/{chat_id}/rename")
async def update_title_chat(
        chat_id: uuid.UUID,
        title_data: ChatUpdate,
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    """Rename a chat.

    Returns 404 if the chat does not exist or does not belong to the user.
    """
    await service.rename_chat(user_id=current_user.id, chat_id=chat_id, new_title=title_data.title)
    return {"status": "success", "message": "Chat title updated successfully"}


@router.delete("/{chat_id}")
async def delete_chat(
        chat_id: uuid.UUID,
        current_user: CurrentUserDep,
        service: ChatServiceDep,
):
    """Permanently delete a chat and all its messages.

    Returns 404 if the chat does not exist or does not belong to the user.
    """
    await service.delete_chat(current_user.id, chat_id)
    return {"status": "success", "message": "Чат успешно удален"}