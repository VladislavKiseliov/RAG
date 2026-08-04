"""A11 MVP: conditional query expansion for known document abbreviations.

See rag_service/ISSUES.md, section "A11" for the agreed design. Deliberately
simple: no LLM rewrite, no cross-query fusion, no Aho-Corasick automaton - a
query is only ever expanded when it contains a CAPS token that matches a known
acronym (direct index) or the same word sequence as a known expansion, modulo
grammatical case/number via pymorphy3 lemmas (reverse index).
"""

from __future__ import annotations

import re
import threading
from typing import Iterable

from pymorphy3 import MorphAnalyzer

# То же регэксп-условие, что в ISSUES.md: аббревиатура - один "слитный" CAPS-токен
# (буквы/цифры/дефис без пробелов внутри). Многословные записи вроде "ИУС ДУ"
# (см. parse_abbreviation_section) осознанно не участвуют в MVP-расширении -
# отдельного индекса под них нет, см. целевую архитектуру в ISSUES.md.
_CAPS_TOKEN_RE = re.compile(r"\b[А-ЯA-Z0-9-]{2,}\b")
_WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z]+")

# MorphAnalyzer грузит словарь (~секунды доли) - создаём один раз на процесс,
# не на каждый AbbreviationExpander (тесты конструируют его десятками раз).
_morph: MorphAnalyzer | None = None
_morph_lock = threading.Lock()


def _get_morph() -> MorphAnalyzer:
    global _morph
    if _morph is None:
        with _morph_lock:
            if _morph is None:
                _morph = MorphAnalyzer()
    return _morph


def _lemmatize_word(word: str) -> str:
    """Приводит слово к словарной форме (именительный падеж/инфинитив и т.п.).

    Берём первый (наиболее вероятный) разбор pymorphy3 - для нашей задачи
    (сопоставить формы одного и того же слова) редкая неоднозначность разбора
    не критична.
    """
    return _get_morph().parse(word)[0].normal_form


def _lemma_sequence(text: str) -> tuple[str, ...]:
    return tuple(_lemmatize_word(match.group(0).lower()) for match in _WORD_RE.finditer(text))


class AbbreviationExpander:
    """Adds one canonical query variant when a query hits the direct or reverse index.

    Direct index: query contains a known CAPS acronym ("ПНР") -> add its
    expansion ("пусконаладочные работы"). Reverse index: query contains the
    same words as a known expansion, in any grammatical form ("пусконаладочных
    работ", "о пусконаладочных работах") -> add the acronym. This is the
    actual live bug this feature closes: document body says "ПНР", user asks
    with the full phrase in whatever case - a plain substring match (the
    pre-pymorphy3 version of this class) only caught the exact nominative
    wording and missed most real phrasings.
    """

    def __init__(self, entries: dict[str, list[str]]) -> None:
        self._entries = entries  # acronym -> [expansion, ...]
        # первая лемма расшифровки -> [(вся последовательность лемм, [акронимы]), ...]
        self._reverse_by_first_lemma: dict[str, list[tuple[tuple[str, ...], list[str]]]] = {}
        for acronym, expansions in entries.items():
            for expansion in expansions:
                lemmas = _lemma_sequence(expansion)
                if not lemmas:
                    continue
                bucket = self._reverse_by_first_lemma.setdefault(lemmas[0], [])
                for existing_lemmas, acronyms in bucket:
                    if existing_lemmas == lemmas:
                        if acronym not in acronyms:
                            acronyms.append(acronym)
                        break
                else:
                    bucket.append((lemmas, [acronym]))

    @classmethod
    def from_pairs(cls, pairs: Iterable[tuple[str, str]]) -> "AbbreviationExpander":
        """Builds the lookup dict from raw (acronym, expansion) pairs.

        Only keeps pairs where the acronym is a single CAPS token - lowercase
        synonym pairs and multi-word OCR-spaced acronyms are skipped here (for
        both the direct and reverse index, since the reverse index is derived
        from this same filtered dict).
        """
        entries: dict[str, list[str]] = {}
        for acronym, expansion in pairs:
            if not _CAPS_TOKEN_RE.fullmatch(acronym):
                continue
            expansions = entries.setdefault(acronym, [])
            if expansion not in expansions:
                expansions.append(expansion)
        return cls(entries)

    def expand(self, queries: list[str]) -> list[str]:
        """Returns `queries` plus one extra canonical variant per query that matched.

        A query that hits neither index passes through unchanged - no extra
        embedding/search cost for the common case.
        """
        result = list(queries)
        for query in queries:
            canonical = self._build_canonical(query)
            if canonical is not None and canonical not in result:
                result.append(canonical)
        return result

    def _build_canonical(self, query: str) -> str | None:
        # Собираем непересекающиеся правки (start, end, replacement) относительно
        # исходной строки `query` и применяем все разом - иначе смещения после
        # первой же подстановки съезжают и вторая правка попадает не туда.
        ops: list[tuple[int, int, str]] = []

        for match in _CAPS_TOKEN_RE.finditer(query):
            acronym = match.group(0)
            expansions = self._entries.get(acronym)
            if expansions is None:
                continue
            # Несколько известных расшифровок на одну аббревиатуру - не плодим
            # доп. варианты запроса, перечисляем все через "; " в одной подстановке.
            replacement = f"{acronym} ({'; '.join(expansions)})"
            ops.append((match.start(), match.end(), replacement))

        word_matches = list(_WORD_RE.finditer(query))
        word_lemmas = [_lemmatize_word(match.group(0).lower()) for match in word_matches]
        i = 0
        while i < len(word_matches):
            bucket = self._reverse_by_first_lemma.get(word_lemmas[i])
            matched_length = 0
            if bucket:
                for lemma_seq, acronyms in bucket:
                    n = len(lemma_seq)
                    if word_lemmas[i:i + n] == list(lemma_seq):
                        start = word_matches[i].start()
                        end = word_matches[i + n - 1].end()
                        original_phrase = query[start:end]
                        replacement = f"{original_phrase} ({'; '.join(acronyms)})"
                        ops.append((start, end, replacement))
                        matched_length = n
                        break
            i += matched_length if matched_length else 1

        if not ops:
            return None

        ops.sort(key=lambda op: op[0])
        parts: list[str] = []
        cursor = 0
        for start, end, replacement in ops:
            if start < cursor:
                continue  # пересечение с уже применённой правкой - пропускаем
            parts.append(query[cursor:start])
            parts.append(replacement)
            cursor = end
        parts.append(query[cursor:])
        return "".join(parts)
