from rag_service.domain.chunking.docling_segmenter import ChapterSplitter


def test_split_creates_chapter_per_numbered_heading() -> None:
    markdown = (
        "## 1 ОБЩИЕ ПОЛОЖЕНИЯ\n"
        "Текст главы 1.\n"
        "## 2 ПОРЯДОК ОПРЕДЕЛЕНИЯ\n"
        "Текст главы 2.\n"
    )

    chapters = ChapterSplitter().split(markdown)

    assert [c.number for c in chapters] == ["1", "2"]
    assert "Текст главы 1." in chapters[0].markdown
    assert "Текст главы 2." in chapters[1].markdown


def test_split_ignores_reused_chapter_number_from_worked_example() -> None:
    """Регрессия на B9: шаги внутри примера ("1. Исходные данные.") переиспользуют
    номера уже открытых глав — не должны порождать новую главу/дубликат номера."""
    markdown = (
        "## 1 ОБЩИЕ ПОЛОЖЕНИЯ\n"
        "Текст главы 1.\n"
        "## 2 ПОРЯДОК ОПРЕДЕЛЕНИЯ\n"
        "Текст главы 2.\n"
        "## 5.8.2. Здания категории Б\n"
        "## Пример 23\n"
        "## 1. Исходные данные.\n"
        "Шаг решения примера.\n"
        "## 2. Определение категории здания.\n"
        "Ещё шаг решения.\n"
        "## 5.8.3. Здания категории В\n"
        "Текст следующей главы.\n"
    )

    chapters = ChapterSplitter().split(markdown)

    numbers = [c.number for c in chapters]
    assert numbers == ["1", "2", "5.8.2", "5.8.3"]
    assert len(numbers) == len(set(numbers)), "chapter_number должен быть уникален для bulk_insert_chapters"

    body_5_8_2 = next(c for c in chapters if c.number == "5.8.2").markdown
    assert "Шаг решения примера." in body_5_8_2
    assert "Ещё шаг решения." in body_5_8_2


def test_split_stops_at_appendix() -> None:
    markdown = (
        "## 1 ОБЩИЕ ПОЛОЖЕНИЯ\n"
        "Текст главы 1.\n"
        "## Приложение А Что-то\n"
        "## 2 Мусор после приложения\n"
    )

    chapters = ChapterSplitter().split(markdown)

    assert [c.number for c in chapters] == ["1"]


def test_split_falls_back_to_recursive_chunks_when_no_numbered_headings() -> None:
    """Регрессия: документы без пронумерованной структуры разделов (man-страницы -
    заголовки вида "## NAME"/"## DESCRIPTION" без цифр) не матчат основной паттерн
    вообще - раньше split() возвращал пустой список, и это ошибочно трактовалось
    выше по пайплайну как "в документе нет контента" (ingestion_service.py::store_chunks),
    хотя текст был извлечён нормально, просто резать его было не по чему."""
    markdown = (
        "## NAME\n"
        "auditctl - a utility to assist controlling the kernel's audit system.\n\n"
        "## SYNOPSIS\n"
        "auditctl [options]\n\n"
        "## DESCRIPTION\n"
        + ("Some long description text about audit rules and configuration. " * 30)
    )

    chapters = ChapterSplitter().split(markdown)

    assert len(chapters) > 0
    numbers = [c.number for c in chapters]
    assert len(numbers) == len(set(numbers)), "номера псевдо-глав должны быть уникальны"
    # Весь исходный текст должен быть покрыт (с точностью до overlap/пробелов) -
    # ничего не потеряно молча.
    assert "auditctl - a utility" in chapters[0].markdown
    assert any("audit rules and configuration" in c.markdown for c in chapters)


def test_split_does_not_fall_back_when_numbered_heading_exists() -> None:
    """Если хоть одна пронумерованная глава нашлась - используем её, fallback не
    трогаем (даже если рядом есть неструктурированный текст без номеров)."""
    markdown = "## 1 ОБЩИЕ ПОЛОЖЕНИЯ\nТекст главы 1.\n"

    chapters = ChapterSplitter().split(markdown)

    assert [c.number for c in chapters] == ["1"]


def test_split_fallback_on_short_document_returns_single_chapter() -> None:
    markdown = "## NAME\nshort-tool - does a short thing.\n"

    chapters = ChapterSplitter().split(markdown)

    assert len(chapters) == 1
    assert chapters[0].number == "1"
    assert "short-tool" in chapters[0].markdown
