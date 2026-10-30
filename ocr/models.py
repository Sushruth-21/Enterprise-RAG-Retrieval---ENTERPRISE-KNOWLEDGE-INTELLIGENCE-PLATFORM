from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OCRResult(BaseModel):
    """Normalized output from either offline or online OCR engines."""
    model_config = ConfigDict(from_attributes=True)

    text: str = Field(..., description="Extracted text or formatted markdown content")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Average OCR confidence score")
    engine_used: str = Field(..., description="Engine that produced the result: 'rapidocr_offline' or 'gemini_vision_online'")
    boxes: List[Any] = Field(default_factory=list, description="Bounding polygon coordinates for detected text lines")
    scores: List[float] = Field(default_factory=list, description="Per-line confidence scores")
    lines: List[str] = Field(default_factory=list, description="Individual extracted text lines in reading order")
    duration_ms: float = Field(default=0.0, description="Processing latency in milliseconds")
    fallback_triggered: bool = Field(default=False, description="Whether fail-safe fallback was engaged")
    metadata: Dict[str, Any] = Field(default_factory=dict)
