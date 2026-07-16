import enum
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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


class RetrieveRequest(BaseModel):
    queries: list[str] = Field(..., min_length=1, description="One or more search queries")
    top_k: int = Field(default=5, ge=1, le=50)

    @field_validator("queries")
    @classmethod
    def validate_queries(cls, values: list[str]) -> list[str]:
        result = [v.strip() for v in values if v.strip()]
        if not result:
            raise ValueError("queries cannot be empty")
        return result


class RetrieveItemMetadata(BaseModel):
    """Document reference metadata: source document, page, and search score."""
    doc_id: str
    parent_id: str
    page_num: str | None = None
    score: float
    headers: dict[str, Any] = Field(default_factory=dict)


class ChildChunk(BaseModel):
    """A single child chunk from Qdrant — relevant text fragment with its similarity score."""
    text: str
    score: float


class RetrieveItem(BaseModel):
    """One RAG search result: matched child chunks, full parent text, and document metadata."""
    child_chunks: list[ChildChunk]
    parent_chunk: str
    metadata: RetrieveItemMetadata


class RetrieveResponse(BaseModel):
    items: list[RetrieveItem]
    total: int


class DocumentSummaryResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    created_at: datetime
    chunk_count: int | None = None


class ChapterSummary(BaseModel):
    chapter_number: str
    title: str


class TableSummary(BaseModel):
    table_index: int


class DocumentDetailResponse(DocumentSummaryResponse):
    file_hash: str | None = None
    s3key: str | None = None
    meta: dict[str, Any] | None = None
    chapters: list[ChapterSummary] = Field(default_factory=list)
    tables: list[TableSummary] = Field(default_factory=list)


class DocumentStatusResponse(BaseModel):
    doc_id: str
    status: str
    filename: str
    created_at: datetime
    chunk_count: int | None = None


class UploadedFileInfo(BaseModel):
    doc_id: str
    filename: str
    s3key: str
    size: int
    status: str


class DuplicateFileInfo(BaseModel):
    doc_id: str
    filename: str
    status: str
    reason: Literal["duplicate_file_hash"]


class UploadDocumentResponse(BaseModel):
    uploaded: int
    skipped: int
    files: list[UploadedFileInfo] = Field(default_factory=list)
    duplicates: list[DuplicateFileInfo] = Field(default_factory=list)


class DeleteDocumentResponse(BaseModel):
    status: Literal["deleted"]
    doc_id: str


class BatchDeleteErrorItem(BaseModel):
    doc_id: str
    reason: str


class BatchDeleteDocumentsRequest(BaseModel):
    doc_ids: list[str] = Field(..., min_length=1)


class BatchDeleteDocumentsResponse(BaseModel):
    deleted: list[str] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)
    failed: list[BatchDeleteErrorItem] = Field(default_factory=list)


class PlaceholderActionResponse(BaseModel):
    status: Literal["not_implemented"]
    action: str
    detail: str


class UploadFileResponse(BaseModel):
    doc_id: str
    presigned_url: str


class S3Object(BaseModel):
    key: str

class S3Data(BaseModel):
    object: S3Object

class MinioRecord(BaseModel):
    s3: S3Data

class MinioWebhookEvent(BaseModel):
    # MinIO присылает список записей в поле "Records"
    records: list[MinioRecord] = Field(..., alias="Records")


