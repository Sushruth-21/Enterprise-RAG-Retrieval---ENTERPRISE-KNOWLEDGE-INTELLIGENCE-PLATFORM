from datetime import date
import logging
from typing import List, Optional
import uuid
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.embedding import BGEEmbeddingService
from retrieval.models import SearchResult

logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    Dense semantic vector retriever using PostgreSQL pgvector.
    
    Guarantees:
    - Strict multi-tenant isolation via mandatory `organization_id`.
    - Never retrieves superseded documents for current policy searches.
    - Filters by temporal effective dates when specified.
    - Transparent fallback for SQLite testing environments.
    
    Time Complexity:
    - O(log N) with HNSW/IVFFlat index in PostgreSQL, or O(C * D) brute-force scan across C candidate chunks with D dimensions.
    """

    def __init__(self, embedding_service: Optional[BGEEmbeddingService] = None):
        """
        Initialize the vector retriever.

        Args:
            embedding_service: Embedding service instance for query vectorization.
        """
        self.embedding_service = embedding_service or BGEEmbeddingService()

    def search(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        current_only: bool = True,
        as_of_date: Optional[date] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[SearchResult]:
        """
        Execute dense semantic retrieval.

        Args:
            session: SQLAlchemy session.
            organization_id: Tenant UUID boundary (mandatory).
            query: User search query.
            top_k: Number of nearest chunks to return.
            current_only: If True, exclude superseded document chunks.
            as_of_date: Optional temporal snapshot date for policy validity.
            query_embedding: Optional precomputed query embedding vector.

        Returns:
            List of SearchResult items ranked by semantic similarity.
        """
        if not query or not query.strip():
            return []

        # Vectorize query if not provided
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
                    score=score,
                    rank=rank,
                    source_method="dense",
                    metadata={},
                )
            )

        return results
