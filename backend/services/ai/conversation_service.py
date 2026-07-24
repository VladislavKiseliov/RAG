import asyncio
import logging
from uuid import UUID
from typing import Dict, Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.repository.chat_repository import ChatRepository
from backend.repository.messages_repository import MessageRepository
from backend.services.ai.llm_client import LLMClient
from backend.utils.exceptions import ChatNotFoundError

logger = logging.getLogger(__name__)

HISTORY_WINDOW = 10
SUMMARY_THRESHOLD = 20


class ConversationService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], llm_client: LLMClient):
        self._sf = session_factory
        self._llm = llm_client
        # Сериализует update_summary по chat_id — без лока два параллельных сообщения в один
        # чат, оба пересёкшие SUMMARY_THRESHOLD, читают одинаковый устаревший summary_link,
        # шлют overlapping batch в LLM и в конце перезаписывают chat.summary друг за другом
        # (last-write-wins), теряя более полную версию. Ключи по chat_id копятся на весь
        # процесс — не проблема при масштабе этого проекта (self-hosted, конечное число чатов).
        self._summary_locks: dict[int, asyncio.Lock] = {}
        # Держит ссылки на фоновые таски саммаризации — без этого event loop может
        # собрать Task сборщиком мусора до завершения (см. тот же паттерн в
        # rag_service/application/ingestion_service.py::_run_pipeline).
        self._background_tasks: set[asyncio.Task] = set()

    def _get_summary_lock(self, chat_id: int) -> asyncio.Lock:
        lock = self._summary_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._summary_locks[chat_id] = lock
        return lock

    async def _maybe_trigger_summary(self, chat_id: int, summary_link: int | None) -> None:
        async with self._sf() as session:
            count = await MessageRepository(session).count_after(chat_id, summary_link)
        if count >= SUMMARY_THRESHOLD:
            await self.update_summary(chat_id)

    def _trigger_summary_in_background(self, chat_id: int, summary_link: int | None) -> None:
        """Запускает проверку/генерацию саммари в фоне, не блокируя ответ пользователю.

        Саммари — ещё один LLM-вызов поверх основного ответа; синхронное ожидание
        здесь регулярно продавливало ответ за proxy_read_timeout на nginx (клиент
        видел ошибку, хотя ответ ассистента уже сохранён в БД).
        """
        async def _run() -> None:
            try:
                await self._maybe_trigger_summary(chat_id, summary_link)
            except Exception:
                logger.exception("Background summary trigger failed chat_id=%s", chat_id)

        task = asyncio.create_task(_run())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def get_context_chat(self, chat_guid: UUID) -> Dict[str, Any]:
        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat_by_guid(chat_guid)
                if chat is None:
                    raise ChatNotFoundError()
                messages = await MessageRepository(session).get_recent(chat.id, limit=HISTORY_WINDOW)

        short_messages = [{"role": m.role, "content": m.content} for m in messages]
        return {"summary": chat.summary, "messages": short_messages}

    async def update_summary(self, chat_id: int) -> None:
        async with self._get_summary_lock(chat_id):
            async with self._sf() as session:
                async with session.begin():
                    chat = await ChatRepository(session).get_chat(chat_id)
                    if chat is None:
                        raise ChatNotFoundError()
                    batch = await MessageRepository(session).get_messages_after(
                        chat_id=chat.id,
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

            result = await self._llm.get_summary(
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

    async def process_message(self, user_id: int, chat_guid: UUID, content: str) -> Dict:
        async with self._sf() as session:
            chat = await ChatRepository(session).get_chat_by_guid(chat_guid)
            if chat is None:
                raise ChatNotFoundError()
            short_messages = await MessageRepository(session).get_recent(chat.id, limit=HISTORY_WINDOW)
            short_messages = [{"role": m.role, "content": m.content} for m in short_messages]

        summary_link = chat.summary_link
        summary_chat = chat.summary
        chat_id = chat.id

        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(chat_id, content=content, role="user")

        rag_result = await self._llm.get_answer(
            question=content,
            history_messages=short_messages,
            summary=summary_chat or "",
        )

        assistant_response = rag_result["answer"]
        sources = rag_result.get("sources", [])

        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(
                    chat_id, content=assistant_response, role="assistant", sources=sources
                )

        self._trigger_summary_in_background(chat_id, summary_link)
        return {"response": assistant_response, "sources": sources}