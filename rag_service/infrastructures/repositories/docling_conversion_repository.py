from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

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

from rag_service.domain.chunking.docling_models import ConversionOutput, SavedTable

_log = logging.getLogger(__name__)


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

    Наружу докинг-объекты не отдаёт — только чистые dataclass'ы из domain-слоя.
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
        # шрифт как фолбэк. use_style без generate_parsed_pages молча не сработает — не
        # включаем, use_numbering и так основной сигнал на нормативных документах.
        pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True)
        pipeline_options.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=device)
        pipeline_options.ocr_batch_size = ocr_batch_size
        pipeline_options.layout_batch_size = layout_batch_size
        pipeline_options.table_batch_size = table_batch_size
        pipeline_options.queue_max_size = queue_max_size
        # Прогретые в образе layout/tableformer модели лежат здесь (Dockerfile:
        # `docling-tools models download`) — без artifacts_path Docling резолвит их
        # через huggingface_hub в /root/.cache/huggingface, который перекрыт
        # persistent-volume'ом без этих репозиториев.
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