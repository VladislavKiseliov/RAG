from __future__ import annotations

from rag_service.domain.chunking.docling_models import ParsedDocument
from rag_service.domain.chunking.docling_segmenter import ChapterSplitter, MetaSectionExtractor
from rag_service.domain.chunking.docling_text_cleaner import DoclingMarkdownCleaner
from rag_service.infrastructures.providers.pdf_conversion_provider import PdfConversionProvider


class DocumentConversionPipeline:
    """Оркестрирует полный цикл разбора PDF в структурированный markdown: конвертация → очистка → сегментация.

    Ничего не пишет на диск/S3 — результат целиком в памяти (`DoclingParseResult`),
    решение о том, куда его сохранять, принимает вызывающий код (см. `IngestionService._store_docling_artifacts`).

    Внутри создаёт четыре класса, каждый отвечает за один шаг конвейера:

    - `PdfConversionProvider` (передаётся через DI, не создаётся здесь) —
      `Protocol`, за которым скрывается `DoclingConversionRepository`: конвертирует
      PDF через Docling (батчинг по страницам — внутри `StandardPdfPipeline`), отдаёт
      сырой markdown + извлечённые таблицы (`ConversionOutput`). Инжектируется, а не
      создаётся напрямую, потому что
      конкретная реализация грузит OCR-модели при инициализации — дорого пересоздавать
      на каждый документ, поэтому в `container.py` это синглтон.
    - `DoclingMarkdownCleaner` — чистит артефакты OCR/Docling в сыром markdown:
      повторяющиеся колонтитулы/номера страниц (`remove_repeated_lines`), разорванные
      переносом слова, слипшиеся абзацы и пункты списков (`clean`).
    - `ChapterSplitter` — режет очищенный markdown на `Chapter` по пронумерованным
      заголовкам (`## 3.2 Название`), начиная с "Введения"/"Предисловия" и до "Приложений".
    - `MetaSectionExtractor` — вытаскивает из markdown три опциональных раздела
      (Содержание, Сокращения, Приложения) как `MetaSection`, не входящие ни в одну главу.

    """

    def __init__(self, provider: PdfConversionProvider) -> None:
        self._provider = provider
        self._cleaner = DoclingMarkdownCleaner()
        self._meta_extractor = MetaSectionExtractor()
        self._chapter_splitter = ChapterSplitter()

    def convert_document(self, content: bytes, filename: str) -> ParsedDocument:
        """Прогоняет PDF через весь конвейер и возвращает готовый к чанкингу результат.

        Args:
            content: Байты PDF-файла (уже скачан из S3, во временный файл не пишем).
            filename: Имя файла — по нему Docling определяет формат документа.

        Returns:
            ParsedDocument: `full_markdown` — очищенный markdown всего документа;
                `chapters` — главы, нарезанные `ChapterSplitter`; `meta_sections` —
                Содержание/Сокращения/Приложения, если найдены; `tables` — таблицы,
                извлечённые Docling'ом при конвертации (без изменений, очистка их не касается).
        """
        conversion = self._provider.convert(content, filename)

        cleaned_markdown = self._cleaner.remove_repeated_lines(conversion.markdown)
        cleaned_markdown = self._cleaner.clean(cleaned_markdown)

        return ParsedDocument(
            full_markdown=cleaned_markdown,
            chapters=self._chapter_splitter.split(cleaned_markdown),
            meta_sections=self._meta_extractor.extract(cleaned_markdown),
            tables=conversion.tables,
        )