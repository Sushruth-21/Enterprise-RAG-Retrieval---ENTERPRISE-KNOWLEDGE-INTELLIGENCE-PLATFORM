from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
import uuid
from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────
# Core passage / evidence model (shared contract)
# ─────────────────────────────────────────────
class DocumentPassage(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    version: str = "1.0"
    is_current: bool = True
    section: str = ""
    page: int = 1
    content: str
    access_scope: str = "public"
    score: float = 0.0


# ─────────────────────────────────────────────
# Citation — Dual compatible with Person 1 & Person 4
# ─────────────────────────────────────────────
class Citation(BaseModel):
    id: Optional[str] = None
    document_id: str
    document_name: str
    version: str = "1.0"
    section: str = ""
    page: int = 1
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    snippet: Optional[str] = None
    relevance_score: float = 0.0

    @model_validator(mode="after")
    def populate_dual_fields(self) -> Citation:
        if not self.id:
            self.id = self.chunk_id or str(uuid.uuid4())
        if self.page_number is None:
            self.page_number = self.page
        if not self.snippet:
            self.snippet = self.section or f"Excerpt from {self.document_name} (Page {self.page})"
        if not self.chunk_id:
            self.chunk_id = self.id
        return self


# ─────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────
class VerificationResult(BaseModel):
    verified: bool = True
    unsupported_claims: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Chat — Dual compatible with Person 1 & Person 4
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    # Person 1 uses 'question', Person 4 frontend uses 'query' or 'message'
    question: Optional[str] = None
    query: Optional[str] = None
    message: Optional[str] = None
    workspace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    document_ids: Optional[List[str]] = Field(default_factory=list)
    access_scope: Optional[str] = None
    use_local: Optional[bool] = None

    @model_validator(mode="after")
    def normalize_query(self) -> ChatRequest:
        text = (self.question or self.query or self.message or "").strip()
        if not text:
            raise ValueError("Either 'question', 'query', or 'message' must be provided and non-empty.")
        self.question = text
        self.query = text
        self.message = text
        if not self.access_scope:
            self.access_scope = "public"
        return self


class ChatResponse(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_id: Optional[str] = None
    conversation_id: str
    response: str = ""  # Person 4 frontend field
    answer: str = ""    # Person 1 backend field
    coverage: Literal["full", "partial", "insufficient_evidence"] = "full"
    status: Literal["answered", "partially_answered", "not_covered"] = "answered"
    grounded_doc_count: int = 0
    grounded_document_count: Optional[int] = None
    execution_time_ms: int = 0
    execution_latency_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    citations: List[Citation] = Field(default_factory=list)
    verification: Optional[VerificationResult] = Field(
        default_factory=lambda: VerificationResult(verified=True, unsupported_claims=[])
    )
    model_used: str = "qwen2.5:3b"

    @model_validator(mode="after")
    def sync_dual_fields(self) -> ChatResponse:
        # Sync response and answer
        if self.answer and not self.response:
            self.response = self.answer
        elif self.response and not self.answer:
            self.answer = self.response

        # Sync IDs and latency aliases
        if not self.query_id:
            self.query_id = self.message_id
        if self.latency_ms is None:
            self.latency_ms = self.execution_time_ms
        if self.execution_latency_ms is None:
            self.execution_latency_ms = self.execution_time_ms

        # Sync coverage and status
        if self.status == "answered":
            self.coverage = "full"
        elif self.status == "partially_answered":
            self.coverage = "partial"
        elif self.status == "not_covered":
            self.coverage = "insufficient_evidence"

        # Calculate grounded doc count if not explicitly set
        if not self.grounded_doc_count and self.citations:
            unique_docs = {c.document_id for c in self.citations if c.document_id}
            self.grounded_doc_count = len(unique_docs)
        if self.grounded_document_count is None:
            self.grounded_document_count = self.grounded_doc_count

        return self


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    role: str
    content: str
    coverage: Optional[str] = "full"
    grounded_doc_count: int = 0
    execution_time_ms: int = 0
    citations: List[Any] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    timestamp: Optional[str] = None

    @model_validator(mode="after")
    def sync_timestamp(self) -> ChatMessage:
        if not self.timestamp:
            self.timestamp = self.created_at
        return self


# ─────────────────────────────────────────────
# Documents — Dual compatible with Person 1 & Person 4
# ─────────────────────────────────────────────
class DocumentUploadResponse(BaseModel):
    # Person 4 frontend fields
    id: str
    workspaceId: str = "default"
    name: str
    format: str = "pdf"
    sizeBytes: int = 0
    pageCount: int = 1
    chunkCount: int = 0
    # Person 1 backend fields
    document_id: str
    document_name: str
    status: str = "indexed"
    message: str = "Document processed successfully"
    version_id: Optional[str] = None
    status_url: Optional[str] = None


class DocumentInfo(BaseModel):
    # Person 4 frontend fields
    id: str = ""
    workspaceId: str = "default"
    name: str = ""
    format: str = "txt"
    sizeBytes: int = 0
    pageCount: int = 1
    chunkCount: int = 0
    # Person 1 backend fields
    document_id: str = ""
    document_name: str = ""
    version: str = "1.0"
    is_current: bool = True
    doc_type: str = "txt"
    page_count: int = 1
    section_count: int = 0
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def sync_fields(self) -> DocumentInfo:
        if self.document_id and not self.id:
            self.id = self.document_id
        elif self.id and not self.document_id:
            self.document_id = self.id

        if self.document_name and not self.name:
            self.name = self.document_name
        elif self.name and not self.document_name:
            self.document_name = self.name

        if self.doc_type and not self.format:
            self.format = self.doc_type
        elif self.format and not self.doc_type:
            self.doc_type = self.format

        if self.page_count and self.pageCount == 1:
            self.pageCount = self.page_count
        elif self.pageCount and self.page_count == 1:
            self.page_count = self.pageCount

        if self.section_count and self.chunkCount == 0:
            self.chunkCount = self.section_count
        elif self.chunkCount and self.section_count == 0:
            self.section_count = self.chunkCount

        return self


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo] = Field(default_factory=list)
    total: int = 0


# ─────────────────────────────────────────────
# Batch Processing — Dual compatible with Person 1 & Person 4
# ─────────────────────────────────────────────
class BatchQuestion(BaseModel):
    question: str
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class BatchRequest(BaseModel):
    # Person 4 sends questions: List[str] or Person 1 sends List[BatchQuestion]
    questions: Union[List[str], List[BatchQuestion]]
    workspace_id: Optional[str] = "default"
    document_ids: Optional[List[str]] = Field(default_factory=list)
    access_scope: str = "public"


class BatchAnswer(BaseModel):
    question_id: str
    question: str
    answer: str
    status: Literal["answered", "partially_answered", "not_covered"]
    citations: List[Citation] = Field(default_factory=list)
    verified: bool = True


class BatchResultItem(BaseModel):
    id: str
    question: str
    answer: str
    coverage: Literal["full", "partial", "insufficient_evidence"]
    status: str = "completed"
    execution_time_ms: int = 0
    latency_ms: int = 0
    citations: List[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_latency(self) -> BatchResultItem:
        if self.execution_time_ms and not self.latency_ms:
            self.latency_ms = self.execution_time_ms
        elif self.latency_ms and not self.execution_time_ms:
            self.execution_time_ms = self.latency_ms
        return self


class BatchResponse(BaseModel):
    # Person 4 frontend fields
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = "default"
    overall_execution_time_ms: int = 0
    coverage_rate: float = 1.0
    total_questions: int = 0
    completed_count: int = 0
    results: List[BatchResultItem] = Field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None
    # Person 1 backend fields
    answers: List[BatchAnswer] = Field(default_factory=list)
    total: int = 0
    answered: int = 0
    partially_answered: int = 0
    not_covered: int = 0

    @model_validator(mode="after")
    def sync_batch_summary(self) -> BatchResponse:
        if not self.total_questions:
            self.total_questions = self.total or len(self.results)
        if not self.completed_count:
            self.completed_count = len(self.results) or self.total
        if self.summary is None:
            full_cov = sum(1 for r in self.results if r.coverage == "full")
            part_cov = sum(1 for r in self.results if r.coverage == "partial")
            none_cov = sum(1 for r in self.results if r.coverage == "insufficient_evidence")
            avg_lat = (
                round(sum(r.execution_time_ms for r in self.results) / max(1, len(self.results)))
                if self.results
                else 0
            )
            self.summary = {
                "full_coverage_count": full_cov,
                "partial_coverage_count": part_cov,
                "insufficient_evidence_count": none_cov,
                "avg_latency_ms": avg_lat,
            }
        return self


# ─────────────────────────────────────────────
# Health — Dual compatible with Person 1 & Person 4
# ─────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = "ok"
    latency_ms: int = 0
    latencyMs: Optional[int] = None
    version: str = "1.0.0"
    ollama_available: bool = True
    cloud_available: bool = False
    db_connected: bool = True
    vectorDbStatus: str = "connected"
    modelGroundingStrictness: str = "enforced"

    @model_validator(mode="after")
    def sync_latency(self) -> HealthResponse:
        if self.latency_ms and self.latencyMs is None:
            self.latencyMs = self.latency_ms
        elif self.latencyMs and not self.latency_ms:
            self.latency_ms = self.latencyMs
        return self
