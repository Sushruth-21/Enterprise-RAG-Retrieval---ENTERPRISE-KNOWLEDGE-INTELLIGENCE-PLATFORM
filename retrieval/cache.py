from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.db import Document as DocumentDB, QACacheEntry as QACacheEntryDB
from models.enums import DocumentStatus
from retrieval.embedding import BGEEmbeddingService
from retrieval.models import Citation

logger = logging.getLogger(__name__)

DEFAULT_CACHE_SIMILARITY_THRESHOLD = 0.90


class CacheLookupResult:
    """Represents the outcome of a semantic cache lookup."""

    def __init__(
        self,
        is_hit: bool,
        answer_text: Optional[str] = None,
        formatted_context: Optional[str] = None,
        citation_metadata: Optional[Dict[str, Any]] = None,
        similarity_score: float = 0.0,
        cache_entry_id: Optional[uuid.UUID] = None,
        invalidation_reason: Optional[str] = None,
    ):
        self.is_hit = is_hit
        self.answer_text = answer_text
        self.formatted_context = formatted_context
        self.citation_metadata = citation_metadata
        self.similarity_score = similarity_score
        self.cache_entry_id = cache_entry_id
        self.invalidation_reason = invalidation_reason


class SemanticQACache:
    """
    Semantic Question-Answer Cache (CAG - Cache-Augmented Generation).
    
    Guarantees:
    - Multi-tenant tenant boundary isolation.
    - Semantic similarity matching using normalized dense BGE query embeddings.
    - STRICT DEPENDENCY VALIDATION:
        "Never reuse cached answers without validating their source dependencies and permissions."
        If any underlying source document has been superseded, deleted, or modified,
        the cache entry is invalidated immediately and fresh retrieval is enforced.
    
    Time Complexity:
    - O(C * D + S) where C is active cached queries, D is embedding dimension (384),
      and S is source dependency validation queries.
    """

    def __init__(
        self,
        embedding_service: Optional[BGEEmbeddingService] = None,
        similarity_threshold: float = DEFAULT_CACHE_SIMILARITY_THRESHOLD,
    ):
        """
        Initialize the semantic QA cache.

        Args:
            embedding_service: BGE service to vectorize queries.
            similarity_threshold: Minimum cosine similarity to trigger a candidate hit.
        """
        self.embedding_service = embedding_service or BGEEmbeddingService()
        self.similarity_threshold = similarity_threshold

    def lookup(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        query_embedding: Optional[List[float]] = None,
    ) -> CacheLookupResult:
        """
        Search for a reusable cached answer, strictly validating dependencies.

        Args:
            session: Active database session.
            organization_id: Tenant UUID boundary (mandatory).
            query: User's question string.
            query_embedding: Optional precomputed query embedding.

        Returns:
            CacheLookupResult indicating hit/miss and validated answer.
        """
        if not query or not query.strip():
            return CacheLookupResult(is_hit=False)

        if query_embedding is None:
            # Query-to-query semantic cache matching uses symmetric embedding
            query_embedding = self.embedding_service.embed_single_document(query)

        # 1. Fetch valid cache entries for this organization
        cache_entries = session.scalars(
            select(QACacheEntryDB).where(
                QACacheEntryDB.organization_id == organization_id,
                QACacheEntryDB.is_valid == True,  # noqa: E712
            )
        ).all()

        if not cache_entries:
            return CacheLookupResult(is_hit=False)

        # 2. Compute cosine similarity against cached query embeddings
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        best_score = -1.0
        best_entry: Optional[QACacheEntryDB] = None

        for entry in cache_entries:
            if not entry.query_embedding:
                continue
            c_vec = np.array(entry.query_embedding, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec)
            if c_norm > 0:
                c_vec = c_vec / c_norm

            sim = float(np.dot(q_vec, c_vec))
            if sim > best_score:
                best_score = sim
                best_entry = entry

        # Check if best candidate exceeds similarity threshold
        if best_entry is None or best_score < self.similarity_threshold:
            return CacheLookupResult(is_hit=False, similarity_score=best_score)

        # 3. CRITICAL: Validate source document dependencies and permissions
        is_valid, reason = self._validate_source_dependencies(session, best_entry, organization_id)

        if not is_valid:
            logger.warning(
                "Invalidating stale cache entry %s: %s",
                best_entry.id,
                reason,
            )
            # Transactionally invalidate cache entry
            best_entry.is_valid = False
            session.commit()
            return CacheLookupResult(
                is_hit=False,
                similarity_score=best_score,
                cache_entry_id=best_entry.id,
                invalidation_reason=reason,
            )

        # Update last accessed timestamp
        best_entry.last_accessed_at = datetime.utcnow()
        session.commit()

        logger.info(
            "Semantic QA cache HIT for query '%s' (score=%.4f, entry_id=%s)",
            query[:50],
            best_score,
            best_entry.id,
        )

        return CacheLookupResult(
            is_hit=True,
            answer_text=best_entry.answer_text,
            formatted_context=best_entry.formatted_context,
            citation_metadata=best_entry.citation_metadata,
            similarity_score=best_score,
            cache_entry_id=best_entry.id,
        )

    def _validate_source_dependencies(
        self, session: Session, entry: QACacheEntryDB, organization_id: uuid.UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that all source documents relied upon by this answer remain valid and current.

        Returns (True, None) if valid, or (False, reason) if stale.
        """
        source_doc_ids_raw = entry.source_document_ids or []
        if not source_doc_ids_raw:
            # If answer has no traceable dependencies, reject for safety
            return False, "Answer has no source document dependencies recorded."

        source_doc_uuids = []
        for raw_id in source_doc_ids_raw:
            try:
                source_doc_uuids.append(uuid.UUID(str(raw_id)))
            except ValueError:
                return False, f"Malformed dependency UUID: {raw_id}"

        # Fetch current database state of all dependent documents
        docs = session.scalars(
            select(DocumentDB).where(
                DocumentDB.id.in_(source_doc_uuids),
                DocumentDB.organization_id == organization_id,
            )
        ).all()

        found_ids = {d.id for d in docs}
        missing_ids = set(source_doc_uuids) - found_ids
        if missing_ids:
            return False, f"Source documents {missing_ids} no longer exist in organization."

        for doc in docs:
            # Strict rule: NEVER reuse answer if any source document is superseded
            if doc.status == DocumentStatus.SUPERSEDED:
                return (
                    False,
                    f"Source document '{doc.name}' (canonical_id='{doc.canonical_id}', version='{doc.version}') has been superseded.",
                )

        return True, None

    def store_answer(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query_text: str,
        answer_text: str,
        formatted_context: str,
        source_document_ids: List[uuid.UUID],
        source_chunk_ids: List[uuid.UUID],
        citation_metadata: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> QACacheEntryDB:
        """
        Store a newly synthesized question-answer pair into the semantic cache.

        Args:
            session: Active database session.
            organization_id: Organization tenant UUID.
            query_text: User question.
            answer_text: Synthesized answer.
            formatted_context: Grounding context.
            source_document_ids: UUIDs of source documents used.
            source_chunk_ids: UUIDs of chunks cited.
            citation_metadata: Serialized citation list.
            query_embedding: Optional precomputed query embedding.

        Returns:
            The newly created and persisted QACacheEntryDB record.
        """
        if query_embedding is None:
            # Query-to-query semantic cache matching uses symmetric embedding
            query_embedding = self.embedding_service.embed_single_document(query_text)

        entry = QACacheEntryDB(
            id=uuid.uuid4(),
            organization_id=organization_id,
            query_text=query_text.strip(),
            query_embedding=query_embedding,
            answer_text=answer_text.strip(),
            formatted_context=formatted_context,
            source_document_ids=[str(doc_id) for doc_id in source_document_ids],
            source_chunk_ids=[str(chunk_id) for chunk_id in source_chunk_ids],
            citation_metadata=citation_metadata,
            is_valid=True,
            created_at=datetime.utcnow(),
            last_accessed_at=datetime.utcnow(),
        )

        session.add(entry)
        session.commit()
        logger.info("Persisted new QA cache entry %s for org %s", entry.id, organization_id)
        return entry

    def invalidate_for_document(
        self, session: Session, organization_id: uuid.UUID, document_id: uuid.UUID
    ) -> int:
        """
        Proactively invalidate all cache entries that depend on a specific document.

        Args:
            session: Database session.
            organization_id: Organization UUID.
            document_id: UUID of superseded or modified document.

        Returns:
            Number of invalidated cache records.
        """
        entries = session.scalars(
            select(QACacheEntryDB).where(
                QACacheEntryDB.organization_id == organization_id,
                QACacheEntryDB.is_valid == True,  # noqa: E712
            )
        ).all()

        invalidated_count = 0
        doc_id_str = str(document_id)

        for e in entries:
            if doc_id_str in (e.source_document_ids or []):
                e.is_valid = False
                invalidated_count += 1

        if invalidated_count > 0:
            session.commit()
            logger.info("Invalidated %d cache entries for document %s", invalidated_count, document_id)

        return invalidated_count
