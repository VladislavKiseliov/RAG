import os
import re
import uuid
import hashlib
import pymupdf4llm
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter


class DocumentProcessor:
    def __init__(self, chunk_size=1000, chunk_overlap=50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.seen_hashes = set()

    def get_content_hash(self, text: str) -> str:
        normalized = re.sub(r'\s+', '', text)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def fix_spaced_text(self, text: str) -> str:
        pattern = r'(?:[а-яА-ЯёЁ]\s){2,}[а-яА-ЯёЁ]'
        return re.sub(pattern, lambda m: m.group(0).replace(" ", ""), text)

    def is_table_of_contents(self, text: str) -> bool:
        toc_keywords = ['СОДЕРЖАНИЕ', 'ОГЛАВЛЕНИЕ', 'TABLE OF CONTENTS', 'СПИСОК РАЗДЕЛОВ']
        if any(kw in text.upper()[:150] for kw in toc_keywords):
            return True
        lines = text.split('\n')
        toc_patterns = [l for l in lines if re.search(r'\.{3,}\s*\d+', l)]
        return len(toc_patterns) > 2

    def clean_content(self, text: str) -> str:
        text = self.fix_spaced_text(text)
        text = re.sub(r'(?i)Page \d+ of \d+', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def split_by_physical_pages(self, text: str) -> list:
        pattern = r'\n\s*(\d+)\s*\n'
        parts = re.split(pattern, text)
        pages = []
        if parts[0].strip():
            pages.append({"num": "N/A", "content": parts[0].strip()})
        for i in range(1, len(parts), 2):
            num = parts[i]
            content = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            if content:
                pages.append({"num": num, "content": content})
        return pages

    def split_to_children(self, text: str) -> list:
        point_pattern = r'\n(?=\d+\.\d+(?:\.\d+)*\s)'
        if re.search(r'\d+\.\d+', text):
            items = re.split(point_pattern, text)
            results = [i.strip() for i in items if len(i.strip()) > 20]
            if len(results) > 1:
                return results

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return [c.strip() for c in splitter.split_text(text) if len(c.strip()) > 20]

    def process_document(self, file_path: str):
        """
        Возвращает список родительских объектов.
        Каждый родитель содержит метаданные заголовков, текст страницы и список детей.
        """
        if not os.path.exists(file_path):
            return []

        self.seen_hashes.clear()
        md_text = pymupdf4llm.to_markdown(file_path)

        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
            strip_headers=False
        )
        structural_sections = header_splitter.split_text(md_text)

        all_data = []

        for section in structural_sections:
            pages = self.split_by_physical_pages(section.page_content)

            for page in pages:
                page_text = self.clean_content(page["content"])

                if self.is_table_of_contents(page_text) or len(page_text) < 50:
                    continue

                h = self.get_content_hash(page_text)
                if h in self.seen_hashes:
                    continue
                self.seen_hashes.add(h)

                p_id = str(uuid.uuid4())[:8]

                # Формируем объект родителя
                parent_obj = {
                    "id": p_id,
                    "page_num": page["num"],
                    "headers": section.metadata,
                    "text": page_text,
                    "children": []
                }

                # Нарезаем детей
                child_texts = self.split_to_children(page_text)
                for chunk in child_texts:
                    parent_obj["children"].append({
                        "parent_id": p_id,
                        "text": chunk,
                        "metadata": section.metadata
                    })

                all_data.append(parent_obj)

        return all_data


if __name__ == "__main__":
    processor = DocumentProcessor()
    structured_data = processor.process_document("123.pdf")

    # Пример вывода
    for parent in structured_data[:3]:
        print(f"Родитель ID: {parent['id']} (Стр: {parent['page_num']})")
        print(f"Заголовки: {parent['headers']}")
        print(f"Детей: {len(parent['children'])}")
        print("-" * 20)