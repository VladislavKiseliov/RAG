# rag_service/core/chunking.py
from __future__ import annotations

import hashlib
import os
import re
import uuid

import pymupdf4llm
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


MIN_CONTENT_LEN = 80
MIN_CONTENT_WORDS = 10


class DocumentProcessor:
    """
    Разбивает PDF/DOCX на parent-чанки (для LLM) и child-чанки (для поиска).

    process_document(file_path) → (parents, children)

    parents  → пишутся в Postgres (parent_chunks)
    children → векторизуются и пишутся в Qdrant
    """

    _header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
        strip_headers=False,
    )
    _child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=40,
        separators=["\n\n", "\n", ". ", "! ", "? ", " "],
    )

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()

    # ── public ────────────────────────────────────────────────

    def process_document(
        self, file_path: str
    ) -> tuple[list[dict], list[dict]]:
        """
        Возвращает (parents, children).

        parents:
            id, doc_index, text, page_num, headers, source

        children:
            id, parent_id, text, page_num, headers, source
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        source = os.path.basename(file_path)
        self._seen_hashes.clear()

        # 1. PDF → Markdown (сохраняет структуру заголовков)
        full_md = pymupdf4llm.to_markdown(file_path)

        # 2. Маппинг страниц для определения page_num
        page_map = self._build_page_map(file_path)

        # 3. Режем по заголовкам
        sections = self._header_splitter.split_text(full_md)

        parents: list[dict] = []
        children: list[dict] = []

        for doc_index, section in enumerate(sections):
            text = self._clean(section.page_content)

            if self._is_noise(text):
                continue

            content_hash = self._hash(text)
            if content_hash in self._seen_hashes:
                continue
            self._seen_hashes.add(content_hash)

            parent_id = str(uuid.uuid4())
            page_num = self._find_page_num(text, page_map)

            parents.append({
                "id":        parent_id,
                "doc_index": doc_index,
                "text":      text,
                "page_num":  page_num,
                "headers":   section.metadata,
                "source":    source,
            })

            for child_text in self._split_children(text):
                children.append({
                    "id":        str(uuid.uuid4()),
                    "parent_id": parent_id,
                    "text":      child_text,
                    "page_num":  page_num,
                    "headers":   section.metadata,
                    "source":    source,
                })

        return parents, children

    # ── private ───────────────────────────────────────────────

    def _build_page_map(self, file_path: str) -> list[dict]:
        """Возвращает [{page: N, text: '...'}] для определения номера страницы."""
        try:
            chunks = pymupdf4llm.to_markdown(file_path, page_chunks=True)
            return [
                {"page": c["metadata"]["page"], "text": c["text"]}
                for c in chunks
            ]
        except Exception:
            return []

    def _find_page_num(self, text: str, page_map: list[dict]) -> str:
        """Определяет страницу по первым 80 символам текста секции."""
        fragment = text[:80]
        for entry in page_map:
            if fragment in entry["text"]:
                return str(entry["page"])
        return "N/A"

    def _split_children(self, text: str) -> list[str]:
        """Нарезает текст на child-чанки. Сначала по нумерованным пунктам, потом по символам."""
        point_pattern = r'\n(?=\d+\.\d+(?:\.\d+)*\s)'
        if re.search(r'\d+\.\d+', text):
            items = re.split(point_pattern, text)
            results = [i.strip() for i in items if self._is_valid(i.strip())]
            if len(results) > 1:
                return results

        return [
            c.strip()
            for c in self._child_splitter.split_text(text)
            if self._is_valid(c.strip())
        ]

    def _clean(self, text: str) -> str:
        """Очистка текста от артефактов PDF."""
        text = self._fix_spaced_cyrillic(text)
        text = re.sub(r'(?i)Page \d+ of \d+', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _fix_spaced_cyrillic(self, text: str) -> str:
        """Убирает пробелы между кириллическими буквами (артефакт PDF)."""
        pattern = r'(?:[а-яА-ЯёЁ]\s){2,}[а-яА-ЯёЁ]'
        return re.sub(pattern, lambda m: m.group(0).replace(" ", ""), text)

    def _is_noise(self, text: str) -> bool:
        """Фильтрует оглавления, короткий текст, строки из точек."""
        if len(text) < MIN_CONTENT_LEN:
            return True
        if len(text.split()) < MIN_CONTENT_WORDS:
            return True
        toc_keywords = ['СОДЕРЖАНИЕ', 'ОГЛАВЛЕНИЕ', 'TABLE OF CONTENTS', 'СПИСОК РАЗДЕЛОВ']
        if any(kw in text.upper()[:200] for kw in toc_keywords):
            return True
        if text.count('.') / max(len(text), 1) > 0.3:
            return True
        return False

    def _is_valid(self, text: str) -> bool:
        return len(text) >= MIN_CONTENT_LEN and len(text.split()) >= MIN_CONTENT_WORDS

    @staticmethod
    def _hash(text: str) -> str:
        normalized = re.sub(r'\s+', '', text)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()