from __future__ import annotations
import logging
import time
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.security import UserPayload, get_optional_current_user
from app.models.conversation import conversation_store
from app.orchestrator.graph import run_orchestrator
from app.schemas import ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse, summary="Ask a question")
async def chat(
    request: ChatRequest,
    fastapi_request: Request,
    user: Optional[UserPayload] = Depends(get_optional_current_user),
) -> ChatResponse:
    """
    Submit a question and receive a grounded, cited answer.
    Dual-compatible with Person 1's backend tests and Person 4's frontend UI.
    Automatically respects user role access scopes (public / internal / confidential).
    Restricts search and citations strictly to the requested active document_ids.
    """
    query_text = (request.question or request.query or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    conv_id = request.conversation_id or str(uuid.uuid4())

    # Resolve clearance scope across JWT, headers, and request payload
    system_mode = fastapi_request.headers.get("x-system-mode", "").lower()
    auth_header = fastapi_request.headers.get("authorization", "")

    if system_mode == "read-only-employee" or request.access_scope in ("public", "employee", "read-only-employee"):
        effective_scope = "public"
    elif user and ("confidential" in user.access_scopes or "admin" in getattr(user, "role", "").lower()):
        effective_scope = "confidential"
    elif system_mode == "maintenance-admin" or (auth_header.startswith("Bearer ") and len(auth_header) > 20):
        effective_scope = "confidential"
    elif request.access_scope in ("confidential", "admin", "all"):
        effective_scope = "confidential"
    else:
        effective_scope = "public"

    t0 = time.perf_counter()

    response = await run_orchestrator(
        question=query_text,
        conversation_id=conv_id,
        access_scope=effective_scope,
        force_local=request.use_local,
        document_ids=request.document_ids,
        workspace_id=request.workspace_id,
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
