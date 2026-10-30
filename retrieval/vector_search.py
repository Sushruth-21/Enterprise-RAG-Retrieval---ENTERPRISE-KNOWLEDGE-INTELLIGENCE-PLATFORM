from datetime import date
import logging
from typing import List, Optional
import uuid

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.embedding import BGEEmbeddingService
from retrieval.models import SearchResult

logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    PostgreSQL pgvector dense retrieval service with fallback for non-Postgres engines.
    
    Guarantees:
    - Multi-tenant boundary isolation via `organization_id`.
    - Document status enforcement (never retrieves superseded documents if current_only=True).
    - Temporal filtering (respects effective_date if as_of_date is provided).
    - Access scope enforcement (only returns chunks the user has clearance for).
    - Native pgvector cosine distance operator `<=>` on PostgreSQL.
    
    Time Complexity:
    - O(log N) with HNSW index in PostgreSQL, or O(N * D) with SQLite in-memory scan.
    """

    def __init__(self, embedding_service: Optional[BGEEmbeddingService] = None):
        """
        Initialize vector retriever.

        Args:
            embedding_service: Embedding generator (defaults to BGE-small-en-v1.5).
        """
        self.embedding_service = embedding_service or BGEEmbeddingService()

    def search(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        current_only: bool = True,
        as_of_date: Optional[date] = None,
        access_scopes: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Execute vector similarity search.

        Args:
            session: SQLAlchemy session.
            organization_id: Multi-tenant organization UUID boundary.
            query: User search query string.
            query_embedding: Optional precomputed query embedding.
            top_k: Number of nearest neighbors to retrieve.
            current_only: If True, exclude superseded or archived documents.
            as_of_date: Optional temporal snapshot date.
            access_scopes: Optional list of permitted access scopes (e.g. ['public', 'internal']).

        Returns:
            Ranked list of SearchResult items ordered by cosine similarity descending.
        """
        if not query and query_embedding is None:
            return []

        if query_embedding is None:
            query_embedding = self.embedding_service.embed_query(query)

        bind = session.get_bind()
        is_postgres = bind and bind.dialect.name == "postgresql"

        stmt = (
            select(ChunkDB, DocumentDB)
            .join(DocumentDB, ChunkDB.document_id == DocumentDB.id)
            .where(
                ChunkDB.organization_id == organization_id,
                ChunkDB.processing_status == ProcessingStatus.COMPLETED,
                ChunkDB.embedding.is_not(None),
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

        if is_postgres:
            # Native pgvector cosine distance operator (<=>)
            distance_col = ChunkDB.embedding.cosine_distance(query_embedding).label("distance")
            pg_stmt = (
                select(ChunkDB, DocumentDB, distance_col)
                .join(DocumentDB, ChunkDB.document_id == DocumentDB.id)
                .where(
                    ChunkDB.organization_id == organization_id,
                    ChunkDB.processing_status == ProcessingStatus.COMPLETED,
                    ChunkDB.embedding.is_not(None),
                )
            )
            if current_only:
                pg_stmt = pg_stmt.where(
                    ChunkDB.document_status == DocumentStatus.CURRENT,
                    DocumentDB.status == DocumentStatus.CURRENT,
                )
            if as_of_date is not None:
                pg_stmt = pg_stmt.where(DocumentDB.effective_date <= as_of_date)

            if access_scopes:
                pg_stmt = pg_stmt.where(
                    or_(ChunkDB.access_scope.in_(access_scopes), ChunkDB.access_scope.is_(None))
                )

            pg_stmt = pg_stmt.order_by(distance_col.asc()).limit(top_k)
            rows = session.execute(pg_stmt).all()

            results: List[SearchResult] = []
            for rank, (chunk, doc, dist) in enumerate(rows, start=1):
                # Cosine distance in [0, 2], similarity = 1 - distance
                similarity = max(0.0, 1.0 - float(dist))
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
                        score=similarity,
                        rank=rank,
                        source_method="dense",
                        metadata={"distance": float(dist)},
                    )
                )
            return results

        # SQLite / Non-Postgres fallback: compute cosine similarity in memory
        rows = session.execute(stmt).all()
        if not rows:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scored_candidates = []
        for chunk, doc in rows:
            if chunk.embedding is None:
                continue
            c_vec = np.array(chunk.embedding, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec)
            if c_norm > 0:
                c_vec = c_vec / c_norm
            similarity = float(np.dot(q_vec, c_vec))
            scored_candidates.append((similarity, chunk, doc))

        # Sort descending by similarity
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored_candidates[:top_k]

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
                    score=score,
                    rank=rank,
                    source_method="dense",
                    metadata={},
                )
            )

        return results
