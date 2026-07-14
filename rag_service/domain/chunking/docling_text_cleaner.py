from __future__ import annotations

import re
from collections import Counter


class DoclingMarkdownCleaner:
    """Пост-обработка сырого Markdown от артефактов Docling: разорванные слова,
    повторяющиеся колонтитулы, слипшиеся абзацы и списки."""

    def remove_repeated_lines(self, text: str, min_count: int = 8) -> str:
        """Удаляет сквозные повторяющиеся строки (колонтитулы, номера страниц)."""
        lines = text.splitlines()
        counts = Counter(ln.strip() for ln in lines if ln.strip())
        return "\n".join(ln for ln in lines if counts.get(ln.strip(), 0) < min_count)

    def clean(self, text: str) -> str:
        """Склейка разорванных переносом слов, нормализация пробелов, слипшихся абзацев/пунктов."""
        if not text:
            return ""

        cleaned = re.sub(r'/hyphenminus\s*', '- ', text)
        cleaned = re.sub(r'(\w+)-\n([а-яёa-zA-Z])', r'\1\2', cleaned)
        cleaned = re.sub(r'(\w+)-\n\n([а-яёa-zA-Z])', r'\1\2', cleaned)

        lines = [re.sub(r'[ \t\xa0]+', ' ', line).strip() for line in cleaned.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        cleaned = re.sub(r'([^.!?:»;\n])\n\n([а-яёa-z])', r'\1 \2', cleaned)
        cleaned = re.sub(r';\s*-\s+', ';\n- ', cleaned)
        cleaned = re.sub(r'\.\s+(\d+\.\d+(?:\.\d+)*\s+[А-ЯЁа-яёA-Za-z])', r'.\n\1', cleaned)
        cleaned = re.sub(r'^- (\d)', r'\1', cleaned, flags=re.MULTILINE)

        return cleaned