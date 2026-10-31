from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Literal, Optional, TypedDict
import uuid

from langgraph.graph import StateGraph, START, END

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
from app.storage.vault import KnowledgeVault

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# State definition
# ─────────────────────────────────────────────────────────────────────
class OrchestratorState(TypedDict):
    question: str
    conversation_id: str
    access_scope: str
    force_local: Optional[bool]
    document_ids: Optional[List[str]]
    workspace_id: Optional[str]
    query_type: str  # factual | comparative | procedural | ambiguous
    retrieved_passages: List[DocumentPassage]
    mcp_passages: List[DocumentPassage]
    all_passages: List[DocumentPassage]
    context: str
    answer: str
    status: str
    citations: List[Citation]
    verification: VerificationResult
    confidence_score: float
    model_used: str
    error: Optional[str]
    has_restricted_matches: Optional[bool]


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
    return {"query_type": query_type}


async def retrieve_context(state: OrchestratorState) -> Dict[str, Any]:
    """Fetch relevant passages strictly from active document partition and enforce RBAC clearance."""
    if state.get("document_ids") is not None and len(state.get("document_ids")) == 0:
        return {"retrieved_passages": [], "has_restricted_matches": False}

    client = RetrievalClient()
    passages = await client.hybrid_search(
        query=state["question"],
        access_scope=state["access_scope"],
        top_k=8,
        doc_ids=state.get("document_ids"),
        workspace_id=state.get("workspace_id"),
    )
    logger.info("Retrieved %d passages for active docs: %s", len(passages), state.get("document_ids"))

    is_admin = state["access_scope"].lower() in ("confidential", "admin", "maintenance-admin", "all")
    has_restricted_matches = False

    # Standard employee clearance guard: detect if confidential documents hold relevant records
    if not is_admin:
        vault = KnowledgeVault.get_instance()
        doc_ids = state.get("document_ids") or []

        # 1. Did the user query or select document_ids that are marked confidential?
        if doc_ids:
            with vault._get_connection() as conn:
                placeholders = ",".join(["?"] * len(doc_ids))
                conf_docs = conn.execute(
                    f"SELECT id FROM vault_documents WHERE id IN ({placeholders}) AND access_scope = 'confidential'",
                    doc_ids,
                ).fetchall()
                if conf_docs:
                    has_restricted_matches = True

        # 2. If public passages yielded no strong match, check if confidential chunks match
        top_public_score = max((p.score for p in passages), default=0.0)
        if not has_restricted_matches and top_public_score < 0.45:
            conf_passages = vault.search_chunks(
                query=state["question"],
                workspace_id=state.get("workspace_id"),
                doc_ids=doc_ids if doc_ids else None,
                access_scope="confidential",
                top_k=5,
            )
            conf_relevant = [
                p for p in conf_passages
                if p.access_scope == "confidential" and p.score >= 0.45
            ]
            if conf_relevant:
                has_restricted_matches = True

    return {
        "retrieved_passages": passages if not has_restricted_matches else [],
        "has_restricted_matches": has_restricted_matches,
    }


async def invoke_mcp_tools(state: OrchestratorState) -> Dict[str, Any]:
    """For comparative/complex queries, augment with MCP search if running."""
    mcp_passages: List[DocumentPassage] = []
    if state["query_type"] in ("comparative", "ambiguous"):
        client = MCPClient()
        mcp_passages = await client.search_documents(query=state["question"])
    return {"mcp_passages": mcp_passages}


def merge_passages(state: OrchestratorState) -> Dict[str, Any]:
    """Deduplicate and rank passages, keep top 8."""
    seen: set = set()
    merged: List[DocumentPassage] = []

    # Filter strictly to document_ids if specified (prevents previous sources from lingering)
    allowed_docs = state.get("document_ids")
    allowed_set = set(allowed_docs) if allowed_docs is not None else None

    for p in state["retrieved_passages"] + state["mcp_passages"]:
        if allowed_set is not None and p.document_id not in allowed_set:
            continue
        if p.chunk_id not in seen:
            seen.add(p.chunk_id)
            if not p.is_current:
                p = p.model_copy(update={"score": p.score * 0.7})
            merged.append(p)

    merged.sort(key=lambda x: x.score, reverse=True)
    top = merged[:8]
    return {"all_passages": top}


def build_context(state: OrchestratorState) -> Dict[str, Any]:
    """Format passages into a structured context string for the LLM."""
    if not state["all_passages"]:
        return {"context": ""}
    lines = []
    for i, p in enumerate(state["all_passages"], 1):
        status = "CURRENT" if p.is_current else "SUPERSEDED"
        header = (
            f"[{i}] Document: {p.document_name} v{p.version} ({status}), "
            f"Section: {p.section}, Page: {p.page}"
        )
        lines.append(f"{header}\n{p.content}\n")
    return {"context": "\n".join(lines)}


async def generate_answer(state: OrchestratorState) -> Dict[str, Any]:
    """Route to local Ollama and generate the answer strictly from retrieved context."""
    # Strict RBAC Clearance Guard: If employee queried admin-only confidential documents
    if state.get("has_restricted_matches"):
        answer = (
            "Access Restricted: Information related to this query exists within enterprise documents "
            "restricted exclusively to Administrator clearance. You do not have permission to retrieve "
            "or view these confidential records. Please contact your system administrator if you require access."
        )
        await conversation_store.add_message(state["conversation_id"], "user", state["question"])
        await conversation_store.add_message(state["conversation_id"], "assistant", answer)
        return {"answer": answer, "model_used": "rbac-permission-guard"}

    # Strict empty document selection guard
    if state.get("document_ids") is not None and len(state.get("document_ids")) == 0:
        answer = "No documents are currently selected. Please select one or more documents from the checklist to retrieve information."
        await conversation_store.add_message(state["conversation_id"], "user", state["question"])
        await conversation_store.add_message(state["conversation_id"], "assistant", answer)
        return {"answer": answer, "model_used": "dataset-strict-grounding"}

    if not state["all_passages"] or not state["context"].strip():
        answer = "The provided documents do not contain information about this topic."
        await conversation_store.add_message(state["conversation_id"], "user", state["question"])
        await conversation_store.add_message(state["conversation_id"], "assistant", answer)
        return {"answer": answer, "model_used": "dataset-strict-grounding"}

    system_prompt = (
        "You are an offline Enterprise Knowledge Intelligence Assistant.\n"
        "Analyse the provided document passages deeply to produce an accurate, detailed, and factual answer.\n\n"
        "STRICT GROUNDING & CITATION RULES:\n"
        "1. Answer ONLY using verifiable facts directly stated in the context passages below.\n"
        "2. Do NOT use previous conversation history to introduce or assume facts from documents not present in the CURRENT context passages below.\n"
        "3. If tables are present in the context, extract numbers, columns, and metrics accurately.\n"
        "4. When facts are mentioned, cite the source using inline markers like [1], [2] matching the passage numbers.\n"
        "5. If multiple versions of a document exist, prefer CURRENT versions over SUPERSEDED versions.\n"
        "6. Do NOT invent, assume, or extrapolate information outside the context.\n"
        "7. If the context does not explicitly contain the answer, say exactly: "
        "'The provided documents do not contain information about this topic.'\n"
        "8. Provide a clear, thorough explanation covering all parts of the question."
    )

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
        force_local=True,  # 100% local Ollama execution
    )

    await conversation_store.add_message(state["conversation_id"], "user", state["question"])
    await conversation_store.add_message(state["conversation_id"], "assistant", answer)

    return {"answer": answer, "model_used": model_used}


def verify_answer(state: OrchestratorState) -> Dict[str, Any]:
    """Grounding verification: check that key terms from answer appear in supporting passages."""
    answer = state["answer"]
    if state.get("has_restricted_matches") or "access restricted:" in answer.lower():
        return {"verification": VerificationResult(verified=True, unsupported_claims=[])}

    passages_text = " ".join(p.content for p in state["all_passages"]).lower()

    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
        "to", "for", "of", "and", "or", "that", "this", "it", "with",
        "as", "by", "from", "be", "been", "will", "has", "have", "had",
        "not", "no", "its", "their", "they", "our", "all", "per", "up",
    }
    words = re.findall(r"\b[a-zA-Z]{4,}\b", answer.lower())
    key_words = [w for w in words if w not in stop_words]

    not_found_signals = [
        "do not contain", "does not contain", "not found", "no information",
        "not available", "unable to find", "not covered",
    ]
    if any(sig in answer.lower() for sig in not_found_signals):
        return {"verification": VerificationResult(verified=True, unsupported_claims=[])}

    if not key_words or not state["all_passages"]:
        return {
            "verification": VerificationResult(
                verified=False, unsupported_claims=["No supporting passages found"]
            )
        }

    found = sum(1 for w in key_words if w in passages_text)
    ratio = found / len(key_words) if key_words else 0
    verified = ratio >= 0.45

    unsupported: List[str] = []
    if not verified:
        unsupported = ["Answer may contain information not directly supported by the provided passages"]

    return {"verification": VerificationResult(verified=verified, unsupported_claims=unsupported)}


def classify_status(state: OrchestratorState) -> Dict[str, Any]:
    """Determine answered / partially_answered / not_covered and compute grounded confidence score."""
    answer = state["answer"].lower().strip()

    # Exact refusal check or restricted permission guard
    exact_not_found = (
        state.get("has_restricted_matches")
        or "access restricted:" in answer
        or "the provided documents do not contain information about this topic" in answer
        or "the uploaded documents do not contain facts to substantiate an answer" in answer
        or "no documents are currently selected" in answer
        or not state["all_passages"]
    )

    if exact_not_found:
        status = "not_covered"
        confidence = 0.0
    elif state["verification"].verified:
        status = "answered"
        if state["all_passages"]:
            top_scores = [p.score for p in state["all_passages"][:3]]
            avg_top = sum(top_scores) / len(top_scores)
            confidence = round(min(max(avg_top, 0.85), 0.98), 2)
        else:
            confidence = 0.85
    else:
        status = "partially_answered"
        confidence = 0.65

    return {"status": status, "confidence_score": confidence}


def build_citations(state: OrchestratorState) -> Dict[str, Any]:
    """Build Citation objects with exact document name, page number, and snippet."""
    if (
        state.get("has_restricted_matches")
        or "access restricted:" in state["answer"].lower()
        or state["status"] == "not_covered"
        or not state["all_passages"]
    ):
        return {"citations": []}

    allowed_docs = state.get("document_ids")
    passages = state["all_passages"]
    if allowed_docs is not None:
        passages = [p for p in passages if p.document_id in set(allowed_docs)]

    if not passages:
        return {"citations": []}

    seen_keys: set = set()
    unique_citations: List[Citation] = []

    for p in passages[:5]:
        key = f"{p.document_id}:{p.page}:{p.section}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique_citations.append(
                Citation(
                    id=p.chunk_id,
                    document_id=p.document_id,
                    document_name=p.document_name,
                    version=p.version,
                    section=p.section,
                    page=p.page,
                    page_number=p.page,
                    chunk_id=p.chunk_id,
                    snippet=p.content[:350] if p.content else p.section,
                    relevance_score=float(p.score or 0.88),
                )
            )

    return {"citations": unique_citations}


# ─────────────────────────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────────────────────────

def _build_graph() -> Any:
    builder = StateGraph(OrchestratorState)

    builder.add_node("understand_query", understand_query)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("merge_passages", merge_passages)
    builder.add_node("build_context", build_context)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("verify_answer", verify_answer)
    builder.add_node("classify_status", classify_status)
    builder.add_node("build_citations", build_citations)

    builder.add_edge(START, "understand_query")
    builder.add_edge("understand_query", "retrieve_context")
    builder.add_edge("retrieve_context", "merge_passages")
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
    document_ids: Optional[List[str]] = None,
    workspace_id: Optional[str] = None,
) -> ChatResponse:
    """Entry point called by the FastAPI chat endpoint."""
    conv_id = conversation_id or str(uuid.uuid4())

    initial_state: OrchestratorState = {
        "question": question,
        "conversation_id": conv_id,
        "access_scope": access_scope,
        "force_local": force_local,
        "document_ids": document_ids,
        "workspace_id": workspace_id,
        "query_type": "ambiguous",
        "retrieved_passages": [],
        "mcp_passages": [],
        "all_passages": [],
        "context": "",
        "answer": "",
        "status": "not_covered",
        "confidence_score": 0.0,
        "citations": [],
        "verification": VerificationResult(verified=False, unsupported_claims=[]),
        "model_used": "unknown",
        "error": None,
        "has_restricted_matches": False,
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
        confidence_score=final_state.get("confidence_score", 0.0),
        citations=final_state["citations"],
        verification=final_state["verification"],
        model_used=final_state["model_used"],
        conversation_id=conv_id,
    )
