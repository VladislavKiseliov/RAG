from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedItem:
    """Один кандидат в ранжированном списке — уже сведённый к тому, что нужно суите
    retrieval для сверки с меткой (см. EVAL_PLAN.md §3.1)."""
    doc_id: str
    chapter_number: str
    parent_chunk: str
    score: float


def _is_relevant(item: RankedItem, *, expected_doc_id: str, expected_chapters: list[str]) -> bool:
    return item.doc_id == expected_doc_id and item.chapter_number in expected_chapters


def hit_at_k(
        items: list[RankedItem], *, expected_doc_id: str, expected_chapters: list[str], k: int,
) -> bool:
    """Попала ли хотя бы одна ожидаемая глава в топ-k."""
    return any(
        _is_relevant(item, expected_doc_id=expected_doc_id, expected_chapters=expected_chapters)
        for item in items[:k]
    )


def mrr(items: list[RankedItem], *, expected_doc_id: str, expected_chapters: list[str]) -> float:
    """1/ранг первого попадания ожидаемой главы, 0 если не найдено."""
    for rank, item in enumerate(items, start=1):
        if _is_relevant(item, expected_doc_id=expected_doc_id, expected_chapters=expected_chapters):
            return 1.0 / rank
    return 0.0


def recall_at_k(
        items: list[RankedItem], *, expected_doc_id: str, expected_chapters: list[str], k: int,
) -> float:
    """Доля ожидаемых глав, покрытых топ-k (recall@k_cand — потолок качества пайплайна)."""
    if not expected_chapters:
        return 0.0
    found = {
        item.chapter_number
        for item in items[:k]
        if item.doc_id == expected_doc_id and item.chapter_number in expected_chapters
    }
    return len(found) / len(expected_chapters)


def anchor_hit(items: list[RankedItem], *, expected_doc_id: str, anchor: str, k: int) -> bool:
    """Встречается ли якорная фраза внутри parent_chunk одного из топ-k (ловит деградацию
    внутри правильной главы — глава найдена, но нужный кусок текста обрезан/не тот)."""
    if not anchor:
        return False
    return any(
        item.doc_id == expected_doc_id and anchor in item.parent_chunk
        for item in items[:k]
    )


def negative_precision(items: list[RankedItem], *, threshold: float) -> bool:
    """Для negative-вопросов: честный отказ — пусто или верхний скор ниже порога no_data."""
    if not items:
        return True
    return items[0].score < threshold