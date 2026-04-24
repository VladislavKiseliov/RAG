"""Unit tests for the lightweight parent/child chunking engine."""

from rag_service.workers.ingestion_service import ChinkingEngine


def test_chinking_engine_produces_parents_and_children_payload():
    """Ensure chunker emits expected parent and child payload structure."""
    engine = ChinkingEngine(child_chunk_size=40, child_chunk_overlap=10)

    pages = [
        {
            "page_num": "1",
            "text": "# Title\n\nThis is a long enough text block for parent chunk creation. "
            "It should be split into multiple child chunks for vectorization.",
        }
    ]

    parents, children = engine.process_document(pages=pages, source="sample.pdf")

    assert len(parents) == 1
    assert len(children) >= 1

    parent = parents[0]
    assert parent["parent_id"]
    assert parent["page_num"] == "1"
    assert isinstance(parent["headers"], dict)

    child = children[0]
    assert child["text"]
    payload = child["payload"]
    assert payload["parent_id"] == parent["parent_id"]
    assert payload["page_num"] == "1"
    assert payload["source"] == "sample.pdf"
