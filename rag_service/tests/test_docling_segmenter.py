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
