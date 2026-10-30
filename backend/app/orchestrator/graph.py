"""
LangGraph orchestration workflow — the central brain of the system.

Flow:
  understand_query → retrieve_context → invoke_mcp_tools → merge_passages
  → build_context → generate_answer → verify_answer → classify_status
  → build_citations → END
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.llm.router import ModelRouter
from app.mcp.client import MCPClient
from app.models.conversation import conversation_store
from app.retrieval.client import RetrievalClient
from app.schemas import (
    ChatResponse,
    Citation,
    DocumentPassage,
    VerificationResult,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# State definition
# ─────────────────────────────────────────────────────────────────────
class OrchestratorState(TypedDict):
    question: str
    conversation_id: str
    access_scope: str
    force_local: Optional[bool]
    query_type: str  # factual | comparative | procedural | ambiguous
    retrieved_passages: List[DocumentPassage]
    mcp_passages: List[DocumentPassage]
    all_passages: List[DocumentPassage]
    context: str
    answer: str
    status: str
    citations: List[Citation]
    verification: VerificationResult
    model_used: str
    error: Optional[str]


# ─────────────────────────────────────────────────────────────────────
# Graph nodes
# ─────────────────────────────────────────────────────────────────────

def understand_query(state: OrchestratorState) -> Dict[str, Any]:
    """Classify query type using keyword heuristics (no extra LLM call)."""
    q = state["question"].lower()
    if any(w in q for w in ["compare", "difference", "versus", "vs", "which is better", "contrast"]):
        query_type = "comparative"
    elif any(w in q for w in ["how to", "steps to", "procedure", "process", "guide me", "walk me"]):
        query_type = "procedural"
    elif any(w in q for w in ["what is", "who is", "when", "where", "define", "what are"]):
        query_type = "factual"
    else:
        query_type = "ambiguous"
    logger.info("Query type: %s", query_type)
    return {"query_type": query_type}


async def retrieve_context(state: OrchestratorState) -> Dict[str, Any]:
    """Fetch relevant passages from Person 3's retrieval service."""
    client = RetrievalClient()
    passages = await client.hybrid_search(
        query=state["question"],
        access_scope=state["access_scope"],
        top_k=10,
    )
    logger.info("Retrieved %d passages from retrieval service", len(passages))
    return {"retrieved_passages": passages}


async def invoke_mcp_tools(state: OrchestratorState) -> Dict[str, Any]:
    """For comparative/complex queries, augment with MCP search."""
    mcp_passages: List[DocumentPassage] = []
    if state["query_type"] in ("comparative", "ambiguous"):
        client = MCPClient()
        mcp_passages = await client.search_documents(query=state["question"])
        logger.info("MCP returned %d additional passages", len(mcp_passages))
    return {"mcp_passages": mcp_passages}


def merge_passages(state: OrchestratorState) -> Dict[str, Any]:
    """Deduplicate and rank passages, keep top 8."""
    seen: set = set()
    merged: List[DocumentPassage] = []
    for p in state["retrieved_passages"] + state["mcp_passages"]:
        if p.chunk_id not in seen:
            seen.add(p.chunk_id)
            # Prefer current versions
            if not p.is_current:
                p = p.model_copy(update={"score": p.score * 0.7})
            merged.append(p)
    merged.sort(key=lambda x: x.score, reverse=True)
    top = merged[:8]
    logger.info("Merged to %d unique passages", len(top))
    return {"all_passages": top}


def build_context(state: OrchestratorState) -> Dict[str, Any]:
    """Format passages into a numbered context string for the LLM."""
    if not state["all_passages"]:
        return {"context": ""}
    lines = []
    for i, p in enumerate(state["all_passages"], 1):
        status = "CURRENT" if p.is_current else "SUPERSEDED"
        header = (
            f"[{i}] Document: {p.document_name} v{p.version} ({status}), "
            f"Section {p.section}, Page {p.page}"
        )
        lines.append(f"{header}\n{p.content}\n")
    return {"context": "\n".join(lines)}


async def generate_answer(state: OrchestratorState) -> Dict[str, Any]:
    """Route to local/cloud and generate the answer."""
    system_prompt = (
        "You are an Enterprise Knowledge Assistant. "
        "Answer ONLY using information from the provided context passages. "
        "If the context does not contain the answer, say exactly: "
        "'The provided documents do not contain information about this topic.' "
        "Always reference the document name, section, and version. "
        "Do NOT invent figures, percentages, dates, or names. "
        "If a document is marked SUPERSEDED, note that it is an older version."
    )

    # Include conversation history
    history = await conversation_store.get_context_string(state["conversation_id"])
    question_with_history = state["question"]
    if history:
        question_with_history = f"Previous conversation:\n{history}\n\nCurrent question: {state['question']}"

    router = ModelRouter()
    answer, model_used = await router.generate(
        question=question_with_history,
        system_prompt=system_prompt,
        context=state["context"],
        access_scope=state["access_scope"],
        force_local=state["force_local"],
    )

    # Save to conversation history
    await conversation_store.add_message(state["conversation_id"], "user", state["question"])
    await conversation_store.add_message(state["conversation_id"], "assistant", answer)

    return {"answer": answer, "model_used": model_used}


def verify_answer(state: OrchestratorState) -> Dict[str, Any]:
    """Simple grounding check: key noun phrases from answer appear in passages."""
    answer = state["answer"]
    passages_text = " ".join(p.content for p in state["all_passages"]).lower()

    # Extract meaningful words from answer (skip stop words)
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
        "to", "for", "of", "and", "or", "that", "this", "it", "with",
        "as", "by", "from", "be", "been", "will", "has", "have", "had",
        "not", "no", "its", "their", "they", "our", "all", "per", "up",
    }
    words = re.findall(r"\b[a-zA-Z]{4,}\b", answer.lower())
    key_words = [w for w in words if w not in stop_words]

    # Check if the answer says "not found" type phrases
    not_found_signals = [
        "do not contain", "does not contain", "not found", "no information",
        "not available", "unable to find", "not covered",
    ]
    if any(sig in answer.lower() for sig in not_found_signals):
        return {
            "verification": VerificationResult(
                verified=True, unsupported_claims=[]
            )
        }

    if not key_words or not state["all_passages"]:
        return {
            "verification": VerificationResult(
                verified=False, unsupported_claims=["No supporting passages found"]
            )
        }

    # Count how many key words appear in the passages
    found = sum(1 for w in key_words if w in passages_text)
    ratio = found / len(key_words) if key_words else 0
    verified = ratio >= 0.5

    unsupported: List[str] = []
    if not verified:
        unsupported = ["Answer may contain information not directly supported by the provided passages"]

    return {"verification": VerificationResult(verified=verified, unsupported_claims=unsupported)}


def classify_status(state: OrchestratorState) -> Dict[str, Any]:
    """Determine answered / partially_answered / not_covered."""
    answer = state["answer"].lower()
    not_found_signals = [
        "do not contain", "does not contain", "not found", "no information",
        "not available", "unable to find", "not covered", "cannot answer",
    ]

    if any(sig in answer for sig in not_found_signals) or not state["all_passages"]:
        status = "not_covered"
    elif state["verification"].verified:
        status = "answered"
    else:
        status = "partially_answered"

    return {"status": status}


def build_citations(state: OrchestratorState) -> Dict[str, Any]:
    """Build Citation objects from the used passages."""
    citations = [
        Citation(
            document_id=p.document_id,
            document_name=p.document_name,
            version=p.version,
            section=p.section,
            page=p.page,
            chunk_id=p.chunk_id,
        )
        for p in state["all_passages"][:5]  # Top 5 citations
    ]
    # Deduplicate by section
    seen_sections: set = set()
    unique_citations: List[Citation] = []
    for c in citations:
        key = f"{c.document_id}:{c.section}"
        if key not in seen_sections:
            seen_sections.add(key)
            unique_citations.append(c)
    return {"citations": unique_citations}


# ─────────────────────────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────────────────────────

def _build_graph() -> Any:
    builder = StateGraph(OrchestratorState)

    builder.add_node("understand_query", understand_query)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("invoke_mcp_tools", invoke_mcp_tools)
    builder.add_node("merge_passages", merge_passages)
    builder.add_node("build_context", build_context)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("verify_answer", verify_answer)
    builder.add_node("classify_status", classify_status)
    builder.add_node("build_citations", build_citations)

    builder.add_edge(START, "understand_query")
    builder.add_edge("understand_query", "retrieve_context")
    builder.add_edge("retrieve_context", "invoke_mcp_tools")
    builder.add_edge("invoke_mcp_tools", "merge_passages")
    builder.add_edge("merge_passages", "build_context")
    builder.add_edge("build_context", "generate_answer")
    builder.add_edge("generate_answer", "verify_answer")
    builder.add_edge("verify_answer", "classify_status")
    builder.add_edge("classify_status", "build_citations")
    builder.add_edge("build_citations", END)

    return builder.compile()


_graph = _build_graph()


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def run_orchestrator(
    question: str,
    conversation_id: Optional[str] = None,
    access_scope: str = "public",
    force_local: Optional[bool] = None,
) -> ChatResponse:
    """Entry point called by the FastAPI chat endpoint."""
    conv_id = conversation_id or str(uuid.uuid4())

    initial_state: OrchestratorState = {
        "question": question,
        "conversation_id": conv_id,
        "access_scope": access_scope,
        "force_local": force_local,
        "query_type": "ambiguous",
        "retrieved_passages": [],
        "mcp_passages": [],
        "all_passages": [],
        "context": "",
        "answer": "",
        "status": "not_covered",
        "citations": [],
        "verification": VerificationResult(verified=False, unsupported_claims=[]),
        "model_used": "unknown",
        "error": None,
    }

    try:
        final_state = await _graph.ainvoke(initial_state)
    except Exception as exc:
        logger.error("Orchestrator error: %s", exc, exc_info=True)
        return ChatResponse(
            answer="An internal error occurred while processing your question.",
            status="not_covered",
            citations=[],
            verification=VerificationResult(verified=False, unsupported_claims=[str(exc)]),
            model_used="error",
            conversation_id=conv_id,
        )

    return ChatResponse(
        answer=final_state["answer"],
        status=final_state["status"],
        citations=final_state["citations"],
        verification=final_state["verification"],
        model_used=final_state["model_used"],
        conversation_id=conv_id,
    )
