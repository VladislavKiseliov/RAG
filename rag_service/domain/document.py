import hashlib
import uuid
from dataclasses import dataclass, field

from rag_service.api.schemas import DocumentStatus
from rag_service.domain.errors.base import InvalidIngestionStateError


@dataclass
class IngestionDocument:
    doc_id: uuid.UUID
    s3_key: str
    status: DocumentStatus
    file_hash: str | None = field(default=None)
    chunk_count: int | None = field(default=None)

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