import asyncio
import logging
from uuid import UUID
from typing import AsyncIterator, Dict, Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.repository.chat_repository import ChatRepository
from backend.repository.messages_repository import MessageRepository
from backend.services.ai.llm_client import LLMClient
from backend.utils.exceptions import ChatNotFoundError, LLMError, LLMUnavailableError

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

    async def get_context_chat(self, chat_guid: UUID, user_id: int) -> Dict[str, Any]:
        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat_by_guid_for_participant(chat_guid, user_id)
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
            chat = await ChatRepository(session).get_chat_by_guid_for_participant(chat_guid, user_id)
            if chat is None:
                raise ChatNotFoundError()
            short_messages = await MessageRepository(session).get_recent(chat.id, limit=HISTORY_WINDOW)
            short_messages = [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in short_messages
            ]

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

        # degraded (llm_service::response_degraded) - служебная нота об обрыве/сбое, не
        # настоящий ответ. Пользователь и так видит её в этом ответе - в БД не пишем,
        # чтобы не засорять историю/саммари следующих ходов текстом ошибки.
        if not rag_result.get("degraded", False):
            async with self._sf() as session:
                async with session.begin():
                    await MessageRepository(session).add_message(
                        chat_id, content=assistant_response, role="assistant", sources=sources
                    )

        self._trigger_summary_in_background(chat_id, summary_link)
        return {"response": assistant_response, "sources": sources}

    async def ensure_chat_exists(self, chat_guid: UUID, user_id: int) -> None:
        """Отдельная от process_message_stream проверка - нужна как FastAPI-зависимость
        (Depends в chats_routes.py) для стримингового эндпоинта. Тот эндпоинт сам стал
        async-генератором (ради нативного EventSourceResponse - см. agent_routers.py в
        llm_service, тот же паттерн), а значит ChatNotFoundError изнутри его собственного
        тела всплыл бы только на первой итерации, когда 200 и заголовки уже ушли. Depends
        резолвится ДО вызова тела эндпоинта - здесь исключение ещё становится чистым 404."""
        async with self._sf() as session:
            chat = await ChatRepository(session).get_chat_by_guid_for_participant(chat_guid, user_id)
            if chat is None:
                raise ChatNotFoundError()

    async def process_message_stream(
        self, user_id: int, chat_guid: UUID, content: str
    ) -> AsyncIterator[tuple[str, dict]]:
        """SSE-вариант process_message().

        Генерация ответа и его сохранение в БД идут в отдельной asyncio.Task
        (self._background_tasks - тот же паттерн, что и у фонового саммари), а не в
        генераторе, который отдаёт события в HTTP-ответ. Причина: StreamingResponse
        Starlette сам слушает ASGI-дисконнект и при разрыве браузера (закрыл вкладку,
        потерял сеть) шлёт CancelledError в этот генератор - если бы он же дёргал LLM,
        обрыв на середине ответа терял бы уже сгенерированный (и оплаченный) текст, не
        сохранив его в БД. Задача же не привязана к scope конкретного HTTP-запроса и
        не отменяется при его дисконнекте - продолжает работать до конца и пишет
        результат в БД независимо от того, слушает её ещё кто-то через SSE или нет.
        Мост между ними - asyncio.Queue: задача пишет в неё, генератор читает.

        Подготовка (поиск чата, сохранение сообщения юзера) выполняется до запуска
        задачи, а не внутри неё - иначе ChatNotFoundError всплывёт только в фоне, когда
        StreamingResponse уже отдал 200 и заголовки не переписать."""
        async with self._sf() as session:
            chat = await ChatRepository(session).get_chat_by_guid_for_participant(chat_guid, user_id)
            if chat is None:
                raise ChatNotFoundError()
            short_messages = await MessageRepository(session).get_recent(chat.id, limit=HISTORY_WINDOW)
            short_messages = [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in short_messages
            ]

        summary_link = chat.summary_link
        summary_chat = chat.summary
        chat_id = chat.id

        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(chat_id, content=content, role="user")

        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

        async def generate_and_persist() -> None:
            answer_parts: list[str] = []
            sources: list = []
            degraded = False
            try:
                try:
                    async for event_name, data in self._llm.stream_answer(
                        question=content, history_messages=short_messages, summary=summary_chat or "",
                    ):
                        if event_name == "token":
                            answer_parts.append(data.get("text", ""))
                        elif event_name == "sources":
                            sources = data.get("sources", [])
                        elif event_name == "done":
                            # llm_service уже собрал полный текст (в т.ч. с пометкой обрыва,
                            # если генерация прервалась на его стороне) - он авторитетный,
                            # накопленные по token-событиям куски ему не нужны.
                            answer_parts = [data.get("answer", "")]
                            degraded = data.get("degraded", False)
                        await queue.put((event_name, data))
                except (LLMError, LLMUnavailableError) as exc:
                    # Обрыв связи backend -> llm_service (не сам апстрим-LLM - тот уже
                    # восстанавливается внутри llm_service, см. LeanRagAgent.run_stream).
                    # То, что успело прийти token-событиями, не теряем - показываем с
                    # пометкой, а не молча роняем на середине ответа. Всегда деградация -
                    # обрыв нашего же соединения к llm_service, не настоящий ответ.
                    note = (
                        "\n\n_[ответ прерван: обрыв соединения с llm_service]_"
                        if answer_parts else "_Не удалось получить ответ: сбой при обращении к llm_service._"
                    )
                    answer_parts.append(note)
                    degraded = True
                    await queue.put(("token", {"text": note}))
                    await queue.put(("error", {"message": str(exc)}))

                answer = "".join(answer_parts)
                # degraded - служебная нота, не настоящий ответ. Пользователь уже увидел
                # её через token/error-события выше - в БД не пишем, чтобы не засорять
                # историю/саммари следующих ходов текстом ошибки (см. process_message()).
                if not degraded:
                    async with self._sf() as session:
                        async with session.begin():
                            await MessageRepository(session).add_message(
                                chat_id, content=answer, role="assistant", sources=sources
                            )

                self._trigger_summary_in_background(chat_id, summary_link)
            except Exception:
                logger.exception("process_message_stream background task failed chat_id=%s", chat_id)
            finally:
                # Сентинел конца потока - в finally, чтобы читатель ниже не завис
                # навсегда, если тут выше вылетело что-то неожиданное (напр. сама БД).
                await queue.put(None)

        task = asyncio.create_task(generate_and_persist())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        async def event_generator() -> AsyncIterator[tuple[str, dict]]:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item

        return event_generator()