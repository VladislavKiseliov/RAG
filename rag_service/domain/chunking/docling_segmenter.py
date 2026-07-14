from __future__ import annotations

import re
from typing import Optional

from rag_service.domain.chunking.docling_models import Chapter, MetaSection


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
    """Нарезает тело документа на главы по пронумерованным заголовкам."""

    def __init__(self) -> None:
        self._patterns = _HeadingPatterns()

    def split(self, markdown: str) -> list[Chapter]:
        lines = markdown.splitlines(keepends=True)

        chapters: list[Chapter] = []
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
            if m:
                save_current()
                current_num = m.group(2)
                current_title = f"{m.group(2)} {m.group(3)}".strip()
                current_lines = [line]
            elif current_lines:
                current_lines.append(line)

        save_current()
        return chapters