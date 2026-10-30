from __future__ import annotations
import logging
import time
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth.security import UserPayload, get_optional_current_user
from app.models.conversation import conversation_store
from app.orchestrator.graph import run_orchestrator
from app.schemas import ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse, summary="Ask a question")
async def chat(
    request: ChatRequest,
    user: Optional[UserPayload] = Depends(get_optional_current_user),
) -> ChatResponse:
    """
    Submit a question and receive a grounded, cited answer.
    Dual-compatible with Person 1's backend tests and Person 4's frontend UI.
    Automatically respects user role access scopes (public / internal / confidential).
    """
    query_text = (request.question or request.query or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    conv_id = request.conversation_id or str(uuid.uuid4())

    # Resolve clearance scope from authenticated user JWT token if available
    if user:
        if "confidential" in user.access_scopes:
            effective_scope = "confidential"
        elif "internal" in user.access_scopes:
            effective_scope = "internal"
        else:
            effective_scope = "public"
    else:
        effective_scope = request.access_scope or "public"

    t0 = time.perf_counter()

    response = await run_orchestrator(
        question=query_text,
        conversation_id=conv_id,
        access_scope=effective_scope,
        force_local=request.use_local,
    )

    execution_time_ms = max(1, int((time.perf_counter() - t0) * 1000))
    response.execution_time_ms = execution_time_ms

    # Enrich the recorded assistant turn with Person 4 frontend metadata
    history = await conversation_store.get_history(conv_id)
    if history and history[-1].role == "assistant":
        history[-1].coverage = response.coverage
        history[-1].grounded_doc_count = response.grounded_doc_count
        history[-1].execution_time_ms = execution_time_ms
        history[-1].citations = [c.model_dump() for c in response.citations]
    elif not history:
        await conversation_store.add_message(conv_id, "user", query_text)
        await conversation_store.add_message(
            conv_id,
            "assistant",
            response.answer,
            coverage=response.coverage,
            grounded_doc_count=response.grounded_doc_count,
            execution_time_ms=execution_time_ms,
            citations=[c.model_dump() for c in response.citations],
        )

    return response


@router.get(
    "/chat/{conversation_id}/history",
    response_model=List[ChatMessage],
    summary="Get conversation history",
)
async def get_history(conversation_id: str) -> List[ChatMessage]:
    """Retrieve structured message history for Person 4's frontend UI."""
    history = await conversation_store.get_history(conversation_id)
    return [
        ChatMessage(
            id=m.id,
            conversation_id=m.conversation_id or conversation_id,
            role=m.role,
            content=m.content,
            coverage=m.coverage,
            grounded_doc_count=m.grounded_doc_count,
            execution_time_ms=m.execution_time_ms,
            citations=m.citations,
            created_at=m.created_at,
            timestamp=m.created_at,
        )
        for m in history
    ]


@router.delete("/chat/{conversation_id}", summary="Clear a conversation")
async def clear_conversation(conversation_id: str):
    await conversation_store.clear(conversation_id)
    return {"message": f"Conversation {conversation_id} cleared"}
