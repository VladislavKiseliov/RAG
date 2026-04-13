from __future__ import annotations

from typing import Iterable


def build_context(sources: Iterable[dict], max_context_chars: int) -> str:
    parts: list[str] = []
    current_size = 0

    for src in sources:
        part = (
            f"[parent_id={src['parent_id']}; page={src.get('page_num')}; score={src['score']}]\n"
            f"{src['text']}"
        )
        if current_size + len(part) > max_context_chars:
            break
        parts.append(part)
        current_size += len(part)

    return "\n\n".join(parts)
