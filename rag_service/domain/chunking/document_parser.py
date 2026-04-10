import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

import hashlib
import pymupdf4llm
from langchain_text_splitters import MarkdownHeaderTextSplitter
from typing import Any


class PdfExtractor:
    """Извлекает структурные текстовые секции из PDF."""

    def __init__(self) -> None:
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
            strip_headers=False,
        )

    def extract(self, file_path: str) -> list[dict[str, Any]]:
        """
        Извлекает секции документа в виде списка блоков:
        {
            "text": "...",
            "headers": {...}
        }
        """
        markdown_text = pymupdf4llm.to_markdown(file_path)
        sections = self._header_splitter.split_text(markdown_text)

        result: list[dict[str, Any]] = []
        for section in sections:
            result.append(
                {
                    "text": section.page_content,
                    "headers": section.metadata,
                }
            )

        return result


class TextCleaner:
    """Очищает и нормализует текст документа перед чанкированием."""

    def clean(self, text: str) -> str:
        text = self._fix_spaced_cyrillic(text)
        text = self._remove_common_page_footers(text)
        text = self._normalize_whitespace(text)
        text = self._normalize_blank_lines(text)
        return text.strip()

    def _fix_spaced_cyrillic(self, text: str) -> str:
        """Склеивает кириллические слова, если буквы разделены пробелами."""
        pattern = r"(?:[а-яА-ЯёЁ]\s){2,}[а-яА-ЯёЁ]"
        return re.sub(pattern, lambda m: m.group(0).replace(" ", ""), text)

    def _remove_common_page_footers(self, text: str) -> str:
        """Удаляет типовые пагинационные и footer-строки."""
        patterns = [
            r"(?im)^page\s+\d+\s+of\s+\d+\s*$",
            r"(?im)^стр\.\s*\d+\s*$",
            r"(?im)^страница\s+\d+\s+из\s+\d+\s*$",
            r"(?im)^\s*\d+\s*$",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Схлопывает лишние пробелы и заменяет неразрывные пробелы."""
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def _normalize_blank_lines(self, text: str) -> str:
        """Убирает избыточные пустые строки."""
        return re.sub(r"\n{3,}", "\n\n", text)




class ContentFilter:
    """Отбрасывает текстовые блоки, которые не подходят для чанкирования."""

    def __init__(self, min_length: int = 80, min_words: int = 10) -> None:
        self._min_length = min_length
        self._min_words = min_words

    def should_skip(self, text: str) -> bool:
        # Слишком короткие блоки не несут полезного контекста.
        if len(text) < self._min_length:
            return True

        # Блоки с очень малым числом слов обычно являются шумом.
        if len(text.split()) < self._min_words:
            return True

        # Оглавление и похожие страницы лучше не индексировать.
        if self._is_table_of_contents(text):
            return True

        return False

    def _is_table_of_contents(self, text: str) -> bool:
        """Определяет, похож ли текст на оглавление."""
        toc_keywords = [
            "СОДЕРЖАНИЕ",
            "ОГЛАВЛЕНИЕ",
            "TABLE OF CONTENTS",
            "СПИСОК РАЗДЕЛОВ",
        ]

        if any(keyword in text.upper()[:200] for keyword in toc_keywords):
            return True

        lines = text.split("\n")
        toc_lines = [line for line in lines if re.search(r"\.{3,}\s*\d+", line)]

        return len(toc_lines) > 2


import uuid
from typing import Any


class ParentChunkBuilder:
    """Строит parent chunks из подготовленных текстовых блоков документа."""

    def build(
        self,
        *,
        text: str,
        headers: dict[str, Any] | None = None,
        source: str = "",
        block_index: int = 0,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "doc_index": block_index,
            "text": text,
            "headers": headers or {},
            "source": source,
        }



class ChildChunkBuilder:
    """Нарезает parent chunk на child chunks для retrieval."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 40) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "],
        )

    def build(self, text: str) -> list[str]:
        # Сначала пробуем резать по структуре нумерованных подпунктов.
        structured_chunks = self._split_by_numbered_points(text)
        if structured_chunks:
            return structured_chunks

        # Если явной структуры нет, режем стандартным сплиттером.
        return [
            chunk.strip()
            for chunk in self._splitter.split_text(text)
            if self._is_valid(chunk.strip())
        ]

    def _split_by_numbered_points(self, text: str) -> list[str]:
        """Пробует разбить текст по подпунктам вида 1.1 / 1.2.3."""
        point_pattern = r"\n(?=\d+\.\d+(?:\.\d+)*\s)"

        if not re.search(r"\d+\.\d+", text):
            return []

        parts = re.split(point_pattern, text)
        chunks = [part.strip() for part in parts if self._is_valid(part.strip())]

        return chunks if len(chunks) > 1 else []

    def _is_valid(self, text: str) -> bool:
        """Отсекает слишком короткие child chunks."""
        return len(text) >= 80 and len(text.split()) >= 10


class ChunkDeduplicator:
    """Убирает дублирующиеся или почти одинаковые текстовые блоки."""

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()

    def reset(self) -> None:
        """Сбрасывает состояние перед обработкой нового документа."""
        self._seen_hashes.clear()

    def is_duplicate(self, text: str) -> bool:
        """Проверяет, встречался ли уже такой нормализованный текст."""
        content_hash = self._hash(text)

        if content_hash in self._seen_hashes:
            return True

        self._seen_hashes.add(content_hash)
        return False

    def _hash(self, text: str) -> str:
        """Строит хеш текста без учёта лишних пробелов."""
        normalized = re.sub(r"\s+", "", text)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()