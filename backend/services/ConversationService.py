
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class ConversationService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def update_summary_count(self, chat_id: UUID) -> None:
        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat(chat_id)
                chat.summary_count = (chat.summary_count or 0) + 2

        if chat.summary_count % 20 == 0:
            await self.update_summary(chat_id)

    async def get_context_chat(self, chat_id: UUID, k=10) -> Dict[str, Any]:
        async with self._sf() as session:
            async with session.begin():
                chat = await ChatRepository(session).get_chat(chat_id)
                messages = await MessageRepository(session).get_history(chat_id)

        standard_window = 10
        window = standard_window + chat.summary_count
        short_messages = [{"role": m.role, "content": m.content} for m in messages[:window]] or []

        return {"summary": chat.summary_count, "messages": short_messages}

    async def update_summary(self, chat_id: UUID, summary_batch_size: int = 10) -> None:
            async with self._sf() as session:
                async with session.begin():
                    chat = await ChatRepository(session).get_chat(chat_id)
                    messages = await MessageRepository(session).get_history(chat.chat_id)

            summary_link = chat.summary_link
            if summary_link is None:
                messages = messages[:10]
            else:
                async with self._sf() as session:
                    async with session.begin():
                        messages = await MessageRepository(session).get_messages_after(chat_id=chat_id,
                                                                                       after_id=chat.summary_link,
                                                                                       summary_batch_size=summary_batch_size)
            messages = [{"role": m.role, "content": m.content} for m in messages] or []

            # result = updatee_llm_sammary()
            async with self._sf() as session:
                async with session.begin():
                    chat = await ChatRepository(session).get_chat(chat_id)
                    chat.summary_count = 0
                    chat.summary_link = new_summary_link
                    chat.summary = result

            return

    async def process_message(self, user_id: UUID, chat_id: UUID, content: str) -> Dict:
        # 1. Читаем историю — короткая сессия, сразу закрываем
        async with self._sf() as session:
            messages_db = await MessageRepository(session).get_history(chat_id)
            short_messages = [{"role": m.role, "content": m.content} for m in messages_db]
            chat = await ChatRepository(session).get_chat(chat_id)

        summary_chat = chat.summary

        # 2. Сохраняем вопрос пользователя
        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(chat_id, role="user", content=content)

        # 3. LLM вызов — БД не занята
        rag_result = await get_llm_answer(
            question=content,
            history_massage=short_messages,
            summary=summary_chat,
        )

        assistant_response = rag_result["answer"]
        sources = rag_result.get("sources", [])

        # 4. Сохраняем ответ ассистента (атомарно — сюда добавится update_summary)
        async with self._sf() as session:
            async with session.begin():
                await MessageRepository(session).add_message(
                    chat_id, role="assistant", content=assistant_response, sources=sources
                )

        await self.update_summary_count(chat_id)
        return {"response": assistant_response, "sources": sources}
