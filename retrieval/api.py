from datetime import date
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Security, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB
from retrieval.auth import UserPayload, get_current_user
from retrieval.cache import SemanticQACache
from retrieval.context import ContextBuilder
from retrieval.embedding import BGEEmbeddingService
from retrieval.evaluation import BenchmarkQuery, EvaluationReport, RetrievalEvaluator
from retrieval.fulltext_search import FullTextRetriever
from retrieval.graph import GraphRAGRetriever, KnowledgeGraphManager
from retrieval.hybrid import HybridRetriever
from retrieval.models import Citation, ContextResult, SearchResult
from retrieval.reranker import BGEReranker
from retrieval.vector_search import VectorRetriever

logger = logging.getLogger(__name__)


# =====================================================================
# Shared Contract Models (Compatible with Person 1's backend)
# =====================================================================
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


# =====================================================================
# Request / Response Schemas
# =====================================================================
class SearchRequest(BaseModel):
    query: str
    organization_id: Optional[uuid.UUID] = None
    top_k: int = Field(default=10, ge=1, le=100)
    use_reranker: bool = True
    current_only: bool = True
    as_of_date: Optional[date] = None
    access_scopes: Optional[List[str]] = None
    doc_id: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_results: int
    latency_ms: float


class ContextRequest(BaseModel):
    query: str
    organization_id: Optional[uuid.UUID] = None
    top_k: int = Field(default=5, ge=1, le=50)
    max_tokens: int = Field(default=3500, ge=100)
    use_reranker: bool = True
    current_only: bool = True
    as_of_date: Optional[date] = None
    access_scopes: Optional[List[str]] = None


class ContextResponse(BaseModel):
    context: ContextResult
    latency_ms: float


class QARequest(BaseModel):
    query: str
    organization_id: Optional[uuid.UUID] = None
    use_cache: bool = True
    similarity_threshold: float = Field(default=0.88, ge=0.5, le=1.0)
    top_k: int = Field(default=5, ge=1, le=50)
    use_reranker: bool = True
    access_scopes: Optional[List[str]] = None
    prompt_version: Optional[str] = None
    llm_model: Optional[str] = None


class QAResponse(BaseModel):
    cache_hit: bool
    answer_text: Optional[str] = None
    formatted_context: str
    citations: List[Citation]
    retrieved_results: List[SearchResult] = Field(default_factory=list)
    latency_ms: float
    cache_entry_id: Optional[uuid.UUID] = None


class GraphSearchRequest(BaseModel):
    query: str
    organization_id: Optional[uuid.UUID] = None
    top_k: int = Field(default=10, ge=1, le=50)
    include_adjacent_chunks: bool = True
    current_only: bool = True
    access_scopes: Optional[List[str]] = None


class CacheInvalidateRequest(BaseModel):
    document_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None


class CacheInvalidateResponse(BaseModel):
    invalidated_count: int
    message: str


class EvaluationApiRequest(BaseModel):
    benchmarks: List[BenchmarkQuery]
    organization_id: Optional[uuid.UUID] = None
    top_k: int = Field(default=5, ge=1, le=50)
    strategy: str = Field(default="hybrid", description="dense, sparse, hybrid, reranked, graph")


class StoreAnswerRequest(BaseModel):
    query_text: str
    answer_text: str
    formatted_context: str
    source_document_ids: List[uuid.UUID]
    source_chunk_ids: List[uuid.UUID]
    organization_id: Optional[uuid.UUID] = None
    citation_metadata: Optional[Dict[str, Any]] = None
    access_scope: str = "public"
    user_id: Optional[str] = None
    embedding_model: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None


# =====================================================================
# Database Session Dependency Stubs
# =====================================================================
_session_factory = None


def set_session_factory(factory):
    """Register database session factory for dependency injection."""
    global _session_factory
    _session_factory = factory


def get_db():
    """FastAPI database session dependency."""
    if _session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session factory not configured.",
        )
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def resolve_tenant_and_scopes(
    client_org_id: Optional[uuid.UUID],
    client_scopes: Optional[List[str]],
    user: UserPayload,
) -> Tuple[uuid.UUID, List[str]]:
    """
    Security helper:
    1. Derive organization_id strictly from authenticated user.
    2. Reject client-supplied organization_id if it differs (Cross-tenant prevention).
    3. Enforce access_scopes within user's clearance boundaries.
    """
    if client_org_id is not None and client_org_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access prohibited: authenticated organization '{user.organization_id}' does not match requested organization '{client_org_id}'.",
        )
    effective_org = user.organization_id

    if client_scopes:
        effective_scopes = [s for s in client_scopes if s in user.access_scopes]
        if not effective_scopes:
            effective_scopes = user.access_scopes
    else:
        effective_scopes = user.access_scopes

    return effective_org, effective_scopes


# =====================================================================
# Singletons / Shared Components
# =====================================================================
embedding_service = BGEEmbeddingService()
vector_retriever = VectorRetriever(embedding_service=embedding_service)
fulltext_retriever = FullTextRetriever()
hybrid_retriever = HybridRetriever(
    vector_retriever=vector_retriever,
    fulltext_retriever=fulltext_retriever,
)
reranker = BGEReranker()
context_builder = ContextBuilder()
kg_manager = KnowledgeGraphManager()
graph_retriever = GraphRAGRetriever(kg_manager=kg_manager)
qa_cache = SemanticQACache(embedding_service=embedding_service)
evaluator = RetrievalEvaluator()

retrieval_router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@retrieval_router.post("/search", response_model=SearchResponse)
def search_documents(
    req: SearchRequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Execute hybrid retrieval (pgvector + full-text) with optional BGE cross-encoder reranking.
    Enforces JWT authentication and tenant/permission isolation.
    """
    t0 = time.perf_counter()
    org_id, scopes = resolve_tenant_and_scopes(req.organization_id, req.access_scopes, current_user)

    candidates = hybrid_retriever.search(
        session=session,
        organization_id=org_id,
        query=req.query,
        top_k=req.top_k * 2 if req.use_reranker else req.top_k,
        current_only=req.current_only,
        as_of_date=req.as_of_date,
        access_scopes=scopes,
    )

    if req.use_reranker and candidates:
        results = reranker.rerank(query=req.query, candidates=candidates, top_k=req.top_k)
    else:
        results = candidates[: req.top_k]

    latency = (time.perf_counter() - t0) * 1000.0
    return SearchResponse(results=results, total_results=len(results), latency_ms=latency)


@retrieval_router.post("/context", response_model=ContextResponse)
def get_retrieval_context(
    req: ContextRequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Retrieve documents and construct grounded LLM context with precise citation headers.
    Enforces JWT authentication and tenant/permission isolation.
    """
    t0 = time.perf_counter()
    org_id, scopes = resolve_tenant_and_scopes(req.organization_id, req.access_scopes, current_user)

    candidates = hybrid_retriever.search(
        session=session,
        organization_id=org_id,
        query=req.query,
        top_k=req.top_k * 2 if req.use_reranker else req.top_k,
        current_only=req.current_only,
        as_of_date=req.as_of_date,
        access_scopes=scopes,
    )

    if req.use_reranker and candidates:
        results = reranker.rerank(query=req.query, candidates=candidates, top_k=req.top_k)
    else:
        results = candidates[: req.top_k]

    builder = ContextBuilder(max_tokens=req.max_tokens)
    ctx_result = builder.build_context(results)
    latency = (time.perf_counter() - t0) * 1000.0
    return ContextResponse(context=ctx_result, latency_ms=latency)


@retrieval_router.post("/qa", response_model=QAResponse)
def semantic_qa(
    req: QARequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    CAG Question-Answering endpoint.
    Checks semantic cache first with strict source dependency and permission validation.
    Falls back to hybrid retrieval and context construction if cache misses.
    """
    t0 = time.perf_counter()
    org_id, scopes = resolve_tenant_and_scopes(req.organization_id, req.access_scopes, current_user)

    # 1. Check cache
    if req.use_cache:
        cache_instance = SemanticQACache(
            embedding_service=embedding_service,
            similarity_threshold=req.similarity_threshold,
        )
        lookup = cache_instance.lookup(
            session=session,
            organization_id=org_id,
            query=req.query,
            user_id=current_user.user_id,
            access_scopes=scopes,
            expected_prompt_version=req.prompt_version,
            expected_llm_model=req.llm_model,
        )
        if lookup.is_hit:
            latency = (time.perf_counter() - t0) * 1000.0
            return QAResponse(
                cache_hit=True,
                answer_text=lookup.answer_text,
                formatted_context=lookup.formatted_context or "",
                citations=[],
                latency_ms=latency,
                cache_entry_id=lookup.cache_entry_id,
            )

    # 2. Fresh retrieval fallback
    candidates = hybrid_retriever.search(
        session=session,
        organization_id=org_id,
        query=req.query,
        top_k=req.top_k * 2 if req.use_reranker else req.top_k,
        current_only=True,
        access_scopes=scopes,
    )

    if req.use_reranker and candidates:
        results = reranker.rerank(query=req.query, candidates=candidates, top_k=req.top_k)
    else:
        results = candidates[: req.top_k]

    ctx_result = context_builder.build_context(results)
    latency = (time.perf_counter() - t0) * 1000.0

    return QAResponse(
        cache_hit=False,
        answer_text=None,
        formatted_context=ctx_result.context_text,
        citations=ctx_result.citations,
        retrieved_results=results,
        latency_ms=latency,
    )


@retrieval_router.post("/graph-search", response_model=SearchResponse)
def graph_augmented_search(
    req: GraphSearchRequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    GraphRAG retrieval: retrieves seed chunks and expands through NetworkX knowledge graph.
    """
    t0 = time.perf_counter()
    org_id, scopes = resolve_tenant_and_scopes(req.organization_id, req.access_scopes, current_user)

    seeds = hybrid_retriever.search(
        session=session,
        organization_id=org_id,
        query=req.query,
        top_k=5,
        current_only=req.current_only,
        access_scopes=scopes,
    )

    expanded = graph_retriever.expand_graph_context(
        session=session,
        organization_id=org_id,
        seed_results=seeds,
        include_adjacent_chunks=req.include_adjacent_chunks,
        current_only=req.current_only,
        top_k=req.top_k,
    )

    latency = (time.perf_counter() - t0) * 1000.0
    return SearchResponse(results=expanded, total_results=len(expanded), latency_ms=latency)


@retrieval_router.post("/cache/store")
def store_cached_qa(
    req: StoreAnswerRequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Persist newly generated QA pair to semantic cache with full permission and model metadata."""
    org_id, _ = resolve_tenant_and_scopes(req.organization_id, None, current_user)

    entry = qa_cache.store_answer(
        session=session,
        organization_id=org_id,
        query_text=req.query_text,
        answer_text=req.answer_text,
        formatted_context=req.formatted_context,
        source_document_ids=req.source_document_ids,
        source_chunk_ids=req.source_chunk_ids,
        citation_metadata=req.citation_metadata,
        access_scope=req.access_scope,
        user_id=req.user_id or current_user.user_id,
        embedding_model=req.embedding_model,
        llm_model=req.llm_model,
        prompt_version=req.prompt_version,
    )
    return {"status": "success", "cache_entry_id": entry.id}


@retrieval_router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
def invalidate_cache(
    req: CacheInvalidateRequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Proactively invalidate cache entries dependent on a given document."""
    org_id, _ = resolve_tenant_and_scopes(req.organization_id, None, current_user)

    count = qa_cache.invalidate_for_document(
        session=session,
        organization_id=org_id,
        document_id=req.document_id,
    )
    return CacheInvalidateResponse(
        invalidated_count=count,
        message=f"Invalidated {count} cache records for document {req.document_id}",
    )


@retrieval_router.post("/evaluate", response_model=EvaluationReport)
def run_retrieval_evaluation(
    req: EvaluationApiRequest,
    current_user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Benchmark retrieval quality (Precision@K, Recall@K, MRR, NDCG@K) against ground truth."""
    org_id, scopes = resolve_tenant_and_scopes(req.organization_id, None, current_user)

    def search_fn(query_text: str, top_k: int) -> List[SearchResult]:
        if req.strategy == "dense":
            return vector_retriever.search(
                session=session, organization_id=org_id, query=query_text, top_k=top_k, access_scopes=scopes
            )
        elif req.strategy == "sparse":
            return fulltext_retriever.search(
                session=session, organization_id=org_id, query=query_text, top_k=top_k, access_scopes=scopes
            )
        elif req.strategy == "reranked":
            candidates = hybrid_retriever.search(
                session=session, organization_id=org_id, query=query_text, top_k=top_k * 2, access_scopes=scopes
            )
            return reranker.rerank(query=query_text, candidates=candidates, top_k=top_k)
        elif req.strategy == "graph":
            seeds = hybrid_retriever.search(
                session=session, organization_id=org_id, query=query_text, top_k=top_k, access_scopes=scopes
            )
            return graph_retriever.expand_graph_context(
                session=session, organization_id=org_id, seed_results=seeds, top_k=top_k
            )
        else:  # default hybrid
            return hybrid_retriever.search(
                session=session, organization_id=org_id, query=query_text, top_k=top_k, access_scopes=scopes
            )

    report = evaluator.evaluate_search_function(
        search_fn=search_fn,
        benchmarks=req.benchmarks,
        k=req.top_k,
        strategy_name=req.strategy,
    )
    return report


# =====================================================================
# FastAPI root application & Person 1 Backend Contract Endpoints
# =====================================================================
app = FastAPI(
    title="Enterprise Knowledge Intelligence Platform - Retrieval API",
    version="1.0.0",
)
app.include_router(retrieval_router)


@app.get("/health")
def health_check(session: Session = Depends(get_db)):
    """Health check for system orchestrator and monitoring."""
    return {
        "status": "ok",
        "service": "enterprise_retrieval",
        "db_connected": session is not None,
        "version": "1.0.0",
    }


class PassageSearchRequest(BaseModel):
    query: str
    access_scope: str = "public"
    top_k: int = 10
    doc_id: Optional[str] = None
    organization_id: Optional[uuid.UUID] = None


@app.post("/search", response_model=List[DocumentPassage])
def backend_search(
    req: PassageSearchRequest,
    session: Session = Depends(get_db),
    current_user: Optional[UserPayload] = Depends(lambda: None),
):
    """
    Direct endpoint matching Person 1's backend RetrievalClient contract.
    Returns List[DocumentPassage].
    """
    # If organization_id is not in request or user, use default or single organization
    org_id = req.organization_id or (current_user.organization_id if current_user else None)
    if org_id is None:
        first_chunk = session.scalars(select(ChunkDB).limit(1)).first()
        if first_chunk:
            org_id = first_chunk.organization_id
        else:
            return []

    # Map requested access scope
    scopes = ["public"]
    if req.access_scope in ("internal", "confidential"):
        scopes.append("internal")
    if req.access_scope == "confidential":
        scopes.append("confidential")

    results = hybrid_retriever.search(
        session=session,
        organization_id=org_id,
        query=req.query,
        top_k=req.top_k,
        current_only=True,
        access_scopes=scopes,
    )

    if req.doc_id:
        results = [r for r in results if str(r.document_id) == req.doc_id or r.canonical_id == req.doc_id]

    return [
        DocumentPassage(
            chunk_id=str(r.chunk_id),
            document_id=str(r.document_id),
            document_name=r.document_name,
            version=r.version,
            is_current=True,
            section=r.section_context,
            page=r.page_number,
            content=r.content,
            access_scope=r.access_scope,
            score=r.score,
        )
        for r in results
    ]


@app.get("/passage/{chunk_id}", response_model=Optional[DocumentPassage])
def get_passage_by_id(
    chunk_id: str,
    session: Session = Depends(get_db),
):
    """Fetch single passage by chunk UUID for Person 1's backend RetrievalClient."""
    try:
        cid = uuid.UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk_id UUID")

    chunk = session.scalar(select(ChunkDB).where(ChunkDB.chunk_id == cid))
    if not chunk:
        raise HTTPException(status_code=404, detail="Passage not found")

    return DocumentPassage(
        chunk_id=str(chunk.chunk_id),
        document_id=str(chunk.document_id),
        document_name=chunk.document_name,
        version=chunk.version,
        is_current=(chunk.document_status.value == "current" if hasattr(chunk.document_status, "value") else chunk.document_status == "current"),
        section=chunk.section_context or "",
        page=chunk.page_number or 1,
        content=chunk.content,
        access_scope=getattr(chunk, "access_scope", "public") or "public",
        score=1.0,
    )
