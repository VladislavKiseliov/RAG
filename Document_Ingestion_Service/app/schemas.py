from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Path to a PDF file or a directory with PDFs")
    collection: str = Field(..., min_length=1, description="Qdrant collection name")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata for all chunks")


class IngestResponse(BaseModel):
    job_ids: List[str] = Field(..., description="Celery task ids")
    total: int = Field(..., description="Number of queued tasks")


class JobStatus(BaseModel):
    status: Literal[
        "pending",
        "processing",
        "failed",
        "done",
        "queued",
        "retry",
        "revoked",
        "received",
        "unknown",
    ] = Field(..., description="Current status")
    stats: Optional[Dict[str, Any]] = Field(default=None, description="Task result payload")
    error: Optional[str] = Field(default=None, description="Error details if failed")


class JobItem(BaseModel):
    job_id: str = Field(..., description="Celery task id")
    status: Literal[
        "pending",
        "processing",
        "failed",
        "done",
        "queued",
        "retry",
        "revoked",
        "received",
        "unknown",
    ] = Field(..., description="Current status")
    file_path: Optional[str] = Field(default=None, description="Source file path")
    collection: Optional[str] = Field(default=None, description="Qdrant collection name")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp in UTC")


class JobsListResponse(BaseModel):
    total: int = Field(..., description="Total job ids stored")
    items: List[JobItem]


class RagQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")
    collection: Optional[str] = Field(default=None, description="Qdrant collection name")


class RagSource(BaseModel):
    source: Optional[str] = Field(default=None, description="Source file name")
    page: Optional[int] = Field(default=None, description="1-based page number")
    score: Optional[float] = Field(default=None, description="Similarity score")


class RagAnswerResponse(BaseModel):
    answer: str = Field(..., description="Model answer")
    sources: List[RagSource] = Field(default_factory=list, description="Retrieved sources")
