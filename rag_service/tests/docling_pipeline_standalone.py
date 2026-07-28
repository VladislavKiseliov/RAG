"""Автономная копия Docling-конвейера rag_service для отдельных экспериментов.

СКОПИРОВАНО 2026-07-27 из:
  - rag_service/infrastructures/repositories/docling_conversion_repository.py (конвертация PDF)
  - rag_service/domain/chunking/docling_text_cleaner.py (очистка markdown)
  - rag_service/domain/chunking/docling_segmenter.py (нарезка на главы + мета-секции)
  - rag_service/domain/chunking/docling_models.py (dataclass'ы)
  - rag_service/application/docling_pipeline.py (оркестрация всех шагов)

Это СНЭПШОТ, не live-импорт из rag_service - специально, чтобы файл можно было
унести в отдельное окружение без остального пакета rag_service (нужны только
внешние зависимости: docling, docling-core, pandas, langchain-text-splitters).
Если оригинал в rag_service поменяется, этот файл сам не обновится - синхронизировать
руками, если нужно перенести изменения сюда.

Использование:
    python docling_pipeline_standalone.py path/to/document.pdf [output_dir]

Без аргументов — берёт INPUT_FILE/OUTPUT_DIR, заданные константами ниже.
"""

from __future__ import annotations

import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional

import pandas as pd

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    HeadingHierarchyOptions,
    PdfPipelineOptions,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.serializer.base import BaseTableSerializer, SerializationResult
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.types.doc.document import DoclingDocument, TableItem
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_log = logging.getLogger("docling_pipeline_standalone")


# ---------------------------------------------------------------------------
# Что конвертировать (правь эти две константы, либо передай путь аргументом CLI)
# ---------------------------------------------------------------------------
INPUT_FILE = Path("input.pdf")
OUTPUT_DIR = Path("docling_experiment_output")

# ---------------------------------------------------------------------------
# Настройки Docling - те же дефолты, что в rag_service/settings.py.
# В проде сейчас DOCLING_DEVICE=cuda (см. .env) - тут CPU по умолчанию,
# чтобы скрипт из коробки запускался где угодно без настройки CUDA-окружения.
# ---------------------------------------------------------------------------
DOCLING_NUM_THREADS = 3
DOCLING_DEVICE = AcceleratorDevice.CPU  # CPU | CUDA | MPS | XPU | AUTO
DOCLING_OCR_BATCH_SIZE = 4
DOCLING_LAYOUT_BATCH_SIZE = 4
DOCLING_TABLE_BATCH_SIZE = 4
DOCLING_QUEUE_MAX_SIZE = 100
# None - Docling сам скачает модели через huggingface_hub при первом запуске
# (медленнее в первый раз). В проде это прогретый путь внутри образа контейнера
# (см. Dockerfile: `docling-tools models download`), тут такого пути обычно нет.
DOCLING_ARTIFACTS_PATH: str | None = None


# ===========================================================================
# rag_service/domain/chunking/docling_models.py
# ===========================================================================

@dataclass(frozen=True)
class SavedTable:
    """Таблица, прошедшая фильтр по размеру и получившая глобальный номер."""

    index: int
    csv_bytes: bytes
    html_bytes: bytes


@dataclass(frozen=True)
class ConversionOutput:
    """Результат конвертации PDF докингом: markdown с уже подставленными
    ссылками вместо таблиц + сами таблицы, готовые к сохранению."""

    markdown: str
    tables: list[SavedTable] = field(default_factory=list)


@dataclass(frozen=True)
class Chapter:
    number: str
    title: str
    markdown: str


@dataclass(frozen=True)
class MetaSection:
    section_type: str  # "TOC" | "ABBREVIATIONS" | "APPENDICES"
    markdown: str


@dataclass(frozen=True)
class ParsedDocument:
    """Итоговый результат всего пайплайна — то, что получает вызывающий код."""

    full_markdown: str
    chapters: list[Chapter] = field(default_factory=list)
    meta_sections: list[MetaSection] = field(default_factory=list)
    tables: list[SavedTable] = field(default_factory=list)


# ===========================================================================
# rag_service/infrastructures/repositories/docling_conversion_repository.py
# ===========================================================================

def _page_range(item: TableItem) -> tuple[int, int] | None:
    """Min/max page number the table's provenance spans, or `None` without provenance."""
    if not item.prov:
        return None
    pages = [p.page_no for p in item.prov]
    return min(pages), max(pages)


class _LinkingTableSerializer(BaseTableSerializer):
    """Заменяет таблицу в markdown ссылкой на CSV/HTML и сохраняет сами файлы —
    в один проход, в момент сериализации таблицы Docling'ом. Без отдельного
    regex-поиска таблиц в готовом тексте — рассинхрон между ссылкой и файлом
    невозможен по построению, потому что это один и тот же объект таблицы.

    Docling режет таблицу, переходящую через границу страницы, на несколько
    отдельных `TableItem` — без склейки получаем 2-3 карточки вместо одной.
    Продолжение почти всегда без своей подписи и с тем же числом колонок, что
    и предыдущая таблица — если вдобавок оно на той же/следующей странице
    (провенанс), считаем это той же таблицей и дописываем строки вместо новой
    карточки. Эвристика, не гарантия: в теории может ошибочно склеить два
    разных подряд идущих таблицы одинаковой формы без подписи.
    """

    def __init__(self, doc_filename: str) -> None:
        self._doc_filename = doc_filename
        self._next_idx = 0
        self.saved_tables: list[SavedTable] = []
        self._last_df: pd.DataFrame | None = None
        self._last_page_range: tuple[int, int] | None = None

    def serialize(
        self,
        *,
        item: TableItem,
        doc_serializer,
        doc: DoclingDocument,
        **kwargs,
    ) -> SerializationResult:
        cap_res = doc_serializer.serialize_captions(item=item, **kwargs)
        caption = f"{cap_res.text}\n\n" if cap_res.text else ""

        df: pd.DataFrame = item.export_to_dataframe(doc=doc)

        # Меньше 2 колонок — это не таблица, а мусорная разметка. Число строк
        # не фильтруем: однострочная таблица (например, одна норма/показатель)
        # реальна и не должна теряться.
        if df.shape[1] < 2:
            return create_ser_result(text=caption, span_source=item)

        page_range = _page_range(item)
        is_continuation = (
            not cap_res.text
            and self._last_df is not None
            and df.shape[1] == self._last_df.shape[1]
            and self._last_page_range is not None
            and page_range is not None
            and page_range[0] - self._last_page_range[1] <= 1
        )

        if is_continuation:
            # pd.concat выравнивает по ИМЕНИ колонки, а не по позиции — у фрагментов
            # одной и той же таблицы на разных страницах имена колонок (первая строка
            # или авто-индекс) обычно не совпадают, что даёт объединение колонок
            # вместо склейки строк (3 колонки → 6). Обнуляем имена на позиционные.
            df_aligned = df.copy()
            df_aligned.columns = self._last_df.columns
            merged_df = pd.concat([self._last_df, df_aligned], ignore_index=True)
            self._last_df = merged_df
            self._last_page_range = (self._last_page_range[0], page_range[1])

            last = self.saved_tables[-1]
            self.saved_tables[-1] = SavedTable(
                index=last.index,
                csv_bytes=merged_df.to_csv(encoding="utf-8", index=False).encode("utf-8"),
                html_bytes=merged_df.to_html(index=False).encode("utf-8"),
            )
            _log.info("Merged page-break continuation into table %d: now %d rows", last.index, merged_df.shape[0])
            return create_ser_result(text="", span_source=item)

        self._next_idx += 1
        idx = self._next_idx
        self._last_df = df
        self._last_page_range = page_range

        csv_bytes = df.to_csv(encoding="utf-8", index=False).encode("utf-8")
        html_bytes = item.export_to_html(doc=doc).encode("utf-8")
        self.saved_tables.append(SavedTable(index=idx, csv_bytes=csv_bytes, html_bytes=html_bytes))

        _log.info("Extracted table %d: %d×%d", idx, df.shape[0], df.shape[1])

        link = f"\n{caption}[→ Таблица {idx}](tables/{self._doc_filename}_table_{idx}.csv)\n"
        return create_ser_result(text=link, span_source=item)


class DoclingConversionRepository:
    """Конвертирует PDF в Markdown через Docling.

    Постраничный батчинг (защита от переполнения памяти на больших файлах)
    делает сам `StandardPdfPipeline` внутри Docling — через очереди между
    стадиями (OCR/layout/таблицы) с ограниченным размером, без ручного
    разрезания PDF на суб-файлы.
    """

    def __init__(
        self,
        num_threads: int = 3,
        device: AcceleratorDevice = AcceleratorDevice.CPU,
        ocr_batch_size: int = 4,
        layout_batch_size: int = 4,
        table_batch_size: int = 4,
        queue_max_size: int = 100,
        artifacts_path: str | None = None,
    ) -> None:
        self._converter = self._build_converter(
            num_threads, device, ocr_batch_size, layout_batch_size, table_batch_size, queue_max_size, artifacts_path
        )

    def _build_converter(
        self,
        num_threads: int,
        device: AcceleratorDevice,
        ocr_batch_size: int,
        layout_batch_size: int,
        table_batch_size: int,
        queue_max_size: int,
        artifacts_path: str | None,
    ) -> DocumentConverter:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # OCR только для областей без текстового слоя (force_full_page_ocr=False)
        pipeline_options.ocr_options = EasyOcrOptions(
            lang=["ru", "en"],
            model_storage_directory=f"{artifacts_path}/EasyOcr" if artifacts_path else None,
        )
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options = TableStructureOptions(do_cell_matching=True)
        pipeline_options.do_formula_enrichment = False
        pipeline_options.do_picture_description = False
        pipeline_options.generate_picture_images = False
        # По умолчанию Docling кладёт все SECTION_HEADER на level=1 (плоско) — включаем
        # реальную иерархию: закладки PDF (если есть) → нумерация (5.8.2 глубже, чем 1.) →
        # шрифт как фолбэк.
        pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True)
        pipeline_options.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=device)
        pipeline_options.ocr_batch_size = ocr_batch_size
        pipeline_options.layout_batch_size = layout_batch_size
        pipeline_options.table_batch_size = table_batch_size
        pipeline_options.queue_max_size = queue_max_size
        pipeline_options.artifacts_path = artifacts_path

        return DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

    def convert(self, content: bytes, filename: str) -> ConversionOutput:
        doc_filename = Path(filename).stem
        table_serializer = _LinkingTableSerializer(doc_filename)

        stream = DocumentStream(name=filename, stream=BytesIO(content))
        result = self._converter.convert(stream)

        markdown = MarkdownDocSerializer(
            doc=result.document, table_serializer=table_serializer
        ).serialize().text
        del result

        return ConversionOutput(markdown=markdown, tables=table_serializer.saved_tables)


# ===========================================================================
# rag_service/domain/chunking/docling_text_cleaner.py
# ===========================================================================

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


# ===========================================================================
# rag_service/domain/chunking/docling_segmenter.py
# ===========================================================================

# Fallback-размер "псевдо-главы" для документов без номерной структуры разделов
# (см. ChapterSplitter.split ниже) - крупнее child-чанка (400 символов в проде),
# чтобы внутри каждой псевдо-главы всё ещё было что порезать дальше на child chunks.
_FALLBACK_CHAPTER_CHUNK_SIZE = 3000
_FALLBACK_CHAPTER_CHUNK_OVERLAP = 200


class _HeadingPatterns:
    """Общие регэкспы для поиска структурных заголовков документа."""

    def __init__(self) -> None:
        self.heading = re.compile(r"^#{1,6}\s+")
        self.toc = re.compile(
            rf"^#{{1,6}}\s+({self._spaced('Содержание')}|{self._spaced('Оглавление')})\s*$", re.IGNORECASE
        )
        self.abbrev = re.compile(
            rf"^#{{1,6}}\s+(\d+\s+)?{self._spaced('Сокращени')}", re.IGNORECASE
        )
        self.appendix = re.compile(
            rf"^#{{1,6}}\s+{self._spaced('Приложение')}\s+\S", re.IGNORECASE
        )
        self.chapter = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\.?\s+(\S.*)$")

    @staticmethod
    def _spaced(word: str) -> str:
        """Допускает разрядку пробелами между буквами (артефакт Docling-OCR)."""
        return r"\s*".join(re.escape(ch) for ch in word)


class MetaSectionExtractor:
    """Извлекает из документа Содержание, Сокращения и Приложения как отдельные секции."""

    def __init__(self) -> None:
        self._patterns = _HeadingPatterns()

    def extract(self, markdown: str) -> list[MetaSection]:
        lines = markdown.splitlines(keepends=True)

        toc_lines: list[str] = []
        abbrev_lines: list[str] = []
        appendix_lines: list[str] = []

        i = 0
        while i < len(lines):
            s = lines[i].rstrip("\n")
            if self._patterns.toc.match(s):
                toc_lines = self._collect_until_next_heading(lines, i)
                i += len(toc_lines)
            elif self._patterns.abbrev.match(s):
                abbrev_lines = self._collect_until_next_heading(lines, i)
                i += len(abbrev_lines)
            elif self._patterns.appendix.match(s):
                appendix_lines = lines[i:]
                break
            else:
                i += 1

        sections = [
            (toc_lines, "TOC"),
            (abbrev_lines, "ABBREVIATIONS"),
            (appendix_lines, "APPENDICES"),
        ]
        return [
            MetaSection(section_type=section_type, markdown="".join(collected))
            for collected, section_type in sections
            if collected
        ]

    def _collect_until_next_heading(self, lines: list[str], start: int) -> list[str]:
        result = [lines[start]]
        for line in lines[start + 1:]:
            if self._patterns.heading.match(line.rstrip("\n")):
                break
            result.append(line)
        return result


class ChapterSplitter:
    """Нарезает тело документа на главы по пронумерованным заголовкам.

    Заточен под нормативку (СП/ГОСТ/ПУЭ) — там разделы всегда пронумерованы
    ("5.2 Требования к..."). Документы без такой структуры (man-страницы,
    статьи, презентации) не матчат паттерн вообще — тогда включается fallback
    на рекурсивный сплиттер (см. _fallback_split ниже), чтобы документ всё
    равно попал в индекс, а не сдался с "нет контента".
    """

    def __init__(self) -> None:
        self._patterns = _HeadingPatterns()
        self._fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_FALLBACK_CHAPTER_CHUNK_SIZE,
            chunk_overlap=_FALLBACK_CHAPTER_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "],
        )

    def split(self, markdown: str) -> list[Chapter]:
        lines = markdown.splitlines(keepends=True)

        chapters: list[Chapter] = []
        seen_numbers: set[str] = set()
        current_num: Optional[str] = None
        current_title: str = ""
        current_lines: list[str] = []

        def save_current() -> None:
            if current_num and current_lines:
                chapters.append(Chapter(number=current_num, title=current_title, markdown="".join(current_lines)))

        for line in lines:
            s = line.rstrip("\n")

            if self._patterns.appendix.match(s):
                break

            m = self._patterns.chapter.match(s)
            # Номер, который уже встречался, — не новая глава, а шум (например,
            # нумерованный шаг внутри примера/расчёта, который в markdown Docling
            # выглядит как обычный заголовок): дописываем его в текущую главу вместо
            # того, чтобы открывать новую и ловить дубликат chapter_number при записи в БД.
            if m and m.group(2) not in seen_numbers:
                save_current()
                current_num = m.group(2)
                seen_numbers.add(current_num)
                current_title = f"{m.group(2)} {m.group(3)}".strip()
                current_lines = [line]
            elif current_lines:
                current_lines.append(line)

        save_current()

        if not chapters:
            return self._fallback_split(markdown)

        return chapters

    def _fallback_split(self, markdown: str) -> list[Chapter]:
        """Документ без единого пронумерованного заголовка - режем весь текст
        рекурсивным сплиттером на несколько псевдо-глав вместо того, чтобы
        сдаваться и не индексировать документ вообще."""
        blocks = [b.strip() for b in self._fallback_splitter.split_text(markdown) if b.strip()]
        return [
            Chapter(number=str(i + 1), title=self._guess_title(block), markdown=block)
            for i, block in enumerate(blocks)
        ]

    @staticmethod
    def _guess_title(block: str) -> str:
        first_line = block.splitlines()[0].strip().lstrip("#").strip()
        return first_line[:80] if first_line else "Без заголовка"


# ===========================================================================
# rag_service/application/docling_pipeline.py
# ===========================================================================

class DocumentConversionPipeline:
    """Оркестрирует полный цикл разбора PDF в структурированный markdown:
    конвертация → очистка → сегментация."""

    def __init__(self, provider: DoclingConversionRepository) -> None:
        self._provider = provider
        self._cleaner = DoclingMarkdownCleaner()
        self._meta_extractor = MetaSectionExtractor()
        self._chapter_splitter = ChapterSplitter()

    def convert_document(self, content: bytes, filename: str) -> ParsedDocument:
        conversion = self._provider.convert(content, filename)

        cleaned_markdown = self._cleaner.remove_repeated_lines(conversion.markdown)
        cleaned_markdown = self._cleaner.clean(cleaned_markdown)

        return ParsedDocument(
            full_markdown=cleaned_markdown,
            chapters=self._chapter_splitter.split(cleaned_markdown),
            meta_sections=self._meta_extractor.extract(cleaned_markdown),
            tables=conversion.tables,
        )


# ===========================================================================
# CLI-обвязка для эксперимента
# ===========================================================================

def run_pipeline(input_file: Path, output_dir: Path) -> ParsedDocument:
    _log.info("Building Docling converter (device=%s)...", DOCLING_DEVICE)
    provider = DoclingConversionRepository(
        num_threads=DOCLING_NUM_THREADS,
        device=DOCLING_DEVICE,
        ocr_batch_size=DOCLING_OCR_BATCH_SIZE,
        layout_batch_size=DOCLING_LAYOUT_BATCH_SIZE,
        table_batch_size=DOCLING_TABLE_BATCH_SIZE,
        queue_max_size=DOCLING_QUEUE_MAX_SIZE,
        artifacts_path=DOCLING_ARTIFACTS_PATH,
    )
    pipeline = DocumentConversionPipeline(provider=provider)

    _log.info("Converting %s...", input_file)
    content = input_file.read_bytes()
    result = pipeline.convert_document(content, input_file.name)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "full.md").write_text(result.full_markdown, encoding="utf-8")

    chapters_dir = output_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    for chapter in result.chapters:
        safe_num = chapter.number.replace(".", "_")
        (chapters_dir / f"chapter_{safe_num}.md").write_text(chapter.markdown, encoding="utf-8")

    if result.tables:
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        for table in result.tables:
            (tables_dir / f"table_{table.index}.csv").write_bytes(table.csv_bytes)
            (tables_dir / f"table_{table.index}.html").write_bytes(table.html_bytes)

    if result.meta_sections:
        meta_dir = output_dir / "meta"
        meta_dir.mkdir(exist_ok=True)
        for section in result.meta_sections:
            (meta_dir / f"{section.section_type.lower()}.md").write_text(section.markdown, encoding="utf-8")

    _log.info(
        "Done: %d chapters, %d tables, %d meta sections. Output -> %s",
        len(result.chapters), len(result.tables), len(result.meta_sections), output_dir,
    )
    return result


def main() -> None:
    input_file = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_FILE
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_DIR

    if not input_file.exists():
        _log.error("Input file not found: %s", input_file)
        sys.exit(1)

    run_pipeline(input_file, output_dir)


if __name__ == "__main__":
    main()