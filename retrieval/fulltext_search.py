from datetime import date
import logging
import math
import re
from typing import Dict, List, Optional, Set
import uuid

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus
from retrieval.models import SearchResult

logger = logging.getLogger(__name__)


def _tokenize(text_str: str) -> List[str]:
    """Simple regex tokenizer for BM25 fallback."""
    return re.findall(r"\b[a-zA-Z0-9_-]+\b", text_str.lower())


class FullTextRetriever:
    """
    PostgreSQL full-text lexical search retriever with BM25 fallback.
    
    Guarantees:
    - Multi-tenant boundary isolation via `organization_id`.
    - Never retrieves superseded documents for current policy questions.
    - Access scope enforcement (only returns chunks the user has clearance for).
    - PostgreSQL tsvector/tsquery ranking (`ts_rank_cd`).
    - Robust in-memory BM25 ranker when running on SQLite test databases.
    
    Time Complexity:
    - O(log N) with GIN index in PostgreSQL, or O(C * M) for candidate scoring.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize the full-text retriever.

        Args:
            k1: BM25 term frequency saturation parameter.
            b: BM25 document length penalty parameter.
        """
        self.k1 = k1
        self.b = b

    def search(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        current_only: bool = True,
        as_of_date: Optional[date] = None,
        access_scopes: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Execute lexical full-text retrieval.

        Args:
            session: SQLAlchemy session.
            organization_id: Multi-tenant organization UUID boundary.
            query: User search query terms.
            top_k: Max results to return.
            current_only: Whether to exclude superseded documents.
            as_of_date: Optional temporal snapshot date.
            access_scopes: Optional list of permitted access scopes (e.g. ['public', 'internal']).

        Returns:
            List of SearchResult items ranked by lexical relevance.
        """
        if not query or not query.strip():
            return []

        bind = session.get_bind()
        is_postgres = bind and bind.dialect.name == "postgresql"

        if is_postgres:
            return self._search_postgres(
                session=session,
                organization_id=organization_id,
                query=query,
                top_k=top_k,
                current_only=current_only,
                as_of_date=as_of_date,
                access_scopes=access_scopes,
            )

        return self._search_bm25_fallback(
            session=session,
            organization_id=organization_id,
            query=query,
            top_k=top_k,
            current_only=current_only,
            as_of_date=as_of_date,
            access_scopes=access_scopes,
        )

    def _search_postgres(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        top_k: int,
        current_only: bool,
        as_of_date: Optional[date],
        access_scopes: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """PostgreSQL native tsvector full-text search with ts_rank_cd."""
        combined_text = func.concat(
            func.coalesce(ChunkDB.section_context, ""),
            " ",
            ChunkDB.content,
        )
        ts_vector = func.to_tsvector("english", combined_text)
        ts_query = func.websearch_to_tsquery("english", query)
        rank_col = func.ts_rank_cd(ts_vector, ts_query).label("rank_score")

        stmt = (
            select(ChunkDB, DocumentDB, rank_col)
            .join(DocumentDB, ChunkDB.document_id == DocumentDB.id)
            .where(
                ChunkDB.organization_id == organization_id,
                ts_vector.op("@@")(ts_query),
            )
        )

        if current_only:
            stmt = stmt.where(
                ChunkDB.document_status == DocumentStatus.CURRENT,
                DocumentDB.status == DocumentStatus.CURRENT,
            )

        if as_of_date is not None:
            stmt = stmt.where(DocumentDB.effective_date <= as_of_date)

        if access_scopes:
            stmt = stmt.where(
                or_(ChunkDB.access_scope.in_(access_scopes), ChunkDB.access_scope.is_(None))
            )

        stmt = stmt.order_by(rank_col.desc()).limit(top_k)
        rows = session.execute(stmt).all()

        results: List[SearchResult] = []
        for rank, (chunk, doc, score) in enumerate(rows, start=1):
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    canonical_id=doc.canonical_id,
                    version=chunk.version,
                    section_context=chunk.section_context,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    access_scope=getattr(chunk, "access_scope", "public") or "public",
                    score=float(score),
                    rank=rank,
                    source_method="sparse",
                    metadata={"ts_rank": float(score)},
                )
            )
        return results

    def _search_bm25_fallback(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        top_k: int,
        current_only: bool,
        as_of_date: Optional[date],
        access_scopes: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """In-memory BM25 ranking fallback for SQLite and non-PostgreSQL engines."""
        stmt = (
            select(ChunkDB, DocumentDB)
            .join(DocumentDB, ChunkDB.document_id == DocumentDB.id)
            .where(ChunkDB.organization_id == organization_id)
        )

        if current_only:
            stmt = stmt.where(
                ChunkDB.document_status == DocumentStatus.CURRENT,
                DocumentDB.status == DocumentStatus.CURRENT,
            )

        if as_of_date is not None:
            stmt = stmt.where(DocumentDB.effective_date <= as_of_date)

        if access_scopes:
            stmt = stmt.where(
                or_(ChunkDB.access_scope.in_(access_scopes), ChunkDB.access_scope.is_(None))
            )

        rows = session.execute(stmt).all()
        if not rows:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # Prepare corpus for BM25 calculation
        doc_tokens_list: List[List[str]] = []
        doc_items = []
        for chunk, doc in rows:
            text_corpus = f"{chunk.section_context} {chunk.content}"
            tokens = _tokenize(text_corpus)
            doc_tokens_list.append(tokens)
            doc_items.append((chunk, doc))

        N = len(doc_tokens_list)
        if N == 0:
            return []

        # Compute average document length
        avgdl = sum(len(d) for d in doc_tokens_list) / N

        # Compute Document Frequency (DF) for query terms
        df: Dict[str, int] = {}
        for q_token in set(query_tokens):
            df[q_token] = sum(1 for d in doc_tokens_list if q_token in d)

        # Score documents using Okapi BM25 formula
        scored = []
        for i, (chunk, doc) in enumerate(doc_items):
            tokens = doc_tokens_list[i]
            doc_len = len(tokens)
            score = 0.0

            # Count term frequencies in this document
            tf_counts: Dict[str, int] = {}
            for t in tokens:
                tf_counts[t] = tf_counts.get(t, 0) + 1

            for q_token in query_tokens:
                if q_token not in tf_counts:
                    continue
                q_df = df.get(q_token, 0)
                # Robertson-Spärck Jones IDF
                idf = math.log((N - q_df + 0.5) / (q_df + 0.5) + 1.0)
                tf = tf_counts[q_token]
                tf_norm = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * (doc_len / avgdl if avgdl > 0 else 1))
                )
                score += idf * tf_norm

            if score > 0.0:
                scored.append((score, chunk, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored[:top_k]

        results = []
        for rank, (score, chunk, doc) in enumerate(top_candidates, start=1):
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    canonical_id=doc.canonical_id,
                    version=chunk.version,
                    section_context=chunk.section_context,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    access_scope=getattr(chunk, "access_scope", "public") or "public",
                    score=float(score),
                    rank=rank,
                    source_method="sparse",
                    metadata={"bm25_score": float(score)},
                )
            )

        return results
