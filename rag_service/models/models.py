from __future__ import annotations
import uuid
from datetime import datetime

import uuid6
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from rag_service.domain.document import DocumentStatus


class Base(DeclarativeBase):
    pass

class DocumentListItemDTO(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_file_hash", "file_hash"),
        UniqueConstraint("file_hash", name="uq_documents_file_hash"),
        CheckConstraint(
            "status IN ('pending', 'uploading', 'processing', 'extracting', 'indexing', 'completed', 'error','duplicate')",
            name="ck_documents_status",
        ),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DocumentStatus.PROCESSING.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    s3key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    parent_chunks: Mapped[list["ParentChunks"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    document_chapters: Mapped[list["DocumentChapters"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    document_tables: Mapped[list["DocumentTables"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    document_meta_sections: Mapped[list["DocumentMetaSections"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    abbreviations: Mapped[list["Abbreviations"]] = relationship(
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


class DocumentChapters(Base):
    __tablename__ = "document_chapters"
    __table_args__ = (
        UniqueConstraint("doc_id", "chapter_number", name="uq_document_chapters_doc_chapter_number"),
        Index("ix_document_chapters_doc_id", "doc_id"),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_number: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    s3_md_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[DocumentListItemDTO] = relationship(back_populates="document_chapters")


class DocumentTables(Base):
    __tablename__ = "document_tables"
    __table_args__ = (
        UniqueConstraint("doc_id", "table_index", name="uq_document_tables_doc_table_index"),
        Index("ix_document_tables_doc_id", "doc_id"),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    s3_csv_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    s3_html_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.parent_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )

    document: Mapped[DocumentListItemDTO] = relationship(back_populates="document_tables")


class DocumentMetaSections(Base):
    __tablename__ = "document_meta_sections"
    __table_args__ = (
        UniqueConstraint("doc_id", "section_type", name="uq_document_meta_sections_doc_section_type"),
        Index("ix_document_meta_sections_doc_id", "doc_id"),
        CheckConstraint(
            "section_type IN ('TOC', 'ABBREVIATIONS', 'APPENDICES')",
            name="ck_document_meta_sections_section_type",
        ),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_type: Mapped[str] = mapped_column(String(32), nullable=False)
    s3_md_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    document: Mapped[DocumentListItemDTO] = relationship(back_populates="document_meta_sections")


class Abbreviations(Base):
    __tablename__ = "abbreviations"
    __table_args__ = (
        UniqueConstraint("acronym", "expansion", name="uq_abbreviations_acronym_expansion"),
        Index("ix_abbreviations_doc_id", "doc_id"),
        {"schema": "rag_kernel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_kernel.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    acronym: Mapped[str] = mapped_column(Text, nullable=False)
    expansion: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[DocumentListItemDTO] = relationship(back_populates="abbreviations")