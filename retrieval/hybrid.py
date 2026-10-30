from datetime import date
import logging
from typing import Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from retrieval.fulltext_search import FullTextRetriever
from retrieval.models import SearchResult
from retrieval.vector_search import VectorRetriever

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60


class HybridRetriever:
    """
    Hybrid retrieval combining dense semantic search (pgvector) and sparse lexical search (full-text)
    using Reciprocal Rank Fusion (RRF).
    
    Guarantees:
    - Multi-tenant tenant boundary isolation.
    - Excludes superseded versions for current queries.
    - Consistent RRF rank combination formula:
        Score(d) = sum_{m in {dense, sparse}} w_m / (k + rank_m(d))
    
    Time Complexity:
    - O(R_dense log R_dense + R_sparse log R_sparse) where R is the candidate result set size.
    """

    def __init__(
        self,
        vector_retriever: Optional[VectorRetriever] = None,
        fulltext_retriever: Optional[FullTextRetriever] = None,
        rrf_k: int = DEFAULT_RRF_K,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ):
        """
        Initialize the hybrid retriever.

        Args:
            vector_retriever: VectorRetriever instance.
            fulltext_retriever: FullTextRetriever instance.
            rrf_k: RRF smoothing constant (standard is 60).
            dense_weight: Multiplier weight for dense vector rankings.
            sparse_weight: Multiplier weight for sparse lexical rankings.
        """
        self.vector_retriever = vector_retriever or VectorRetriever()
        self.fulltext_retriever = fulltext_retriever or FullTextRetriever()
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

    def search(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        candidate_pool_size: int = 30,
        current_only: bool = True,
        as_of_date: Optional[date] = None,
    ) -> List[SearchResult]:
        """
        Execute hybrid search using Reciprocal Rank Fusion.

        Args:
            session: SQLAlchemy database session.
            organization_id: Tenant UUID boundary (mandatory).
            query: User query string.
            top_k: Final number of ranked results to return.
            candidate_pool_size: Number of candidates to retrieve from each retriever.
            current_only: Exclude superseded documents.
            as_of_date: Optional policy effective date cutoff.

        Returns:
            List of fused SearchResult items sorted descending by RRF score.
        """
        if not query or not query.strip():
            return []

        # 1. Fetch dense candidates
        dense_results = self.vector_retriever.search(
            session=session,
            organization_id=organization_id,
            query=query,
            top_k=candidate_pool_size,
            current_only=current_only,
            as_of_date=as_of_date,
        )

        # 2. Fetch sparse lexical candidates
        sparse_results = self.fulltext_retriever.search(
            session=session,
            organization_id=organization_id,
            query=query,
            top_k=candidate_pool_size,
            current_only=current_only,
            as_of_date=as_of_date,
        )

        # 3. Fuse with Reciprocal Rank Fusion
        fused_items: Dict[uuid.UUID, SearchResult] = {}
        rrf_scores: Dict[uuid.UUID, float] = {}
        rank_breakdowns: Dict[uuid.UUID, Dict[str, Optional[int]]] = {}

        # Process dense ranks
        for item in dense_results:
            cid = item.chunk_id
            rank = item.rank
            score_contrib = self.dense_weight / (self.rrf_k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score_contrib
            fused_items[cid] = item
            if cid not in rank_breakdowns:
                rank_breakdowns[cid] = {"dense_rank": rank, "sparse_rank": None}
            else:
                rank_breakdowns[cid]["dense_rank"] = rank

        # Process sparse ranks
        for item in sparse_results:
            cid = item.chunk_id
            rank = item.rank
            score_contrib = self.sparse_weight / (self.rrf_k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score_contrib
            if cid not in fused_items:
                fused_items[cid] = item
            if cid not in rank_breakdowns:
                rank_breakdowns[cid] = {"dense_rank": None, "sparse_rank": rank}
            else:
                rank_breakdowns[cid]["sparse_rank"] = rank

        # 4. Sort descending by fused score
        sorted_chunk_ids = sorted(
            rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True
        )

        # 5. Build final SearchResult objects
        final_results: List[SearchResult] = []
        for rank, cid in enumerate(sorted_chunk_ids[:top_k], start=1):
            base_item = fused_items[cid]
            breakdown = rank_breakdowns[cid]
            final_results.append(
                SearchResult(
                    chunk_id=base_item.chunk_id,
                    document_id=base_item.document_id,
                    document_name=base_item.document_name,
                    canonical_id=base_item.canonical_id,
                    version=base_item.version,
                    section_context=base_item.section_context,
                    page_number=base_item.page_number,
                    content=base_item.content,
                    score=rrf_scores[cid],
                    rank=rank,
                    source_method="hybrid",
                    metadata={
                        "rrf_score": rrf_scores[cid],
                        "dense_rank": breakdown["dense_rank"],
                        "sparse_rank": breakdown["sparse_rank"],
                    },
                )
            )

        return final_results
