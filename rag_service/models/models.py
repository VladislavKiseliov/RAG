"""SQLAlchemy models for rag document ingestion state and stored parent chunks."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for RAG ORM models."""


class DocumentStatus(str, enum.Enum):
    """Lifecycle states of an ingested document."""

    processing = "processing"
    completed = "completed"
    error = "error"


class Documents(Base):
    """Document metadata and ingestion status."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_file_hash", "file_hash"),
        UniqueConstraint("file_hash", name="uq_documents_file_hash"),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum", schema="rag_kernel"),
        nullable=False,
        default=DocumentStatus.processing,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    parent_chunks: Mapped[list["ParentChunks"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ParentChunks(Base):
    """Parent chunks persisted in Postgres for provenance and reconstruction."""

    __tablename__ = "parent_chunks"
    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", name="uq_parent_chunks_doc_chunk_index"),
        Index("ix_parent_chunks_doc_id", "doc_id"),
        Index("ix_parent_chunks_chunk_index", "chunk_index"),
        Index("ix_parent_chunks_parent_id", "parent_id"),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Backward-compatible column from initial schema. Keep filled together with `text`.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_num: Mapped[str | None] = mapped_column(String(32), nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped[Documents] = relationship(back_populates="parent_chunks")
