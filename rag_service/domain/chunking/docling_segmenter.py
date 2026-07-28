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


class _HeadingPatterns:
    """Общие регэкспы для поиска структурных заголовков документа."""

    def __init__(self) -> None:
        self.heading = re.compile(r"^#{1,6}\s+")
        self.toc = re.compile(
            rf"^#{{1,6}}\s+({self._spaced('Содержание')}|{self._spaced('Оглавление')})\s*$", re.IGNORECASE
        )
        self.abbrev = re.compile(
            rf"^#{{1,6}}\s+(\d+\s+)?{self._spaced('Сокращени')}", re.IGNORECASE
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

        return chapters

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