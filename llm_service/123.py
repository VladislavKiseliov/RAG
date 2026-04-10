def _build_context(sources: list[dict],max_context_chars) -> str:
    """Собирает строку контекста из sources с лимитом по символам."""
    parts: list[str] = []
    current_size = 0

    for src in sources:
        part = (
            f"[parent_id={src['parent_id']}; page={src['page_num']}; score={src['score']}]\n"
            f"{src['text']}"
        )
        if current_size + len(part) > max_context_chars:
            break
        parts.append(part)
        current_size += len(part)

    return "\n\n".join(parts)