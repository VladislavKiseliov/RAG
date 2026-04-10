import json
from pathlib import Path

import pytest

from rag_service.domain.chunking.document_parser import PdfExtractor


# ????? ????? ???? ? PDF, ??????? ?????? ?????????.
PDF_PATH = Path(r"D:\Laboratoria\Rag OVER\RagProgramm\docs\СТО Газпром 2-1.12-802-2014 Организация пусконаладочных работ.pdf")
OUTPUT_PATH = Path(r"D:\Laboratoria\Rag OVER\RagProgramm\rag_service\tests\pdf_extractor_output.txt")


@pytest.mark.skipif(not PDF_PATH.exists(), reason="????? ???????????? ???? ? PDF ? ????????? PDF_PATH")
def test_pdf_extractor_dump_to_txt():
    extractor = PdfExtractor()
    sections = extractor.extract(str(PDF_PATH))

    assert isinstance(sections, list)
    assert len(sections) > 0, "Extractor ?? ?????? ?? ????? ??????"

    parts = []
    for index, section in enumerate(sections, start=1):
        parts.append(f"SECTION #{index}\n")
        parts.append(f"headers={json.dumps(section.get('headers', {}), ensure_ascii=False)}\n")
        parts.append("text=\n")
        parts.append(f"{section.get('text', '')}\n")
        parts.append("-" * 80)
        parts.append("\n")

    OUTPUT_PATH.write_text("".join(parts), encoding="utf-8")

    assert OUTPUT_PATH.exists()
