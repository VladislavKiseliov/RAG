from rag_service.application.abbreviation_expander import AbbreviationExpander


def test_expand_passes_through_query_without_known_acronym() -> None:
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["обычный запрос без аббревиатур"])

    assert result == ["обычный запрос без аббревиатур"]


def test_expand_adds_canonical_variant_for_known_acronym() -> None:
    """Регрессия на живой баг: "ПНР" в теле документа не матчится на запрос
    "пусконаладочные работы" - conditional expansion должен закрыть это."""
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["когда начинаются ПНР на объекте"])

    assert result == [
        "когда начинаются ПНР на объекте",
        "когда начинаются ПНР (пусконаладочные работы) на объекте",
    ]


def test_expand_joins_multiple_expansions_for_same_acronym_in_one_variant() -> None:
    """Несколько известных расшифровок одной аббревиатуры (разные документы дают
    разное написание) - максимум 2 варианта запроса, не 3+, все расшифровки в одном."""
    expander = AbbreviationExpander.from_pairs(
        [
            ("ГСМ", "горюче-смазочные масла"),
            ("ГСМ", "горюче -смазочные масла"),
        ]
    )

    result = expander.expand(["расход ГСМ за месяц"])

    assert result == [
        "расход ГСМ за месяц",
        "расход ГСМ (горюче-смазочные масла; горюче -смазочные масла) за месяц",
    ]


def test_expand_ignores_unknown_caps_token() -> None:
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["что такое СНТ"])

    assert result == ["что такое СНТ"]


def test_expand_only_extends_matching_query_in_multi_query_list() -> None:
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["обычный запрос", "сроки ПНР"])

    assert result == [
        "обычный запрос",
        "сроки ПНР",
        "сроки ПНР (пусконаладочные работы)",
    ]


def test_from_pairs_ignores_lowercase_and_multiword_acronyms() -> None:
    """MVP-ограничение (см. ISSUES.md A11): строчные синонимы и многословные
    OCR-разряженные "аббревиатуры" типа "ИУС ДУ" не участвуют в расширении -
    для них нет CAPS-токена, который можно было бы найти в запросе."""
    expander = AbbreviationExpander.from_pairs(
        [
            ("генподрядчик", "генеральный подрядчик"),
            ("ИУС ДУ", "информационно-управляющая система диспетчерского управления"),
        ]
    )

    result = expander.expand(["вопрос про генподрядчик и ИУС ДУ"])

    assert result == ["вопрос про генподрядчик и ИУС ДУ"]


def test_expand_reverse_direction_adds_acronym_for_full_form_query() -> None:
    """Живой баг (см. память table_summary_feature_and_abbreviation_gap): документ
    называет это "ПНР", пользователь спрашивает полной формой "пусконаладочные
    работы" - дословный acronym в теле документа не находился одним dense-поиском."""
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["сроки проведения пусконаладочные работы на объекте"])

    assert result == [
        "сроки проведения пусконаладочные работы на объекте",
        "сроки проведения пусконаладочные работы (ПНР) на объекте",
    ]


def test_expand_reverse_direction_is_case_insensitive() -> None:
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["Пусконаладочные Работы кто выполняет"])

    assert result == [
        "Пусконаладочные Работы кто выполняет",
        "Пусконаладочные Работы (ПНР) кто выполняет",
    ]


def test_expand_reverse_direction_lists_multiple_acronyms_for_same_expansion() -> None:
    expander = AbbreviationExpander.from_pairs(
        [
            ("ПНР", "пусконаладочные работы"),
            ("ПНРБ", "пусконаладочные работы"),
        ]
    )

    result = expander.expand(["график пусконаладочные работы"])

    assert result == [
        "график пусконаладочные работы",
        "график пусконаладочные работы (ПНР; ПНРБ)",
    ]


def test_expand_reverse_direction_matches_genitive_case() -> None:
    """Основная причина перехода на pymorphy3: точное совпадение подстроки не
    находило ничего в косвенных падежах - "пусконаладочных работ" (родительный)
    не совпадает буквально с "пусконаладочные работы" (именительный) из словаря."""
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["сроки пусконаладочных работ на объекте"])

    assert result == [
        "сроки пусконаладочных работ на объекте",
        "сроки пусконаладочных работ (ПНР) на объекте",
    ]


def test_expand_reverse_direction_matches_prepositional_case() -> None:
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["о пусконаладочных работах на объекте"])

    assert result == [
        "о пусконаладочных работах на объекте",
        "о пусконаладочных работах (ПНР) на объекте",
    ]


def test_expand_reverse_direction_does_not_match_unrelated_word_forms() -> None:
    """Лемматизация не должна начать находить всё подряд - без общих лемм в
    начале известной фразы совпадения быть не должно."""
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])

    result = expander.expand(["обычные строительные работы по графику"])

    assert result == ["обычные строительные работы по графику"]


def test_from_pairs_deduplicates_identical_expansions() -> None:
    expander = AbbreviationExpander.from_pairs(
        [
            ("ПНР", "пусконаладочные работы"),
            ("ПНР", "пусконаладочные работы"),
        ]
    )

    result = expander.expand(["сроки ПНР"])

    assert result == ["сроки ПНР", "сроки ПНР (пусконаладочные работы)"]
