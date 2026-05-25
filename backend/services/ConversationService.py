from uuid import UUID
from typing import Dict, Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.repository.repository import ChatRepository, MessageRepository
from backend.services.llm_client import get_llm_answer, get_llm_summary
from backend.utils.exceptions import ChatNotFoundError

HISTORY_WINDOW = 10
SUMMARY_THRESHOLD = 20


class ConversationService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def _maybe_trigger_summary(self, chat_id: UUID, summary_link: UUID | None) -> None:
        async with self._sf() as session:
            count = await MessageRepository(session).count_after(chat_id, summary_link)
        if count >= SUMMARY_THRESHOLD:
            await self.update_summary(chat_id)

    async def get_context_chat(self, chat_id: UUID) -> Dict[str, Any]:
        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat(chat_id)
                if chat is None:
                    raise ChatNotFoundError()
                messages = await MessageRepository(session).get_recent(chat_id, limit=HISTORY_WINDOW)

        short_messages = [{"role": m.role, "content": m.content} for m in messages]
        return {"summary": chat.summary, "messages": short_messages}

    async def update_summary(self, chat_id: UUID) -> None:
        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat(chat_id)
                if chat is None:
                    raise ChatNotFoundError()
                batch = await MessageRepository(session).get_messages_after(
                    chat_id=chat_id,
                    after_id=chat.summary_link,
                    limit=SUMMARY_THRESHOLD - HISTORY_WINDOW,
                )

        if not batch:
            return

        new_summary_link = batch[-1].id
        messages_dicts = [{"role": m.role, "content": m.content} for m in batch]

        async with self._sf() as session:
            chat = await ChatRepository(session).get_chat(chat_id)
            if chat is None:
                raise ChatNotFoundError()

        result = await get_llm_summary(
            messages=messages_dicts,
            existing_summary=chat.summary or "",
        )

        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat(chat_id)
                if chat is None:
                    raise ChatNotFoundError()
                chat.summary_link = new_summary_link
                chat.summary = result

    async def process_message(self, user_id: UUID, chat_id: UUID, content: str) -> Dict:
        async with self._sf() as session:
            short_messages = await MessageRepository(session).get_recent(chat_id, limit=HISTORY_WINDOW)
            short_messages = [{"role": m.role, "content": m.content} for m in short_messages]
            chat = await ChatRepository(session).get_chat(chat_id)
            if chat is None:
                raise ChatNotFoundError()

        summary_link = chat.summary_link
        summary_chat = chat.summary

        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(chat_id, role="user", content=content)

        rag_result = await get_llm_answer(
            question=content,
            history_massage=short_messages,
            summary=summary_chat or "",
        )

        assistant_response = rag_result["answer"]
        sources = rag_result.get("sources", [])

        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(
                    chat_id, role="assistant", content=assistant_response, sources=sources
                )

        await self._maybe_trigger_summary(chat_id, summary_link)
        return {"response": assistant_response, "sources": sources}