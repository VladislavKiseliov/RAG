import uuid
from collections.abc import AsyncIterable

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette import status

from backend.models.database_models import ChatType
from backend.schemas.schemas import Message, ChatUpdate
from backend.dependencies import CurrentUserDep, ChatServiceDep, ConversationServiceDep
from backend.settings import settings
from backend.utils.rate_limit import enforce_chat_rate_limit

router = APIRouter(prefix="/api/chats", tags=["chats"])

RAG_SERVICE_URL = settings.RAG_SERVICE_URL.rstrip("/")


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


@router.post("/{chat_guid}/messages", dependencies=[Depends(enforce_chat_rate_limit)])
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


async def _validate_stream_chat_exists(
        chat_guid: uuid.UUID,
        current_user: CurrentUserDep,
        service: ConversationServiceDep,
) -> None:
    """`Depends`, не параметр эндпоинта - резолвится ДО тела chat_endpoint_stream. Тот сам
    стал async-генератором (см. комментарий там), поэтому ChatNotFoundError нужно ловить
    здесь, а не внутри его тела, иначе исключение всплывёт только на первой итерации,
    когда EventSourceResponse уже отдал 200 и заголовки не переписать."""
    await service.ensure_chat_exists(chat_guid, current_user.id)


@router.post(
    "/{chat_guid}/messages/stream",
    response_class=EventSourceResponse,
    dependencies=[Depends(enforce_chat_rate_limit), Depends(_validate_stream_chat_exists)],
)
async def chat_endpoint_stream(
        chat_guid: uuid.UUID,
        message: Message,
        current_user: CurrentUserDep,
        service: ConversationServiceDep,
) -> AsyncIterable[ServerSentEvent]:
    generator = await service.process_message_stream(
        user_id=current_user.id,
        chat_guid=chat_guid,
        content=message.user_message,
    )
    async for event_name, data in generator:
        yield ServerSentEvent(event=event_name, data=data)


@router.get("/sources/{parent_id}")
async def get_source_chunk_text(
        parent_id: uuid.UUID,
        current_user: CurrentUserDep,
):
    """Полный текст источника (родительского чанка) — история чата отдаёт sources без
    text/child_chunks (см. ChatService._strip_source_previews), фронт подгружает его
    по требованию при наведении на источник."""
    async with httpx.AsyncClient(base_url=RAG_SERVICE_URL, timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        response = await client.get(f"/parent-chunks/{parent_id}")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Source chunk not found")
    response.raise_for_status()
    return response.json()


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