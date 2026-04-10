import json
from pathlib import Path

import pytest

from rag_service.application.chunking_pipeline import DocumentChunkingPipeline


# ????? ????? ???? ? PDF, ??????? ?????? ???????? ????? pipeline.
PDF_PATH = Path(r"D:\Laboratoria\Rag OVER\RagProgramm\docs\СТО Газпром 2-1.12-802-2014 Организация пусконаладочных работ.pdf")

# ???? ????? ???????? parent ? child chunks.
PARENTS_OUTPUT = Path(r"D:\Laboratoria\Rag OVER\RagProgramm\rag_service\tests\chunking_parents_output.txt")
CHILDREN_OUTPUT = Path(r"D:\Laboratoria\Rag OVER\RagProgramm\rag_service\tests\chunking_children_output.txt")


def _format_parent_chunk(index: int, parent: dict) -> str:
    return (
        f"PARENT #{index}\n"
        f"id={parent.get('id')}\n"
        f"doc_index={parent.get('doc_index')}\n"
        f"source={parent.get('source')}\n"
        f"headers={json.dumps(parent.get('headers', {}), ensure_ascii=False)}\n"
        f"text=\n{parent.get('text', '')}\n"
        + ("-" * 80)
        + "\n"
    )



def _format_child_chunk(index: int, child: dict) -> str:
    return (
        f"CHILD #{index}\n"
        f"parent_id={child.get('parent_id')}\n"
        f"source={child.get('source')}\n"
        f"headers={json.dumps(child.get('headers', {}), ensure_ascii=False)}\n"
        f"text=\n{child.get('text', '')}\n"
        + ("-" * 80)
        + "\n"
    )


@pytest.mark.skipif(not PDF_PATH.exists(), reason="????? ???????????? ???? ? PDF ? ????????? PDF_PATH")
def test_chunking_pipeline_dump_to_files():
    pipeline = DocumentChunkingPipeline()

    parents, children = pipeline.process(str(PDF_PATH))

    assert isinstance(parents, list)
    assert isinstance(children, list)
    assert len(parents) > 0, "Pipeline ?? ?????? ?? ?????? parent chunk"
    assert len(children) > 0, "Pipeline ?? ?????? ?? ?????? child chunk"

    parent_text = "".join(
        _format_parent_chunk(index, parent)
        for index, parent in enumerate(parents, start=1)
    )
    child_text = "".join(
        _format_child_chunk(index, child)
        for index, child in enumerate(children, start=1)
    )

    PARENTS_OUTPUT.write_text(parent_text, encoding="utf-8")
    CHILDREN_OUTPUT.write_text(child_text, encoding="utf-8")

    assert PARENTS_OUTPUT.exists()
    assert CHILDREN_OUTPUT.exists()
