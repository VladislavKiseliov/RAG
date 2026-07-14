from __future__ import annotations

import re
from dataclasses import dataclass, field
from langchain_text_splitters import RecursiveCharacterTextSplitter
import uuid
import uuid6
from typing import Any
import hashlib

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

        return False


@dataclass(frozen=True)
class ParentChunk:
    doc_index: int
    text: str
    headers: dict[str, Any]
    source: str
    id: uuid.UUID = field(default_factory=uuid6.uuid7)

    @classmethod
    def create(
            cls,
            *,
            text: str,
            doc_index: int = 0,
            headers: dict[str, Any] | None = None,
            source: str = "",
    ) -> ParentChunk:

        return cls(
            doc_index=doc_index,
            text=text,
            headers=headers or {},
            source=source,
        )


@dataclass(frozen=True)
class ChildChunk:
    text: str


class ChildChunkBuilder:
    """Нарезает parent chunk на child chunks для retrieval."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 40) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "],
        )

    def build(self, text: str) -> list[ChildChunk]:
        # Сначала пробуем резать по структуре нумерованных подпунктов.
        structured_chunks = self._split_by_numbered_points(text)
        if structured_chunks:
            return [ChildChunk(text=chunk) for chunk in structured_chunks]

        # Если явной структуры нет, режем стандартным сплиттером.
        return [
            ChildChunk(text=chunk.strip())
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