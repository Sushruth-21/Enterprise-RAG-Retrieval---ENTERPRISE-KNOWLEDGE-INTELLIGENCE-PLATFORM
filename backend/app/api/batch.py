from __future__ import annotations
import asyncio
import logging
import time
from typing import List, Optional, Union
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth.security import UserPayload, get_optional_current_user
from app.orchestrator.graph import run_orchestrator
from app.schemas import (
    BatchAnswer,
    BatchQuestion,
    BatchRequest,
    BatchResponse,
    BatchResultItem,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/batch", response_model=BatchResponse, summary="Process multiple questions")
async def batch_process(
    request: BatchRequest,
    user: Optional[UserPayload] = Depends(get_optional_current_user),
) -> BatchResponse:
    """
    Process a list of questions concurrently and return answers with citations.
    Dual-compatible with Person 1 backend tests and Person 4 frontend UI.
    """
    if not request.questions:
        raise HTTPException(status_code=400, detail="No questions provided")
    if len(request.questions) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 questions per batch")

    # Normalize questions into (question_text, question_id)
    normalized_questions: List[tuple[str, str]] = []
    for item in request.questions:
        if isinstance(item, str):
            normalized_questions.append((item.strip(), str(uuid.uuid4())))
        elif isinstance(item, BatchQuestion):
            normalized_questions.append((item.question.strip(), item.question_id))
        elif isinstance(item, dict):
            q_text = item.get("question", "").strip()
            q_id = item.get("question_id") or str(uuid.uuid4())
            normalized_questions.append((q_text, q_id))

    # Determine access scope based on authenticated user or request
    if user:
        if "confidential" in user.access_scopes:
            effective_scope = "confidential"
        elif "internal" in user.access_scopes:
            effective_scope = "internal"
        else:
            effective_scope = "public"
    else:
        effective_scope = request.access_scope or "public"

    batch_id = str(uuid.uuid4())
    t0_overall = time.perf_counter()

    async def process_one(q_text: str, q_id: str) -> tuple[BatchAnswer, BatchResultItem]:
        t0_item = time.perf_counter()
        try:
            resp = await run_orchestrator(
                question=q_text,
                access_scope=effective_scope,
                document_ids=request.document_ids,
                workspace_id=request.workspace_id,
            )
            item_time_ms = max(1, int((time.perf_counter() - t0_item) * 1000))
            cov = "full" if resp.status == "answered" else ("partial" if resp.status == "partially_answered" else "insufficient_evidence")

            ans = BatchAnswer(
                question_id=q_id,
                question=q_text,
                answer=resp.answer,
                status=resp.status,
                citations=resp.citations,
                verified=resp.verification.verified if resp.verification else True,
            )
            res = BatchResultItem(
                id=q_id,
                question=q_text,
                answer=resp.answer,
                coverage=cov,
                execution_time_ms=item_time_ms,
                citations=resp.citations,
            )
            return ans, res
        except Exception as exc:
            logger.error("Batch item %s failed: %s", q_id, exc)
            item_time_ms = max(1, int((time.perf_counter() - t0_item) * 1000))
            ans = BatchAnswer(
                question_id=q_id,
                question=q_text,
                answer="An error occurred processing this question.",
                status="not_covered",
                citations=[],
                verified=False,
            )
            res = BatchResultItem(
                id=q_id,
                question=q_text,
                answer="An error occurred processing this question.",
                coverage="insufficient_evidence",
                execution_time_ms=item_time_ms,
                citations=[],
            )
            return ans, res

    processed = await asyncio.gather(
        *[process_one(q_text, q_id) for q_text, q_id in normalized_questions]
    )

    answers = [p[0] for p in processed]
    results = [p[1] for p in processed]

    overall_ms = max(1, int((time.perf_counter() - t0_overall) * 1000))
    answered = sum(1 for a in answers if a.status == "answered")
    partially = sum(1 for a in answers if a.status == "partially_answered")
    not_covered = sum(1 for a in answers if a.status == "not_covered")
    total = len(answers)
    coverage_rate = round((answered + 0.5 * partially) / max(1, total), 2)

    return BatchResponse(
        batch_id=batch_id,
        workspace_id=request.workspace_id or "default",
        overall_execution_time_ms=overall_ms,
        coverage_rate=coverage_rate,
        results=results,
        answers=answers,
        total=total,
        answered=answered,
        partially_answered=partially,
        not_covered=not_covered,
    )
