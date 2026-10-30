from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.conversation import conversation_store
from app.orchestrator.graph import run_orchestrator
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse, summary="Ask a question")
async def chat(request: ChatRequest) -> ChatResponse:
    """Submit a question and receive a grounded, cited answer."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    response = await run_orchestrator(
        question=request.question,
        conversation_id=request.conversation_id,
        access_scope=request.access_scope,
        force_local=request.use_local,
    )
    return response


@router.get("/chat/{conversation_id}/history", summary="Get conversation history")
async def get_history(conversation_id: str):
    history = await conversation_store.get_history(conversation_id)
    return {
        "conversation_id": conversation_id,
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
            for m in history
        ],
    }


@router.delete("/chat/{conversation_id}", summary="Clear a conversation")
async def clear_conversation(conversation_id: str):
    await conversation_store.clear(conversation_id)
    return {"message": f"Conversation {conversation_id} cleared"}
