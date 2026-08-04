from rag_service.domain.chunking.docling_text_cleaner import DoclingMarkdownCleaner


def test_clean_replaces_slash_hyphenminus_artifact() -> None:
    cleaner = DoclingMarkdownCleaner()

    result = cleaner.clean("/hyphenminusинвестор")

    assert result == "- инвестор"


def test_clean_replaces_dash_plus_hyphenminus_artifact() -> None:
    """Живой баг: другой документ дал другой вариант той же болячки - настоящий
    "-" уже стоит на месте, а лишний хвост "hyphenminus" остаётся сразу за ним."""
    cleaner = DoclingMarkdownCleaner()

    result = cleaner.clean("- hyphenminus инвестор;")

    assert result == "- инвестор;"


def test_clean_removes_hyphenminus_from_real_document_list() -> None:
    """Регрессия на живой текст из главы 9 "СТО Газпром 2-1.12-802-2014" (см.
    chapters/chapter_9.md в MinIO)."""
    cleaner = DoclingMarkdownCleaner()
    raw = (
        "9.1 В структуру взаимодействия участников ПНР , как правило, должны входить:\n"
        "- hyphenminus инвестор;\n"
        "- hyphenminus заказчик;\n"
        "- hyphenminus генподрядчик по СМР;"
    )

    result = cleaner.clean(raw)

    assert "hyphenminus" not in result
    assert "- инвестор;" in result
    assert "- заказчик;" in result
    assert "- генподрядчик по СМР;" in result


def test_clean_inserts_paragraph_break_before_numbered_clause_glued_by_space() -> None:
    """Docling иногда склеивает соседние пункты через пробел вместо переноса
    строки - должны стать отдельными абзацами (двойной \\n), а не просто
    отдельной строкой того же абзаца (одинарный \\n рендерится markdown'ом
    как пробел, см. читалку "Весь текст")."""
    cleaner = DoclingMarkdownCleaner()
    raw = "Текст первого пункта. 6.1.2 Текст второго пункта."

    result = cleaner.clean(raw)

    assert result == "Текст первого пункта.\n\n6.1.2 Текст второго пункта."


def test_clean_upgrades_existing_single_newline_before_numbered_clause_to_paragraph_break() -> None:
    """Регрессия на живой баг: документ "СТО Газпром 2-2.1-607-2011" уже кладёт
    пункты на отдельные строки через одинарный \\n - тоже должно стать абзацем."""
    cleaner = DoclingMarkdownCleaner()
    raw = (
        "6.1.1 Блок должен изготавливаться в соответствии с требованиями "
        "конструкторской документации и настоящего стандарта.\n"
        "6.1.2 Изготовление блоков должно производиться организациями."
    )

    result = cleaner.clean(raw)

    assert "стандарта.\n\n6.1.2" in result
