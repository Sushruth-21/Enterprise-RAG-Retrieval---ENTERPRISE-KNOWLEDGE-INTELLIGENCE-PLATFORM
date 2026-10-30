from datetime import date
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
# Request / Response Schemas
# =====================================================================
class SearchRequest(BaseModel):
    organization_id: uuid.UUID
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    use_reranker: bool = True
    current_only: bool = True
    as_of_date: Optional[date] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_results: int
    latency_ms: float


class ContextRequest(BaseModel):
    organization_id: uuid.UUID
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    max_tokens: int = Field(default=3500, ge=100)
    use_reranker: bool = True
    current_only: bool = True
    as_of_date: Optional[date] = None


class ContextResponse(BaseModel):
    context: ContextResult
    latency_ms: float


class QARequest(BaseModel):
    organization_id: uuid.UUID
    query: str
    use_cache: bool = True
    similarity_threshold: float = Field(default=0.88, ge=0.5, le=1.0)
    top_k: int = Field(default=5, ge=1, le=50)
    use_reranker: bool = True


class QAResponse(BaseModel):
    cache_hit: bool
    answer_text: Optional[str] = None
    formatted_context: str
    citations: List[Citation]
    retrieved_results: List[SearchResult] = Field(default_factory=list)
    latency_ms: float
    cache_entry_id: Optional[uuid.UUID] = None


class GraphSearchRequest(BaseModel):
    organization_id: uuid.UUID
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    include_adjacent_chunks: bool = True
    current_only: bool = True


class CacheInvalidateRequest(BaseModel):
    organization_id: uuid.UUID
    document_id: uuid.UUID


class CacheInvalidateResponse(BaseModel):
    invalidated_count: int
    message: str


class EvaluationApiRequest(BaseModel):
    organization_id: uuid.UUID
    benchmarks: List[BenchmarkQuery]
    top_k: int = Field(default=5, ge=1, le=50)
    strategy: str = Field(default="hybrid", description="dense, sparse, hybrid, reranked, graph")


class StoreAnswerRequest(BaseModel):
    organization_id: uuid.UUID
    query_text: str
    answer_text: str
    formatted_context: str
    source_document_ids: List[uuid.UUID]
    source_chunk_ids: List[uuid.UUID]
    citation_metadata: Optional[Dict[str, Any]] = None


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
    session: Session = Depends(get_db),
):
    """
    Execute hybrid retrieval (pgvector + full-text) with optional BGE cross-encoder reranking.
    """
    t0 = time.perf_counter()
    candidates = hybrid_retriever.search(
        session=session,
        organization_id=req.organization_id,
        query=req.query,
        top_k=req.top_k * 2 if req.use_reranker else req.top_k,
        current_only=req.current_only,
        as_of_date=req.as_of_date,
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
    session: Session = Depends(get_db),
):
    """
    Retrieve documents and construct grounded LLM context with precise citation headers.
    """
    t0 = time.perf_counter()
    candidates = hybrid_retriever.search(
        session=session,
        organization_id=req.organization_id,
        query=req.query,
        top_k=req.top_k * 2 if req.use_reranker else req.top_k,
        current_only=req.current_only,
        as_of_date=req.as_of_date,
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
    session: Session = Depends(get_db),
):
    """
    CAG Question-Answering endpoint.
    Checks semantic cache first with strict source dependency validation.
    Falls back to hybrid retrieval and context construction if cache misses.
    """
    t0 = time.perf_counter()

    # 1. Check cache
    if req.use_cache:
        cache_instance = SemanticQACache(
            embedding_service=embedding_service,
            similarity_threshold=req.similarity_threshold,
        )
        lookup = cache_instance.lookup(
            session=session,
            organization_id=req.organization_id,
            query=req.query,
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
        organization_id=req.organization_id,
        query=req.query,
        top_k=req.top_k * 2 if req.use_reranker else req.top_k,
        current_only=True,
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
    session: Session = Depends(get_db),
):
    """
    GraphRAG retrieval: retrieves seed chunks and expands through NetworkX knowledge graph.
    """
    t0 = time.perf_counter()
    seeds = hybrid_retriever.search(
        session=session,
        organization_id=req.organization_id,
        query=req.query,
        top_k=5,
        current_only=req.current_only,
    )

    expanded = graph_retriever.expand_graph_context(
        session=session,
        organization_id=req.organization_id,
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
    session: Session = Depends(get_db),
):
    """Persist newly generated QA pair to semantic cache."""
    entry = qa_cache.store_answer(
        session=session,
        organization_id=req.organization_id,
        query_text=req.query_text,
        answer_text=req.answer_text,
        formatted_context=req.formatted_context,
        source_document_ids=req.source_document_ids,
        source_chunk_ids=req.source_chunk_ids,
        citation_metadata=req.citation_metadata,
    )
    return {"status": "success", "cache_entry_id": entry.id}


@retrieval_router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
def invalidate_cache(
    req: CacheInvalidateRequest,
    session: Session = Depends(get_db),
):
    """Proactively invalidate cache entries dependent on a given document."""
    count = qa_cache.invalidate_for_document(
        session=session,
        organization_id=req.organization_id,
        document_id=req.document_id,
    )
    return CacheInvalidateResponse(
        invalidated_count=count,
        message=f"Invalidated {count} cache records for document {req.document_id}",
    )


@retrieval_router.post("/evaluate", response_model=EvaluationReport)
def run_retrieval_evaluation(
    req: EvaluationApiRequest,
    session: Session = Depends(get_db),
):
    """Benchmark retrieval quality (Precision@K, Recall@K, MRR, NDCG@K) against ground truth."""
    def search_fn(query_text: str, top_k: int) -> List[SearchResult]:
        if req.strategy == "dense":
            return vector_retriever.search(
                session=session, organization_id=req.organization_id, query=query_text, top_k=top_k
            )
        elif req.strategy == "sparse":
            return fulltext_retriever.search(
                session=session, organization_id=req.organization_id, query=query_text, top_k=top_k
            )
        elif req.strategy == "reranked":
            candidates = hybrid_retriever.search(
                session=session, organization_id=req.organization_id, query=query_text, top_k=top_k * 2
            )
            return reranker.rerank(query=query_text, candidates=candidates, top_k=top_k)
        elif req.strategy == "graph":
            seeds = hybrid_retriever.search(
                session=session, organization_id=req.organization_id, query=query_text, top_k=top_k
            )
            return graph_retriever.expand_graph_context(
                session=session, organization_id=req.organization_id, seed_results=seeds, top_k=top_k
            )
        else:  # default hybrid
            return hybrid_retriever.search(
                session=session, organization_id=req.organization_id, query=query_text, top_k=top_k
            )

    report = evaluator.evaluate_search_function(
        search_fn=search_fn,
        benchmarks=req.benchmarks,
        k=req.top_k,
        strategy_name=req.strategy,
    )
    return report


# FastAPI root application
app = FastAPI(
    title="Enterprise Knowledge Intelligence Platform - Retrieval API",
    version="1.0.0",
)
app.include_router(retrieval_router)
