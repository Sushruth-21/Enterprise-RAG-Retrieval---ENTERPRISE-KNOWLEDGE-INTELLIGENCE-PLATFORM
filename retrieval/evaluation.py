import math
import time
from typing import Any, Callable, Dict, List, Optional, Set
import uuid
from pydantic import BaseModel, Field

from retrieval.models import SearchResult


class BenchmarkQuery(BaseModel):
    """Ground-truth query definition for retrieval benchmarking."""
    query: str
    expected_chunk_ids: List[uuid.UUID] = Field(default_factory=list)
    expected_document_ids: List[uuid.UUID] = Field(default_factory=list)
    description: Optional[str] = None


class QueryEvaluationMetric(BaseModel):
    """Detailed evaluation score per individual query."""
    query: str
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float
    retrieved_count: int
    expected_count: int
    latency_ms: float


class EvaluationReport(BaseModel):
    """Aggregated retrieval benchmark report."""
    strategy: str
    total_queries: int
    k: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr: float  # Mean Reciprocal Rank
    mean_ndcg_at_k: float
    average_latency_ms: float
    query_details: List[QueryEvaluationMetric] = Field(default_factory=list)


def compute_precision_at_k(retrieved_ids: List[uuid.UUID], relevant_ids: Set[uuid.UUID], k: int) -> float:
    """Compute Precision@K."""
    if k <= 0 or not relevant_ids:
        return 0.0
    top_k_ids = retrieved_ids[:k]
    hits = sum(1 for cid in top_k_ids if cid in relevant_ids)
    return hits / float(k)


def compute_recall_at_k(retrieved_ids: List[uuid.UUID], relevant_ids: Set[uuid.UUID], k: int) -> float:
    """Compute Recall@K."""
    if not relevant_ids:
        return 0.0
    top_k_ids = retrieved_ids[:k]
    hits = sum(1 for cid in top_k_ids if cid in relevant_ids)
    return hits / float(len(relevant_ids))


def compute_reciprocal_rank(retrieved_ids: List[uuid.UUID], relevant_ids: Set[uuid.UUID]) -> float:
    """Compute Reciprocal Rank (1/rank of first hit)."""
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / float(rank)
    return 0.0


def compute_ndcg_at_k(retrieved_ids: List[uuid.UUID], relevant_ids: Set[uuid.UUID], k: int) -> float:
    """Compute Normalized Discounted Cumulative Gain (NDCG@K) with binary relevance."""
    if not relevant_ids or k <= 0:
        return 0.0

    top_k_ids = retrieved_ids[:k]
    # Compute DCG
    dcg = 0.0
    for rank, cid in enumerate(top_k_ids, start=1):
        if cid in relevant_ids:
            dcg += 1.0 / math.log2(rank + 1.0)

    # Compute Ideal DCG (IDCG)
    idcg = 0.0
    ideal_hits = min(len(relevant_ids), k)
    for rank in range(1, ideal_hits + 1):
        idcg += 1.0 / math.log2(rank + 1.0)

    if idcg == 0.0:
        return 0.0

    return dcg / idcg


class RetrievalEvaluator:
    """
    Standard Information Retrieval Evaluation Suite.
    
    Evaluates:
    - Precision@K
    - Recall@K
    - Mean Reciprocal Rank (MRR)
    - Normalized Discounted Cumulative Gain (NDCG@K)
    - Latency benchmarking
    """

    def evaluate_search_function(
        self,
        search_fn: Callable[[str, int], List[SearchResult]],
        benchmarks: List[BenchmarkQuery],
        k: int = 5,
        strategy_name: str = "hybrid",
    ) -> EvaluationReport:
        """
        Run benchmarks against a search function and compile performance metrics.

        Args:
            search_fn: Function taking (query_text, top_k) and returning List[SearchResult].
            benchmarks: List of ground-truth benchmark test cases.
            k: Top-K cutoff for metrics.
            strategy_name: Name of retrieval approach under test.

        Returns:
            EvaluationReport with aggregate and per-query IR metrics.
        """
        if not benchmarks:
            return EvaluationReport(
                strategy=strategy_name,
                total_queries=0,
                k=k,
                mean_precision_at_k=0.0,
                mean_recall_at_k=0.0,
                mrr=0.0,
                mean_ndcg_at_k=0.0,
                average_latency_ms=0.0,
            )

        query_metrics: List[QueryEvaluationMetric] = []
        total_precision = 0.0
        total_recall = 0.0
        total_rr = 0.0
        total_ndcg = 0.0
        total_latency = 0.0

        for bench in benchmarks:
            start_time = time.perf_counter()
            results = search_fn(bench.query, k)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Gather relevant IDs (checking chunks or documents)
            if bench.expected_chunk_ids:
                retrieved_ids = [r.chunk_id for r in results]
                relevant_set = set(bench.expected_chunk_ids)
            else:
                retrieved_ids = [r.document_id for r in results]
                relevant_set = set(bench.expected_document_ids)

            p_at_k = compute_precision_at_k(retrieved_ids, relevant_set, k)
            r_at_k = compute_recall_at_k(retrieved_ids, relevant_set, k)
            rr = compute_reciprocal_rank(retrieved_ids, relevant_set)
            ndcg = compute_ndcg_at_k(retrieved_ids, relevant_set, k)

            total_precision += p_at_k
            total_recall += r_at_k
            total_rr += rr
            total_ndcg += ndcg
            total_latency += latency_ms

            query_metrics.append(
                QueryEvaluationMetric(
                    query=bench.query,
                    precision_at_k=p_at_k,
                    recall_at_k=r_at_k,
                    reciprocal_rank=rr,
                    ndcg_at_k=ndcg,
                    retrieved_count=len(results),
                    expected_count=len(relevant_set),
                    latency_ms=latency_ms,
                )
            )

        n = len(benchmarks)
        return EvaluationReport(
            strategy=strategy_name,
            total_queries=n,
            k=k,
            mean_precision_at_k=total_precision / n,
            mean_recall_at_k=total_recall / n,
            mrr=total_rr / n,
            mean_ndcg_at_k=total_ndcg / n,
            average_latency_ms=total_latency / n,
            query_details=query_metrics,
        )
