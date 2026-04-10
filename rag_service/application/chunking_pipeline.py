from typing import Any

from rag_service.domain.chunking.document_parser import ChildChunkBuilder
from rag_service.domain.chunking.document_parser import ChunkDeduplicator
from rag_service.domain.chunking.document_parser import ContentFilter
from rag_service.domain.chunking.document_parser import ParentChunkBuilder
from rag_service.domain.chunking.document_parser import PdfExtractor
from rag_service.domain.chunking.document_parser import TextCleaner


class DocumentChunkingPipeline:
    """Полный pipeline подготовки parent и child chunks из PDF."""

    def __init__(self) -> None:
        self._extractor = PdfExtractor()
        self._cleaner = TextCleaner()
        self._filter = ContentFilter()
        self._deduplicator = ChunkDeduplicator()
        self._parent_builder = ParentChunkBuilder()
        self._child_builder = ChildChunkBuilder()

    def process(self, file_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        sections = self._extractor.extract(file_path)

        self._deduplicator.reset()

        parents: list[dict[str, Any]] = []
        children: list[dict[str, Any]] = []

        for index, section in enumerate(sections):
            raw_text = str(section.get("text") or "")
            headers = section.get("headers") or {}

            cleaned_text = self._cleaner.clean(raw_text)

            if self._filter.should_skip(cleaned_text):
                continue

            if self._deduplicator.is_duplicate(cleaned_text):
                continue

            parent = self._parent_builder.build(
                text=cleaned_text,
                headers=headers,
                source=file_path,
                block_index=index,
            )
            parents.append(parent)

            child_texts = self._child_builder.build(cleaned_text)
            for child_text in child_texts:
                children.append(
                    {
                        "id": None,
                        "parent_id": parent["id"],
                        "text": child_text,
                        "headers": headers,
                        "source": file_path,
                    }
                )

        return parents, children
