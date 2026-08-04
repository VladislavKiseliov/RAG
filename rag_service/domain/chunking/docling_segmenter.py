from __future__ import annotations

import re
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_service.domain.chunking.docling_models import Chapter, MetaSection

# Fallback-размер "псевдо-главы" для документов без номерной структуры разделов
# (см. ChapterSplitter.split ниже) - крупнее child-чанка (400 символов, см.
# chunk_builder.py::ChildChunkBuilder), чтобы внутри каждой псевдо-главы всё ещё
# было что порезать на несколько child chunks, а не одну главу на весь документ.
_FALLBACK_CHAPTER_CHUNK_SIZE = 3000
_FALLBACK_CHAPTER_CHUNK_OVERLAP = 200

# Тот же порог, что и ChildChunkBuilder._is_valid (chunk_builder.py) - намеренно.
# Глава, чьё тело (без строки заголовка) короче этого порога, не даст ни одного
# валидного child-чанка вообще - parent_chunk для неё просто не создастся, и
# контент молча пропадёт из поиска (см. ISSUES.md). Пример из реального документа:
# "3.25" в разделе "Термины и определения" СП 2.13130 - однострочная отсылка к
# ГОСТ, добавленная поправкой и потому визуально жирная в PDF (Docling видит
# заголовок), хотя по сути это рядовой пункт списка терминов, а не подглава.
_MIN_CHAPTER_BODY_LENGTH = 80
_MIN_CHAPTER_BODY_WORDS = 10


class _HeadingPatterns:
    """Общие регэкспы для поиска структурных заголовков документа."""

    def __init__(self) -> None:
        self.heading = re.compile(r"^#{1,6}\s+")
        self.toc = re.compile(
            rf"^#{{1,6}}\s+({self._spaced('Содержание')}|{self._spaced('Оглавление')})\s*$", re.IGNORECASE
        )
        # Не привязываемся к формату номера главы вообще (был баг: "4.2 Сокращения" -
        # составной номер подглавы - не матчился, ловился только простой "4 Сокращения").
        # Вместо разбора номера просто ищем слово "Сокращения" где-то в начале строки
        # заголовка - так же ловит и составные подглавы, и заголовки вида "5 Термины,
        # определения и сокращения" (слово не первое).
        self.abbrev = re.compile(
            rf"^#{{1,6}}\s+.{{0,60}}?{self._spaced('Сокращени')}", re.IGNORECASE
        )
        self.appendix = re.compile(
            rf"^#{{1,6}}\s+{self._spaced('Приложение')}\s+\S", re.IGNORECASE
        )
        self.chapter = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\.?\s+(\S.*)$")

    @staticmethod
    def _spaced(word: str) -> str:
        """Допускает разрядку пробелами между буквами (артефакт Docling-OCR)."""
        return r"\s*".join(re.escape(ch) for ch in word)


class MetaSectionExtractor:
    """Извлекает из документа Содержание, Сокращения и Приложения как отдельные секции."""

    def __init__(self) -> None:
        self._patterns = _HeadingPatterns()

    def extract(self, markdown: str) -> list[MetaSection]:
        lines = markdown.splitlines(keepends=True)

        toc_lines: list[str] = []
        abbrev_lines: list[str] = []
        appendix_lines: list[str] = []

        i = 0
        while i < len(lines):
            s = lines[i].rstrip("\n")
            if self._patterns.toc.match(s):
                toc_lines = self._collect_until_next_heading(lines, i)
                i += len(toc_lines)
            elif self._patterns.abbrev.match(s):
                abbrev_lines = self._collect_until_next_heading(lines, i)
                i += len(abbrev_lines)
            elif self._patterns.appendix.match(s):
                appendix_lines = lines[i:]
                break
            else:
                i += 1

        sections = [
            (toc_lines, "TOC"),
            (abbrev_lines, "ABBREVIATIONS"),
            (appendix_lines, "APPENDICES"),
        ]
        return [
            MetaSection(section_type=section_type, markdown="".join(collected))
            for collected, section_type in sections
            if collected
        ]

    def _collect_until_next_heading(self, lines: list[str], start: int) -> list[str]:
        result = [lines[start]]
        for line in lines[start + 1:]:
            if self._patterns.heading.match(line.rstrip("\n")):
                break
            result.append(line)
        return result


# Разделитель — первое вхождение "пробел+дефис" в строке, не фиксированный формат:
# живые документы вперемешку дают "ГСМ - горюче-смазочные масла;" и "ЕСТД -единая
# система...;" (без пробела перед словом), а также многословные "аббревиатуры" с
# OCR-артефактом (лишний пробел внутри слова, напр. "ИУС ДУ -информационно
# -управляющая..."). Нежадный acronym останавливается на первом же "\s-", что для
# "ИУС ДУ" корректно берёт всё до дефиса, а не только "ИУС".
_ABBREV_LINE_RE = re.compile(r"^(?P<acronym>.+?)\s-\s*(?P<expansion>.+?)\s*[;.]?\s*$")


def parse_abbreviation_section(markdown: str) -> list[tuple[str, str]]:
    """Parses (acronym, expansion) pairs out of an extracted ABBREVIATIONS section.

    Lines without the "acronym - expansion" pattern (the section heading, an intro
    sentence like "В настоящем стандарте применены следующие сокращения:", blank
    lines) don't match `_ABBREV_LINE_RE` and are silently skipped.
    """
    pairs: list[tuple[str, str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ABBREV_LINE_RE.match(stripped)
        if not match:
            continue
        acronym = match.group("acronym").strip()
        expansion = match.group("expansion").strip()
        if acronym and expansion:
            pairs.append((acronym, expansion))
    return pairs


class ChapterSplitter:
    """Нарезает тело документа на главы по пронумерованным заголовкам.

    Заточен под нормативку (СП/ГОСТ/ПУЭ) — там разделы всегда пронумерованы
    ("5.2 Требования к..."). Документы без такой структуры (man-страницы,
    статьи, презентации — заголовки вида "## NAME"/"## DESCRIPTION" без цифр)
    не матчат паттерн вообще, split() раньше возвращал пустой список, а
    выше по пайплайну (ingestion_service.py::store_chunks) это трактовалось
    как "в документе нет контента" и обрывало индексацию целиком — хотя
    Docling нормально извлёк текст, просто резать его было не по чему.
    """

    def __init__(self) -> None:
        self._patterns = _HeadingPatterns()
        self._fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_FALLBACK_CHAPTER_CHUNK_SIZE,
            chunk_overlap=_FALLBACK_CHAPTER_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "],
        )

    def split(self, markdown: str) -> list[Chapter]:
        lines = markdown.splitlines(keepends=True)

        chapters: list[Chapter] = []
        seen_numbers: set[str] = set()
        current_num: Optional[str] = None
        current_title: str = ""
        current_lines: list[str] = []

        def save_current() -> None:
            if current_num and current_lines:
                chapters.append(Chapter(number=current_num, title=current_title, markdown="".join(current_lines)))

        for line in lines:
            s = line.rstrip("\n")

            if self._patterns.appendix.match(s):
                break

            m = self._patterns.chapter.match(s)
            # Номер, который уже встречался, — не новая глава, а шум (например,
            # нумерованный шаг внутри примера/расчёта, который в markdown Docling
            # выглядит как обычный заголовок): дописываем его в текущую главу вместо
            # того, чтобы открывать новую и ловить дубликат chapter_number при записи в БД.
            if m and m.group(2) not in seen_numbers:
                save_current()
                current_num = m.group(2)
                seen_numbers.add(current_num)
                current_title = f"{m.group(2)} {m.group(3)}".strip()
                current_lines = [line]
            elif current_lines:
                current_lines.append(line)

        save_current()

        if not chapters:
            return self._fallback_split(markdown)

        return self._merge_bodyless_chapters(chapters)

    @staticmethod
    def _merge_bodyless_chapters(chapters: list[Chapter]) -> list[Chapter]:
        """Глава без собственного тела (см. _MIN_CHAPTER_BODY_LENGTH выше) - не
        самостоятельная тема, а рядовой пункт. Приклеиваем её markdown в конец
        предыдущей главы вместо того, чтобы плодить главы, контент которых потом
        молча потеряется на этапе child-чанкинга.

        Исключение: если у главы дальше по документу есть свои подглавы (номер
        следующих глав начинается с "{number}."), это настоящий родительский
        раздел с короткой вводной частью (например, "4" перед "4.1"-"4.4", или
        "5" перед "5.1"-"5.4") - не пункт-сирота, а организующий заголовок.
        Такую главу не трогаем независимо от длины её собственного тела -
        реальный контент лежит в её подглавах, не в ней самой."""
        merged: list[Chapter] = []
        for index, chapter in enumerate(chapters):
            _, _, body = chapter.markdown.partition("\n")
            body = body.strip()
            has_body = len(body) >= _MIN_CHAPTER_BODY_LENGTH and len(body.split()) >= _MIN_CHAPTER_BODY_WORDS
            has_children = any(
                later.number.startswith(f"{chapter.number}.") for later in chapters[index + 1:]
            )
            if merged and not has_body and not has_children:
                prev = merged[-1]
                merged[-1] = Chapter(number=prev.number, title=prev.title, markdown=prev.markdown + chapter.markdown)
            else:
                merged.append(chapter)
        return merged

    def _fallback_split(self, markdown: str) -> list[Chapter]:
        """Документ без единого пронумерованного заголовка - режем весь текст
        рекурсивным сплиттером на несколько псевдо-глав вместо того, чтобы
        сдаваться и не индексировать документ вообще. Номер главы тут просто
        порядковый индекс (используется как chapter_number в БД - должен быть
        уникален в пределах документа, как и для обычных глав), title -
        начало первой строки блока, чтобы в UI/логах было что показать вместо
        безликого "Раздел N".
        """
        blocks = [b.strip() for b in self._fallback_splitter.split_text(markdown) if b.strip()]
        return [
            Chapter(number=str(i + 1), title=self._guess_title(block), markdown=block)
            for i, block in enumerate(blocks)
        ]

    @staticmethod
    def _guess_title(block: str) -> str:
        first_line = block.splitlines()[0].strip().lstrip("#").strip()
        return first_line[:80] if first_line else "Без заголовка"