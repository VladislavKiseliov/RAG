from __future__ import annotations

import uuid
from typing import Any



def group_hits_by_parent(
    hits: list[dict],
) -> dict[tuple[str, str], dict]:
    grouped: dict[tuple[str, str], dict] = {}

    for hit in hits:
        payload: dict[str, Any] = hit.get("payload") or {}

        doc_id = str(payload.get("doc_id") or "").strip()
        parent_id = str(payload.get("parent_id") or "").strip()

        if not doc_id or not parent_id:
            continue

        key = (doc_id, parent_id)

        if key not in grouped:
            grouped[key] = {
                "doc_id": doc_id,
                "parent_id": parent_id,
                "page_num": payload.get("page_num"),
                "headers": payload.get("headers") or {},
                "children": [],
            }

        grouped[key]["children"].append(
            {
                "score": float(hit.get("score") or 0.0),
                "payload": payload,
            }
        )

    return grouped


def build_retrieved_items(
    *,
    group_hits: dict[tuple[str, str], dict],
    rows,
) -> list[dict]:

    row_by_key = {(str(row.doc_id), str(row.id)): row for row in rows}

    items: list[dict] = []

    for key, group in group_hits.items():
        row = row_by_key.get(key)
        if row is None:
            continue

        children = group.get("children", [])
        children = sorted(
            children,
            key=lambda child: child["score"],
            reverse=True,
        )

        top_score = children[0]["score"] if children else 0.0
        payload = children[0]["payload"] if children else {}

        items.append(
            {
                "doc_id": str(row.doc_id),
                "parent_id": str(row.id),
                "page_num": str(payload.get("page_num") or row.page_num or "N/A"),
                "headers": payload.get("headers") or row.headers or {},
                "text": row.content,
                "score": round(float(top_score), 6),
                "children": children,
            }
        )

    return items

