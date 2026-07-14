from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import pandas as pd

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions, TableStructureOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.serializer.base import BaseTableSerializer, SerializationResult
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.types.doc.document import DoclingDocument, TableItem

from rag_service.domain.chunking.docling_models import ConversionOutput, SavedTable

_log = logging.getLogger(__name__)


class _LinkingTableSerializer(BaseTableSerializer):
    """Заменяет таблицу в markdown ссылкой на CSV/HTML и сохраняет сами файлы —
    в один проход, в момент сериализации таблицы Docling'ом. Без отдельного
    regex-поиска таблиц в готовом тексте — рассинхрон между ссылкой и файлом
    невозможен по построению, потому что это один и тот же объект таблицы.
    """

    def __init__(self, doc_filename: str) -> None:
        self._doc_filename = doc_filename
        self._next_idx = 0
        self.saved_tables: list[SavedTable] = []

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

        if df.shape[0] < 2 or df.shape[1] < 2:
            return create_ser_result(text=caption, span_source=item)

        self._next_idx += 1
        idx = self._next_idx

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