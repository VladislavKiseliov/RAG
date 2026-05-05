from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from rag_service.api.schemas import DocumentStatus


class Base(DeclarativeBase):
    pass




class DocumentListItemDTO(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_file_hash", "file_hash"),
        UniqueConstraint("file_hash", name="uq_documents_file_hash"),
        CheckConstraint(
            "status IN ('pending', 'uploading', 'processing', 'extracting', 'indexing', 'completed', 'error')",
            name="ck_documents_status",
        ),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DocumentStatus.PROCESSING.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # new fields
    minio_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    parent_chunks: Mapped[list["ParentChunks"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ParentChunks(Base):
    __tablename__ = "parent_chunks"
    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", name="uq_parent_chunks_doc_chunk_index"),
        Index("ix_parent_chunks_doc_id", "doc_id"),
        Index("ix_parent_chunks_chunk_index", "chunk_index"),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # new fields
    page_num: Mapped[str | None] = mapped_column(String(32), nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    document: Mapped[DocumentListItemDTO] = relationship(back_populates="parent_chunks")
