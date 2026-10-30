from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import DocumentStatus, ProcessingStatus


# =====================================================================
# Chunk Models
# =====================================================================
class ChunkModel(BaseModel):
    """
    Pydantic representation of an extracted document chunk.
    Strictly conforms to integration contract with PostgreSQL + pgvector.
    """
    model_config = ConfigDict(from_attributes=True)

    # Identifiers & Multi-Tenancy
    chunk_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the chunk",
    )
    organization_id: UUID = Field(
        ...,
        description="Organization UUID for multi-tenant permission boundaries",
    )
    document_id: UUID = Field(
        ...,
        description="Document ID linking back to the parent Document entity",
    )

    # Document Reference & Sequential Ordering
    document_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Snapshot of the document name at time of chunking",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Version string of the originating document",
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="Sequential 0-indexed order of the chunk within the document",
    )

    # Context & Content
    section_context: str = Field(
        ...,
        description="Section or heading breadcrumb path (e.g., '1. Overview > 1.1 Scope')",
    )
    page_number: int = Field(
        ...,
        ge=1,
        description="1-indexed physical page number where chunk occurs",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Extracted and cleaned textual content of the chunk",
    )
    chunk_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of the chunk text for incremental embedding",
    )

    # Vector Pipeline Fields
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Embedding model identifier for incremental embedding",
    )
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING,
        description="Processing/embedding pipeline status (pending, processing, completed, failed)",
    )

    # Denormalized Parent Status
    document_status: DocumentStatus = Field(
        ...,
        description="Lifecycle status of the parent document (current/superseded)",
    )


# =====================================================================
# Document Models
# =====================================================================
class DocumentBase(BaseModel):
    """Base fields for document definition."""
    organization_id: UUID = Field(
        ...,
        description="Organization UUID for multi-tenant isolation",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable title/name of the document",
    )
    canonical_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Domain/Business identity code (e.g. 'CORP-HR-POL-042') grouping revisions",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Version/Revision code",
    )
    status: DocumentStatus = Field(
        default=DocumentStatus.CURRENT,
        description="Current operational status ('current' or 'superseded')",
    )
    effective_date: date = Field(
        ...,
        description="Date the document takes legal/business effect",
    )
    file_uri: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Original file reference (S3/GCS URI, Blob storage path, or file URI)",
    )
    file_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of original file to prevent duplicate uploads",
    )
    supersedes_id: Optional[UUID] = Field(
        default=None,
        description="ID of the prior document version this document supersedes",
    )
    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="MIME type of the source file (e.g., 'application/pdf')",
    )


class DocumentCreate(DocumentBase):
    """Schema for document registration before ingestion."""
    pass


class DocumentModel(DocumentBase):
    """
    Complete document model including system-generated fields and lineage.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique Document ID",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when document was registered in pipeline",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when document record was last updated",
    )
