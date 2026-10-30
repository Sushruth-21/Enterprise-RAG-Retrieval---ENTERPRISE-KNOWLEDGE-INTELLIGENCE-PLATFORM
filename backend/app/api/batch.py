from __future__ import annotations
import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.orchestrator.graph import run_orchestrator
from app.schemas import BatchAnswer, BatchRequest, BatchResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/batch", response_model=BatchResponse, summary="Process multiple questions")
async def batch_process(request: BatchRequest) -> BatchResponse:
    """Process a list of questions concurrently and return answers with citations."""
    if not request.questions:
        raise HTTPException(status_code=400, detail="No questions provided")
    if len(request.questions) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 questions per batch")

    async def process_one(bq) -> BatchAnswer:
        try:
            resp = await run_orchestrator(
                question=bq.question,
                access_scope=request.access_scope,
            )
            return BatchAnswer(
                question_id=bq.question_id,
                question=bq.question,
                answer=resp.answer,
                status=resp.status,
                citations=resp.citations,
                verified=resp.verification.verified,
            )
        except Exception as exc:
            logger.error("Batch item %s failed: %s", bq.question_id, exc)
            return BatchAnswer(
                question_id=bq.question_id,
                question=bq.question,
                answer="An error occurred processing this question.",
                status="not_covered",
                citations=[],
                verified=False,
            )

    answers = await asyncio.gather(*[process_one(q) for q in request.questions])
    answers = list(answers)

    answered = sum(1 for a in answers if a.status == "answered")
    partially = sum(1 for a in answers if a.status == "partially_answered")
    not_covered = sum(1 for a in answers if a.status == "not_covered")

    return BatchResponse(
        answers=answers,
        total=len(answers),
        answered=answered,
        partially_answered=partially,
        not_covered=not_covered,
    )
