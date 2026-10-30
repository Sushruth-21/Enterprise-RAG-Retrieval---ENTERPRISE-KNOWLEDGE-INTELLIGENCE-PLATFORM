from __future__ import annotations
from datetime import datetime
from typing import Literal, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Core passage / evidence model (shared contract)
# ─────────────────────────────────────────────
class DocumentPassage(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    version: str
    is_current: bool
    section: str
    page: int
    content: str
    access_scope: str = "public"
    score: float = 0.0


# ─────────────────────────────────────────────
# Citation — what goes in the final response
# ─────────────────────────────────────────────
class Citation(BaseModel):
    document_id: str
    document_name: str
    version: str
    section: str
    page: int
    chunk_id: str


# ─────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────
class VerificationResult(BaseModel):
    verified: bool
    unsupported_claims: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    access_scope: str = "public"
    use_local: Optional[bool] = None  # None = auto-route


class ChatResponse(BaseModel):
    answer: str
    status: Literal["answered", "partially_answered", "not_covered"]
    citations: List[Citation] = Field(default_factory=list)
    verification: VerificationResult
    model_used: str
    conversation_id: str


# ─────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────
class DocumentUploadResponse(BaseModel):
    document_id: str
    document_name: str
    status: str
    message: str


class DocumentInfo(BaseModel):
    document_id: str
    document_name: str
    version: str
    is_current: bool
    doc_type: str
    page_count: int
    section_count: int
    uploaded_at: datetime


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int


# ─────────────────────────────────────────────
# Batch processing
# ─────────────────────────────────────────────
class BatchQuestion(BaseModel):
    question: str
    question_id: str


class BatchRequest(BaseModel):
    questions: List[BatchQuestion]
    access_scope: str = "public"


class BatchAnswer(BaseModel):
    question_id: str
    question: str
    answer: str
    status: Literal["answered", "partially_answered", "not_covered"]
    citations: List[Citation] = Field(default_factory=list)
    verified: bool


class BatchResponse(BaseModel):
    answers: List[BatchAnswer]
    total: int
    answered: int
    partially_answered: int
    not_covered: int


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    ollama_available: bool
    cloud_available: bool
    db_connected: bool
    version: str = "1.0.0"
