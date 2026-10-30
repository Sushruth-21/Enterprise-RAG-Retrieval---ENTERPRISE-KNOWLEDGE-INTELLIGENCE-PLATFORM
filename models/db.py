import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import DocumentStatus, ProcessingStatus


class Base(DeclarativeBase):
    pass


class Document(Base):
    """
    SQLAlchemy database model for a Document entity.
    Maintains document metadata, storage reference, and self-referencing lineage.
    """
    __tablename__ = "documents"

    # Core Identifiers
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
        comment="Organization identifier for multi-tenant isolation",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Logical Identity & Versioning (Decoupled from filename)
    canonical_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Business/Domain entity identifier (e.g. 'CORP-HR-POL-042')",
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    # State & Temporal Validity
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        default=DocumentStatus.CURRENT,
        nullable=False,
        index=True,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Lineage / Supersedes Relationship (Self-Referencing Foreign Key)
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="Points to the prior version this document replaces",
    )

    # Self-referencing lineage relationships
    superseded_document: Mapped[Optional["Document"]] = relationship(
        "Document",
        remote_side=[id],
        backref="superseded_by",
        foreign_keys=[supersedes_id],
    )

    # Original File Reference & Content Integrity
    file_uri: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="S3/Blob storage path, URL, or local file reference",
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of original file to prevent duplicate uploads",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Audit Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_doc_org_canonical_status", "organization_id", "canonical_id", "status"),
        Index("ix_doc_org_file_hash", "organization_id", "file_hash"),
        Index("ix_doc_canonical_effective", "canonical_id", "effective_date"),
    )


class Chunk(Base):
    """
    SQLAlchemy database model for a Document Chunk.
    Contains strict context, order indexing, tenant boundaries, and pgvector retrieval fields.
    """
    __tablename__ = "chunks"

    # Primary and Multi-Tenant Identifiers
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
        comment="Tenant boundary for multi-tenant pgvector queries",
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Document Reference & Ordering
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential order of the chunk within the document",
    )

    # Content & Semantic Lineage
    section_context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Structural heading breadcrumbs, e.g. '1.0 Introduction > 1.2 Scope'",
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of chunk text for incremental embedding",
    )

    # Vector Embedding Pipeline Fields
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        default="BAAI/bge-small-en-v1.5",
        nullable=False,
        comment="Embedding model identifier for incremental updates",
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True,
        comment="Embedding processing status (pending, processing, completed, failed)",
    )

    # Denormalized Status for Fast Filtering
    document_status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        nullable=False,
        index=True,
        comment="Denormalized status for high-throughput vector/BM25 filtering",
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_tenant_retrieval", "organization_id", "document_status", "document_id"),
        Index("ix_chunks_order", "document_id", "chunk_index"),
        Index("ix_chunks_embedding_dedup", "organization_id", "chunk_hash", "embedding_model"),
    )
