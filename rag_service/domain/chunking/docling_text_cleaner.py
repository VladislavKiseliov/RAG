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

        # Docling иногда не может смэпить глиф дефиса-маркера списка на символ и
        # печатает его PostScript-имя "hyphenminus" литералом вместо "-". Раньше
        # ловили только вариант "/hyphenminus" - в другом документе встретился
        # другой вариант той же болячки: символ "-" уже стоит на месте (сам
        # смэпился нормально), а "hyphenminus" - лишний хвост сразу после него
        # ("- hyphenminus инвестор;" вместо "- инвестор;"). Опциональные "-\s*"
        # и "/" в начале съедают оба варианта одной заменой.
        cleaned = re.sub(r'(?:-\s*)?/?hyphenminus\s*', '- ', text)
        cleaned = re.sub(r'(\w+)-\n([а-яёa-zA-Z])', r'\1\2', cleaned)
        cleaned = re.sub(r'(\w+)-\n\n([а-яёa-zA-Z])', r'\1\2', cleaned)

        lines = [re.sub(r'[ \t\xa0]+', ' ', line).strip() for line in cleaned.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        cleaned = re.sub(r'([^.!?:»;\n])\n\n([а-яёa-z])', r'\1 \2', cleaned)
        cleaned = re.sub(r';\s*-\s+', ';\n- ', cleaned)
        # \s+ тут матчит и пробел (склеенные Docling предложения), и уже готовый
        # одинарный \n (Docling и так кладёт пункты на отдельные строки) - в обоих
        # случаях перед новым пронумерованным пунктом должна быть настоящая граница
        # абзаца (двойной \n), а не одинарный перенос, который в markdown-рендере
        # схлопывается обратно в пробел (см. читалку - "Весь текст").
        cleaned = re.sub(r'\.\s+(\d+\.\d+(?:\.\d+)*\s+[А-ЯЁа-яёA-Za-z])', r'.\n\n\1', cleaned)
        cleaned = re.sub(r'^- (\d)', r'\1', cleaned, flags=re.MULTILINE)

        return cleaned