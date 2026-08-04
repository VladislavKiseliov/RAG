from __future__ import annotations

from llm_service.LLM_provider import _build_answer_messages, _history_to_messages
from llm_service.application.lean_rag_models import FinalPromptData


def make_final_prompt(**overrides) -> FinalPromptData:
    defaults = dict(
        route="domain_rag",
        context="контекст из документов",
        chat_history=[],
        summary="резюме беседы",
        current_query="текущий вопрос",
    )
    defaults.update(overrides)
    return FinalPromptData(**defaults)


class TestHistoryToMessages:
    def test_converts_role_and_content_as_is(self):
        history = [
            {"role": "user", "content": "привет"},
            {"role": "assistant", "content": "здравствуй"},
        ]
        assert _history_to_messages(history) == history

    def test_missing_role_defaults_to_user(self):
        result = _history_to_messages([{"content": "без роли"}])
        assert result == [{"role": "user", "content": "без роли"}]

    def test_empty_history_returns_empty_list(self):
        assert _history_to_messages([]) == []


class TestBuildAnswerMessages:
    def test_returns_system_history_and_final_user_message(self):
        # Регрессия: история диалога раньше склеивалась текстом в одно
        # user-сообщение вместе с summary/context/вопросом - теперь отдельные
        # role-сообщения, как того требует нативный chat-формат LLM API.
        history = [
            {"role": "user", "content": "привет"},
            {"role": "assistant", "content": "здравствуй"},
        ]
        data_prompt = make_final_prompt(chat_history=history)

        messages = _build_answer_messages("текущий вопрос", data_prompt)

        assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
        assert messages[1] == {"role": "user", "content": "привет"}
        assert messages[2] == {"role": "assistant", "content": "здравствуй"}

    def test_final_message_contains_summary_context_and_query_not_history(self):
        data_prompt = make_final_prompt(
            chat_history=[{"role": "user", "content": "старое сообщение"}],
            summary="резюме X",
            context="контекст Y",
        )
        messages = _build_answer_messages("новый вопрос", data_prompt)
        final_message = messages[-1]["content"]

        assert "резюме X" in final_message
        assert "контекст Y" in final_message
        assert "новый вопрос" in final_message
        # История - отдельными сообщениями выше, не задублирована текстом здесь
        assert "старое сообщение" not in final_message

    def test_empty_history_produces_just_system_and_final_user_message(self):
        data_prompt = make_final_prompt(chat_history=[])
        messages = _build_answer_messages("вопрос", data_prompt)
        assert [m["role"] for m in messages] == ["system", "user"]

    def test_domain_rag_route_uses_rag_system_prompt_and_context(self):
        data_prompt = make_final_prompt(route="domain_rag", context="реальный контекст из базы")
        messages = _build_answer_messages("вопрос", data_prompt)
        assert "реальный контекст из базы" in messages[-1]["content"]

    def test_non_rag_route_ignores_context_and_uses_chat_system_prompt(self):
        data_prompt = make_final_prompt(route="smalltalk", context="этого не должно быть в промпте")
        messages = _build_answer_messages("вопрос", data_prompt)
        assert "этого не должно быть в промпте" not in messages[-1]["content"]
        assert "Поиск в базе знаний не производился" in messages[-1]["content"]
