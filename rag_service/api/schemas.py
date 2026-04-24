import enum
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    error = "error"


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(default=5, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query cannot be empty")
        return value


class RetrievedChunk(BaseModel):
    doc_id: str
    parent_id: str
    page_num: str | None = None
    score: float
    text: str
    headers: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    query: str
    items: list[RetrievedChunk]
    total: int


class DocumentSummaryResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    created_at: datetime
    chunk_count: int | None = None


class DocumentDetailResponse(DocumentSummaryResponse):
    file_hash: str
    minio_key: str | None = None
    meta: dict[str, Any] | None = None


class DocumentStatusResponse(BaseModel):
    doc_id: str
    status: str
    filename: str
    created_at: datetime
    chunk_count: int | None = None


class UploadedFileInfo(BaseModel):
    doc_id: str
    filename: str
    minio_key: str
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


class PlaceholderActionResponse(BaseModel):
    status: Literal["not_implemented"]
    action: str
    detail: str




class UploadFileResponse(BaseModel):
    status_doc: str
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