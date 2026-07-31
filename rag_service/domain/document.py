import enum
import os
import uuid
from dataclasses import dataclass, field
from pathlib import PurePath

import uuid6

from rag_service.domain.errors.base import InvalidIngestionStateError, UploadValidationError
from rag_service.settings import settings


def _sanitize_filename(filename: str) -> str:
    """Normalize uploaded filename and strip path traversal segments."""
    cleaned = filename.replace("\x00", "").replace("\\", "/")
    cleaned = cleaned.split("/")[-1].strip()
    if not cleaned or cleaned in {".", ".."}:
        raise UploadValidationError("Invalid filename")
    return PurePath(cleaned).name


class DocumentStatus(str, enum.Enum):
    # 1. Начальные этапы
    PENDING = "pending"  # Запись создана, ждем начала загрузки
    UPLOAD = "uploading"  # Файл загружен в Хранилище

    # 2. Процессинг
    PROCESSING = "processing"  # Общий статус (уже есть у тебя)
    EXTRACTING = "extracting"  # Идет парсинг текста из PDF/файла
    INDEXING = "indexing"  # Идет генерация эмбеддингов и запись в Qdrant
    DUPLICATE  = "duplicate" # Дупликат документа

    RETRY = "retry"  # Временная ошибка, задача будет перезапущена Celery

    # 3. Финалы
    COMPLETED = "completed"  # Все готово, можно искать по документу
    ERROR = "error"  # Произошла ошибка


@dataclass
class IngestionDocument:
    id: uuid.UUID
    filename: str
    s3key: str
    file_size: int
    status: DocumentStatus
    file_hash: str | None = field(default=None)
    chunk_count: int | None = field(default=None)
    page_count: int | None = field(default=None)

    @classmethod
    def create_new(cls, filename: str, file_size: int) -> "IngestionDocument":
        """Фабричный метод — валидирует метаданные и генерирует S3-ключ."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in settings.upload_allowed_extensions:
            raise UploadValidationError(f"Расширение {ext} не поддерживается.")
        if file_size <= 0:
            raise UploadValidationError("Файл пустой.")
        if file_size > settings.upload_max_size_bytes:
            raise UploadValidationError(f"Файл слишком велик ({file_size} байт). Лимит {settings.upload_max_size_bytes // (1024*1024)}МБ.")

        # Санитизация ДО построения s3key — раньше s3key строился из сырого имени клиента,
        # а _sanitize_filename применялся только позже, к значению для колонки documents.filename
        # (см. application/document_service.py::create_doc). display-имя и реальный
        # MinIO-ключ могли разойтись для имён с "/"/".." (T18 в rag_service/ISSUES.md).
        safe_filename = _sanitize_filename(filename)

        doc_id = uuid6.uuid7()
        s3key = f"{doc_id}/{safe_filename}"

        return cls(
            id=doc_id,
            filename=safe_filename,
            s3key=s3key,
            file_size=file_size,
            status=DocumentStatus.PENDING,
        )

    def start_processing(self) -> None:
        """PENDING → PROCESSING. Вычисляет и регистрирует хеш файла."""
        if self.status != DocumentStatus.PENDING:
            raise InvalidIngestionStateError(self.status.value, DocumentStatus.PROCESSING.value)
        self.status = DocumentStatus.PROCESSING

    def start_extraction(self) -> None:
        """PROCESSING → EXTRACTING."""
        if self.status != DocumentStatus.PROCESSING:
            raise InvalidIngestionStateError(self.status.value, DocumentStatus.EXTRACTING.value)
        self.status = DocumentStatus.EXTRACTING

    def start_indexing(self) -> None:
        """EXTRACTING → INDEXING."""
        if self.status != DocumentStatus.EXTRACTING:
            raise InvalidIngestionStateError(self.status.value, DocumentStatus.INDEXING.value)
        self.status = DocumentStatus.INDEXING

    def complete(self, chunk_count: int) -> None:
        """INDEXING → COMPLETED."""
        if self.status != DocumentStatus.INDEXING:
            raise InvalidIngestionStateError(self.status.value, DocumentStatus.COMPLETED.value)
        self.chunk_count = chunk_count
        self.status = DocumentStatus.COMPLETED

    def mark_duplicate(self) -> None:
        """Любой → DUPLICATE."""
        self.status = DocumentStatus.DUPLICATE

    def reset_for_retry(self) -> None:
        """Любой → PENDING. Вызывается перед Celery retry — задача стартует заново."""
        self.status = DocumentStatus.PENDING

    def fail(self) -> None:
        """Любой → ERROR."""
        self.status = DocumentStatus.ERROR