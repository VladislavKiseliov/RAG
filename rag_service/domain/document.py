import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from rag_service.api.schemas import DocumentStatus
from rag_service.domain.errors.base import InvalidIngestionStateError, UploadValidationError
from rag_service.settings import settings


@dataclass
class IngestionDocument:
    id: uuid.UUID
    filename: str
    s3_key: str
    file_size: int
    status: DocumentStatus
    file_hash: str | None = field(default=None)
    chunk_count: int | None = field(default=None)

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

        doc_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        s3_key = f"documents/{now:%Y/%m}/{doc_id}{ext}"

        return cls(
            id=doc_id,
            filename=filename,
            s3_key=s3_key,
            file_size=file_size,
            status=DocumentStatus.PENDING,
        )

    def start_processing(self, file_bytes: bytes) -> None:
        """PENDING → PROCESSING. Вычисляет и регистрирует хеш файла."""
        if self.status != DocumentStatus.PENDING:
            raise InvalidIngestionStateError(self.status.value, DocumentStatus.PROCESSING.value)
        self.file_hash = hashlib.sha256(file_bytes).hexdigest()
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