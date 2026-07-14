from typing import Protocol, runtime_checkable

from rag_service.domain.chunking.docling_models import ConversionOutput


@runtime_checkable
class PdfConversionProvider(Protocol):
    """Протокол движка, конвертирующего PDF в Markdown + извлечённые таблицы.

    Реализация прячет за собой конкретную библиотеку (сейчас — Docling), так что
    её замена не требует изменений в вызывающем коде.
    """

    def convert(self, content: bytes, filename: str) -> ConversionOutput:
        ...