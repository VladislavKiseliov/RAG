from __future__ import annotations

from llm_service.application.agent.formatters import format_chat_history


def test_empty_history_returns_empty_string():
    assert format_chat_history([]) == ""


def test_numbers_turns_in_order():
    messages = [
        {"role": "user", "content": "привет"},
        {"role": "assistant", "content": "здравствуй"},
        {"role": "user", "content": "как дела"},
    ]
    result = format_chat_history(messages)
    assert "[1]" in result
    assert "[2]" in result
    assert "[3]" in result
    assert result.index("[1]") < result.index("[2]") < result.index("[3]")


def test_translates_role_labels_to_russian():
    messages = [
        {"role": "user", "content": "привет"},
        {"role": "assistant", "content": "здравствуй"},
    ]
    result = format_chat_history(messages)
    assert "Пользователь: привет" in result
    assert "Ассистент: здравствуй" in result


def test_marks_only_the_last_message() -> None:
    # Живой баг: без явной метки модель иногда путала, к какой реплике относится
    # текущий вопрос ("ты откуда это взял?" получило ответ про сообщение 2 хода назад).
    messages = [
        {"role": "user", "content": "первое"},
        {"role": "assistant", "content": "второе"},
        {"role": "user", "content": "третье"},
    ]
    result = format_chat_history(messages)
    assert result.count("последняя реплика перед текущим вопросом") == 1
    marked_line = next(line for line in result.split("\n\n") if "последняя реплика" in line)
    assert "третье" in marked_line
    assert "первое" not in marked_line
    assert "второе" not in marked_line


def test_turns_separated_by_blank_line_not_single_newline() -> None:
    # Живой баг: одинарный \n между репликами схлопывал границы, если ответ
    # ассистента сам многострочный (списки/таблицы - обычное дело для RAG-ответов).
    messages = [
        {"role": "assistant", "content": "строка1\nстрока2\nстрока3"},
        {"role": "user", "content": "следующий вопрос"},
    ]
    result = format_chat_history(messages)
    assert "\n\n" in result
    # Многострочный контент одной реплики не должен сам порождать разрыв на "[N]"
    assert result.count("[1]") == 1
    assert result.count("[2]") == 1


def test_missing_role_defaults_to_user_label() -> None:
    result = format_chat_history([{"content": "без роли"}])
    assert "Пользователь: без роли" in result
