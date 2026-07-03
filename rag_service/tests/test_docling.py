import logging
import re
import time
from pathlib import Path

import pandas as pd
from pypdf import PdfReader, PdfWriter

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,  # используется при do_ocr = True
    PdfPipelineOptions,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

_log = logging.getLogger(__name__)

INPUT_FILE = Path("126.pdf")
OUTPUT_DIR = Path("scratch126")

HEADING = re.compile(r"^#{1,6}\s+")
TOC_HEADING = re.compile(r"^#{1,6}\s+(Содержание|Оглавление)\s*$", re.IGNORECASE)
ABBREV_HEADING = re.compile(r"^#{1,6}\s+(\d+\s+)?[Сс]окращени", re.IGNORECASE)
APPENDIX_HEADING = re.compile(r"^#{1,6}\s+Приложение\s+\S", re.IGNORECASE)
INTRO_HEADING = re.compile(r"^#{1,6}\s+(Введение|Предисловие)\s*$", re.IGNORECASE)
CHAPTER_HEADING = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\s+\S")

MD_TABLE = re.compile(
    r'\|[^\n]+\|\n\|[-:|\s]+\|\n(?:\|[^\n]+\|\n?)*',
    re.MULTILINE,
)


def _remove_repeated_lines(text: str, min_count: int = 8) -> str:
    """Удаляет строки-повторяющиеся хедеры/футеры (номера страниц, название документа)."""
    from collections import Counter
    lines = text.splitlines()
    counts = Counter(ln.strip() for ln in lines if ln.strip())
    return "\n".join(ln for ln in lines if counts.get(ln.strip(), 0) < min_count)


def _replace_tables_with_links(md: str, doc_filename: str, table_map: dict) -> str:
    """Заменяет инлайн-таблицы markdown на ссылки вида [→ Таблица N](tables/...)."""
    counter = [0]

    def _sub(m: re.Match) -> str:
        idx = counter[0]
        counter[0] += 1
        saved_num = table_map.get(idx)
        if saved_num is not None:
            return f"\n[→ Таблица {saved_num}](tables/{doc_filename}_table_{saved_num}.csv)\n"
        return ""

    return MD_TABLE.sub(_sub, md)


def clean_docling_markdown(text_content: str) -> str:
    if not text_content:
        return ""

    cleaned = re.sub(r'/hyphenminus\s*', '- ', text_content)
    # Склейка слов разорванных переносом — через одинарный и двойной перевод строки
    cleaned = re.sub(r'(\w+)-\n([а-яёa-zA-Z])', r'\1\2', cleaned)
    cleaned = re.sub(r'(\w+)-\n\n([а-яёa-zA-Z])', r'\1\2', cleaned)

    lines = []
    for line in cleaned.splitlines():
        line_cleaned = re.sub(r'[ \t\xa0]+', ' ', line).strip()
        lines.append(line_cleaned)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # Склеиваем строку без знака конца предложения с продолжением через пустую строку,
    # если продолжение начинается с маленькой буквы
    cleaned = re.sub(r'([^.!?:»;\n])\n\n([а-яёa-z])', r'\1 \2', cleaned)

    # Несколько пунктов списка на одной строке ("текст; - следующий") → разбиваем
    cleaned = re.sub(r';\s*-\s+', ';\n- ', cleaned)

    # Разделяем слипшиеся определения: "...текст. 3.15 термин:" → перенос строки
    cleaned = re.sub(r'\.\s+(\d+\.\d+(?:\.\d+)*\s+[а-яёa-z])', r'.\n\1', cleaned)

    # Убираем маркер списка перед нумерованными пунктами ("- 5.10 ..." -> "5.10 ...")
    cleaned = re.sub(r'^- (\d)', r'\1', cleaned, flags=re.MULTILINE)

    return cleaned


def _collect_until_next_heading(lines: list[str], start: int) -> list[str]:
    result = [lines[start]]
    for line in lines[start + 1:]:
        if HEADING.match(line.rstrip("\n")):
            break
        result.append(line)
    return result


def extract_sections(md_path: Path, output_dir: Path) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines(keepends=True)
    stem = md_path.stem

    toc_lines: list[str] = []
    abbrev_lines: list[str] = []
    appendix_lines: list[str] = []

    i = 0
    while i < len(lines):
        s = lines[i].rstrip("\n")
        if TOC_HEADING.match(s):
            toc_lines = _collect_until_next_heading(lines, i)
            i += len(toc_lines)
        elif ABBREV_HEADING.match(s):
            abbrev_lines = _collect_until_next_heading(lines, i)
            i += len(abbrev_lines)
        elif APPENDIX_HEADING.match(s):
            appendix_lines = lines[i:]
            break
        else:
            i += 1

    saves = [
        (toc_lines,      f"{stem}_toc.md",        "TOC"),
        (abbrev_lines,   f"{stem}_abbrev.md",      "Abbreviations"),
        (appendix_lines, f"{stem}_appendices.md",  "Appendices"),
    ]
    for collected, filename, label in saves:
        if collected:
            path = output_dir / filename
            path.write_text("".join(collected), encoding="utf-8")
            _log.info(f"{label} saved: {path}")
        else:
            _log.warning(f"Section '{label}' not found.")


def split_into_chapters(md_path: Path, output_dir: Path) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines(keepends=True)
    chapters_dir = output_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    past_intro = False
    current_num: str | None = None
    current_lines: list[str] = []

    def save_current() -> None:
        if current_num is not None and current_lines:
            safe_num = current_num.replace(".", "_")
            path = chapters_dir / f"chapter_{safe_num}.md"
            path.write_text("".join(current_lines), encoding="utf-8")
            _log.info(f"Chapter {current_num} saved: {path}")

    for line in lines:
        s = line.rstrip("\n")

        if not past_intro:
            if INTRO_HEADING.match(s):
                past_intro = True
            continue

        if APPENDIX_HEADING.match(s):
            break

        m = CHAPTER_HEADING.match(s)
        if m:
            save_current()
            current_num = m.group(2)
            current_lines = [line]
        elif current_lines:
            current_lines.append(line)

    save_current()


BATCH_SIZE = 30  # страниц на один проход; уменьши до 15 если снова падает


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(do_cell_matching=True)
    pipeline_options.do_formula_enrichment = False  # VLM на CPU ~18x медленнее, включать только с GPU
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=1, device=AcceleratorDevice.CPU
    )
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )


def _split_pdf_to_batches(input_path: Path, batch_size: int, tmp_dir: Path) -> list[Path]:
    reader = PdfReader(input_path)
    total = len(reader.pages)
    _log.info(f"Total pages: {total}, batch size: {batch_size}")
    batches: list[Path] = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        batch_path = tmp_dir / f"_batch_{start:04d}_{end:04d}.pdf"
        with batch_path.open("wb") as f:
            writer.write(f)
        batches.append(batch_path)
        _log.info(f"Batch {batch_path.name}: pages {start+1}–{end}")
    return batches


def run_pipeline(input_file: Path, output_dir: Path, converter: DocumentConverter) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = input_file.stem

    tmp_dir = output_dir / "_batches"
    tmp_dir.mkdir(exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    batches = _split_pdf_to_batches(input_file, BATCH_SIZE, tmp_dir)

    md_parts: list[str] = []
    table_map: dict[int, int | None] = {}
    global_table_idx = 0
    saved_tables = 0

    start_time = time.time()
    for batch_path in batches:
        _log.info(f"Converting {batch_path.name} ...")
        result = converter.convert(batch_path)

        md_parts.append(result.document.export_to_markdown())

        # Таблицы обрабатываем сразу — не держим ссылку на result.document снаружи
        for table in result.document.tables:
            df: pd.DataFrame = table.export_to_dataframe(doc=result.document)
            if df.shape[0] < 2 or df.shape[1] < 2:
                table_map[global_table_idx] = None
            else:
                saved_tables += 1
                table_map[global_table_idx] = saved_tables
                df.to_csv(tables_dir / f"{doc_filename}_table_{saved_tables}.csv", encoding="utf-8", index=False)
                (tables_dir / f"{doc_filename}_table_{saved_tables}.html").write_text(
                    table.export_to_html(doc=result.document), encoding="utf-8"
                )
                _log.info(f"Table {saved_tables}: {df.shape[0]}×{df.shape[1]}")
            global_table_idx += 1

        del result  # освобождаем тяжёлые структуры батча

    _log.info(f"All batches done in {time.time() - start_time:.2f}s")

    raw_md = "\n\n".join(md_parts)
    del md_parts

    raw_md = _remove_repeated_lines(raw_md)
    raw_md = _replace_tables_with_links(raw_md, doc_filename, table_map)
    cleaned_md = clean_docling_markdown(raw_md)
    del raw_md

    md_path = output_dir / f"{doc_filename}.md"
    md_path.write_text(cleaned_md, encoding="utf-8")
    (output_dir / f"{doc_filename}.txt").write_text(cleaned_md, encoding="utf-8")

    extract_sections(md_path, output_dir)
    split_into_chapters(md_path, output_dir)

    _log.info(f"Results saved to: {output_dir.resolve()}")


def main():
    logging.basicConfig(level=logging.INFO)
    converter = _build_converter()
    run_pipeline(INPUT_FILE, OUTPUT_DIR, converter)


if __name__ == "__main__":
    main()