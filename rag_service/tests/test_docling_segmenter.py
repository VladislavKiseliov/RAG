from rag_service.domain.chunking.docling_segmenter import ChapterSplitter, MetaSectionExtractor, parse_abbreviation_section


_BODY_1 = "Текст главы один содержит достаточно слов, чтобы не считаться пустой главой при склейке."
_BODY_2 = "Текст главы два тоже содержит достаточно слов, чтобы не считаться пустой главой при склейке."


def test_split_creates_chapter_per_numbered_heading() -> None:
    markdown = (
        "## 1 ОБЩИЕ ПОЛОЖЕНИЯ\n"
        f"{_BODY_1}\n"
        "## 2 ПОРЯДОК ОПРЕДЕЛЕНИЯ\n"
        f"{_BODY_2}\n"
    )

    chapters = ChapterSplitter().split(markdown)

    assert [c.number for c in chapters] == ["1", "2"]
    assert _BODY_1 in chapters[0].markdown
    assert _BODY_2 in chapters[1].markdown


def test_split_ignores_reused_chapter_number_from_worked_example() -> None:
    """Регрессия на B9: шаги внутри примера ("1. Исходные данные.") переиспользуют
    номера уже открытых глав — не должны порождать новую главу/дубликат номера."""
    markdown = (
        "## 1 ОБЩИЕ ПОЛОЖЕНИЯ\n"
        f"{_BODY_1}\n"
        "## 2 ПОРЯДОК ОПРЕДЕЛЕНИЯ\n"
        f"{_BODY_2}\n"
        "## 5.8.2. Здания категории Б\n"
        "## Пример 23\n"
        "## 1. Исходные данные.\n"
        "Шаг решения примера содержит достаточно слов, чтобы не считаться пустой главой.\n"
        "## 2. Определение категории здания.\n"
        "Ещё один шаг решения тоже содержит достаточно слов для той же цели проверки.\n"
        "## 5.8.3. Здания категории В\n"
        "Текст следующей главы тоже должен быть достаточно длинным для этой проверки регрессии.\n"
    )

    chapters = ChapterSplitter().split(markdown)

    numbers = [c.number for c in chapters]
    assert numbers == ["1", "2", "5.8.2", "5.8.3"]
    assert len(numbers) == len(set(numbers)), "chapter_number должен быть уникален для bulk_insert_chapters"

    body_5_8_2 = next(c for c in chapters if c.number == "5.8.2").markdown
    assert "Шаг решения примера" in body_5_8_2
    assert "Ещё один шаг решения" in body_5_8_2


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


def test_bodyless_chapter_with_children_is_not_merged() -> None:
    """Регрессия: глава с короткой вводной частью, но с настоящими подглавами
    дальше ("4" перед "4.1"-"4.4") - это организующий заголовок, а не пункт-сирота.
    Раньше _merge_bodyless_chapters сливала такую главу в конец предыдущей
    (нашли на реальном документе: "4" уехала в конец "3", "5" - в конец "4.4")."""
    markdown = (
        "## 3 Термины\n"
        f"{_BODY_1}\n"
        "## 4 Основные положения\n"
        "## 4.1 Первая подглава\n"
        f"{_BODY_2}\n"
        "## 4.2 Вторая подглава\n"
        f"{_BODY_1}\n"
    )

    chapters = ChapterSplitter().split(markdown)

    numbers = [c.number for c in chapters]
    assert numbers == ["3", "4", "4.1", "4.2"], "глава 4 не должна сливаться с 3, у неё есть подглавы"


def test_bodyless_chapter_without_children_is_merged() -> None:
    """Пункт-сирота без своего тела и без подглав (например, короткая ссылка на
    ГОСТ в разделе "Термины и определения") - действительно сливается с предыдущей."""
    markdown = (
        "## 3 Термины\n"
        f"{_BODY_1}\n"
        "## 3.25 Короткий термин\n"
        "## 4 Следующая глава\n"
        f"{_BODY_2}\n"
    )

    chapters = ChapterSplitter().split(markdown)

    numbers = [c.number for c in chapters]
    assert numbers == ["3", "4"], "3.25 без тела и без подглав должна слиться с 3"
    assert "3.25 Короткий термин" in chapters[0].markdown


def test_parse_abbreviation_section_spaced_dash_format() -> None:
    """Реальный формат СТО (проверено живьём в MinIO): "ACRO - expansion;",
    заголовок и вводное предложение без "acronym - expansion" пропускаются."""
    markdown = (
        "## 4 Сокращения\n\n"
        "В настоящем стандарте применены следующие сокращения:\n\n"
        "генподрядчик - генеральный подрядчик;\n\n"
        "ГСМ - горюче-смазочные масла;\n\n"
        "ПНР - пусконаладочные работы;\n\n"
        "ЭХЗ - электрохимзащита.\n\n"
    )

    pairs = parse_abbreviation_section(markdown)

    assert pairs == [
        ("генподрядчик", "генеральный подрядчик"),
        ("ГСМ", "горюче-смазочные масла"),
        ("ПНР", "пусконаладочные работы"),
        ("ЭХЗ", "электрохимзащита"),
    ]


def test_parse_abbreviation_section_no_space_before_dash_format() -> None:
    """Другой реальный формат (второй проверенный документ): "ACRO -expansion ;",
    без пробела перед дефисом, включая многословный acronym с OCR-разрядкой
    ("ИУС ДУ") и стороннюю "пробел+дефис" внутри самой расшифровки, которая не
    должна разрезать пару повторно (нежадный acronym стопорится на первом "\\s-")."""
    markdown = (
        "#### 4 Сокращения\n\n"
        "ЕСТД -единая система технической документации ;\n\n"
        "ИУС ДУ -информационно -управляющая система диспетчерского управления ;\n\n"
        "ТТЗ -тактико -техническое задание .\n\n"
    )

    pairs = parse_abbreviation_section(markdown)

    assert pairs == [
        ("ЕСТД", "единая система технической документации"),
        ("ИУС ДУ", "информационно -управляющая система диспетчерского управления"),
        ("ТТЗ", "тактико -техническое задание"),
    ]


def test_parse_abbreviation_section_empty_input() -> None:
    assert parse_abbreviation_section("") == []


def _abbreviations_section(markdown: str) -> str | None:
    sections = MetaSectionExtractor().extract(markdown)
    match = next((s for s in sections if s.section_type == "ABBREVIATIONS"), None)
    return match.markdown if match else None


def test_meta_section_extractor_finds_simple_numbered_heading() -> None:
    markdown = "## 4 Сокращения\n\nПНР - пусконаладочные работы;\n"
    result = _abbreviations_section(markdown)
    assert result is not None
    assert "ПНР" in result


def test_meta_section_extractor_finds_subchapter_with_compound_number() -> None:
    """Регрессия на живой баг: "4.2 Сокращения" (составной номер подглавы) не
    матчился вообще - ловился только "4 Сокращения" (простой номер главы)."""
    markdown = "#### 4.2 Сокращения\n\nПНР - пусконаладочные работы;\n"
    result = _abbreviations_section(markdown)
    assert result is not None
    assert "ПНР" in result


def test_meta_section_extractor_finds_heading_where_word_is_not_first() -> None:
    """Регрессия на реальный живой документ (проверено в БД): заголовок "3 Термины
    и определения, сокращения" - слово "сокращения" не сразу после номера, а в
    конце составного заголовка. ABBREVIATIONS-секция для такого документа раньше
    не извлекалась вообще (section_type пуст в document_meta_sections)."""
    markdown = "## 3 Термины и определения, сокращения\n\nПНР - пусконаладочные работы;\n"
    result = _abbreviations_section(markdown)
    assert result is not None
    assert "ПНР" in result


def test_meta_section_extractor_another_real_combined_heading() -> None:
    markdown = "## 3 Термины, определения, обозначения и сокращения\n\nПНР - пусконаладочные работы;\n"
    result = _abbreviations_section(markdown)
    assert result is not None


def test_meta_section_extractor_does_not_false_positive_on_terms_without_abbreviations() -> None:
    markdown = "## 3 Термины и определения\n\nОбычный текст главы про термины.\n"
    assert _abbreviations_section(markdown) is None
