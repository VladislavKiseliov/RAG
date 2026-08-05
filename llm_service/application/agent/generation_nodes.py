"""build_prompt_node/generate_node/extract_sources_node/post_actions_node -
сборка промпта, вызов LLM, постобработка ответа."""

from __future__ import annotations

import re
import time
from typing import Any

from llm_service.application.agent.formatters import build_sources_payload, format_retrieval_item_for_prompt
from llm_service.application.agent.retrieval_nodes import _MAX_APPENDIX_CONTEXT_CHARS
from llm_service.application.lean_rag_models import FinalPromptData, LeanAgentState
from llm_service.utils.logger_config import setup_logger
from llm_service.utils.stream_writer import get_safe_stream_writer

logger = setup_logger("llm_service.lean_rag_agent")

# reflect_node уже ловит needs_appendix через LLM, но reflect вообще не вызывается,
# когда rerank сразу дал "sufficient" (типичный случай: нашли раздел, который просто
# УПОМИНАЕТ приложение по имени - "см. Приложение А" - с высоким скором, но не сам
# текст приложения). Живой прогон подтвердил: без этой подстраховки такой запрос
# долетает до generate() без текста приложения вообще. Дешёвый code-gate здесь не
# спрашивает LLM "нужно ли" - только ловит явное упоминание либо в САМОМ вопросе
# пользователя, либо в уже найденном контексте (второй случай нужен, когда
# reflect_node на повторном круге не звал LLM вообще - см. её докстринг про
# reflect_rounds >= 1 fast-path, needs_appendix там не проверяется никак).
# Окончательное решение, использовать ли этот текст в ответе, остаётся за LLM в
# generate_node, как и с любым другим куском context.
_APPENDIX_MENTION_RE = re.compile(r"приложени", re.IGNORECASE)


class GenerationNodesMixin:
    async def build_prompt_node(self, state: LeanAgentState) -> dict[str, Any]:
        started = time.perf_counter()

        context_str = "\n\n".join(format_retrieval_item_for_prompt(item) for item in state.retrieval_data)

        appendix_context = state.appendix_context
        mentions_appendix = _APPENDIX_MENTION_RE.search(state.query) or _APPENDIX_MENTION_RE.search(context_str)
        if not appendix_context and state.retrieval_data and mentions_appendix:
            doc_id = state.retrieval_data[0].metadata.doc_id
            appendix_text = await self.retrieval_service.get_appendix(doc_id)
            if appendix_text:
                appendix_context = appendix_text[:_MAX_APPENDIX_CONTEXT_CHARS]

        if appendix_context:
            # Подтянуто либо reflect_node (needs_appendix от LLM), либо code-gate'ом выше.
            context_str += f"\n\n[Приложения документа]\n{appendix_context}"

        final_context = FinalPromptData(context=context_str,
                                        route=state.route,
                                        chat_history=state.messages,
                                        summary=state.summary,
                                        current_query=state.query
                                        )

        logger.info(
            "Build prompt finished",
            extra={
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"final_context": final_context}

    async def generate_node(self, state: LeanAgentState) -> dict[str, str]:
        """Генерирует финальный ответ с учётом route, контекста и истории диалога.

        Стримит через generate_stream() + custom stream writer вместо generate() -
        единый путь что для /llm/answer (ainvoke без custom stream_mode - writer
        безопасный no-op, см. get_safe_stream_writer), что для /llm/answer/stream
        (astream(stream_mode="custom") в lean_rag_agent.py::run_stream - каждый delta
        уходит наружу как только пришёл от LLM). Раньше это два разных вызова в двух
        разных местах (этот метод дергал generate(), agent_stream.py::StreamRunner -
        отдельно generate_stream() с полной копией ретрай/fallback-логики ниже) -
        теперь один код на оба случая, StreamRunner удалён.

        Ретрай TTFT (до первого чанка) - целиком в generate_stream()
        (_stream_completion_with_retry, LLM_provider.py). Здесь - два случая, которые
        тот ретрай не покрывает: обрыв ПОСЛЕ первых токенов (не ретраим - вторая
        генерация поверх уже показанного текста не имеет смысла, только помечаем
        обрыв) и полный сбой без единого токена (одноразовый fallback на
        нестримящий generate() - живой инцидент с gatellm.ru, 100% отказов именно
        на stream=true при рабочем stream=false)."""
        started = time.perf_counter()
        writer = get_safe_stream_writer()

        answer_parts: list[str] = []
        try:
            async for delta in self.llm_provider.generate_stream(
                current_query=state.query, data_prompt=state.final_context
            ):
                answer_parts.append(delta)
                writer({"event": "token", "data": {"text": delta}})
        except Exception as exc:
            if answer_parts:
                logger.warning("LLM stream interrupted mid-generation: %s", exc)
                note = "\n\n_[ответ прерван: обрыв соединения с LLM]_"
                answer_parts.append(note)
                writer({"event": "token", "data": {"text": note}})
            else:
                logger.warning(
                    "LLM stream produced zero tokens, falling back to non-streaming generate(): %s", exc,
                )
                try:
                    answer = await self.llm_provider.generate(
                        current_query=state.query, data_prompt=state.final_context
                    )
                except Exception as fallback_exc:
                    logger.exception("Non-streaming fallback also failed")
                    note = f"_Не удалось получить ответ: {fallback_exc}_"
                    answer_parts.append(note)
                    writer({"event": "token", "data": {"text": note}})
                else:
                    answer_parts.append(answer)
                    writer({"event": "token", "data": {"text": answer}})

        answer = "".join(answer_parts)

        logger.info(
            "Generate finished",
            extra={
                "route": state.route,
                "query": state.query,
                "answer_len": len(answer or ""),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"response_model": answer}

    async def extract_sources_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНАЯ нода: тот же build_sources_payload, что раньше вызывался инлайново в
        run_stream()/agent_routers.py - вынесен в ноду графа, поведение не меняется."""
        return {"sources": build_sources_payload(state.retrieval_data)}

    async def post_actions_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: настоящий no-op - не делает I/O, не вызывает LLM, proposed_action
        остаётся None. Нет ни промпта, ни write-инструментов с реальной реализацией
        (create_task/create_note/update_note - все NotImplementedError в реестре)."""
        return {"proposed_action": None}
