import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Unified representation of a retrieved document chunk across search methods."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    canonical_id: Optional[str] = None
    version: str
    section_context: str
    page_number: int
    content: str
    score: float
    rank: int = 1
    source_method: str = "hybrid"  # "dense", "sparse", "hybrid", "reranked", "graph"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """Citation metadata attached to an answer or context segment."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    canonical_id: Optional[str] = None
    version: str
    section_context: str
    page_number: int
    text_excerpt: str


class ContextResult(BaseModel):
    """Formatted context assembled for LLM generation with strict citation tracking."""
    context_text: str
    citations: List[Citation]
    chunk_count: int
    token_estimate: int
    total_characters: int
