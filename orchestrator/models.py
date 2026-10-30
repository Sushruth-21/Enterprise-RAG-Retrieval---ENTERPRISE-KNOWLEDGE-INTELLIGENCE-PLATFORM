from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from models.enums import DocumentStatus


class IngestionRequest(BaseModel):
    """
    Input contract for the Ingestion Orchestrator.
    Encapsulates file location, tenant scope, and domain version metadata.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_path: Union[str, Path] = Field(
        ...,
        description="Local filesystem path or accessible URI to raw document",
    )
    organization_id: UUID = Field(
        ...,
        description="Tenant / Organization UUID for permission isolation",
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional human-readable document name (defaults to file title)",
    )
    canonical_id: str = Field(
        ...,
        min_length=1,
        description="Domain entity identifier grouping document versions (e.g. 'HR-POL-042')",
    )
    version: str = Field(
        default="1.0",
        description="Semantic or revision string (e.g., '1.0', '2.1')",
    )
    effective_date: date = Field(
        ...,
        description="Operational/legal effective date of this document version",
    )
    supersedes_id: Optional[UUID] = Field(
        default=None,
        description="Explicit UUID of the predecessor document this version replaces",
    )
    file_uri: Optional[str] = Field(
        default=None,
        description="Cloud storage reference (S3/GCS URI); defaults to stringified file_path",
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type if known upfront (e.g., 'application/pdf')",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Target embedding model identifier for vector generation",
    )
    min_tokens_per_chunk: int = Field(default=500, ge=10)
    max_tokens_per_chunk: int = Field(default=800, ge=50)


class IngestionResult(BaseModel):
    """
    Audit record returned upon ingestion completion.
    """
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    organization_id: UUID
    document_name: str
    canonical_id: str
    version: str
    status: DocumentStatus
    file_hash: str
    total_pages: int
    total_chunks: int
    superseded_chunks_count: int = 0
    superseded_doc_id: Optional[UUID] = None
    processing_time_ms: float
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
