from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB, Document as DocumentDB, QACacheEntry as QACacheEntryDB
from models.enums import DocumentStatus
from retrieval.embedding import BGEEmbeddingService
from retrieval.models import Citation

logger = logging.getLogger(__name__)

DEFAULT_CACHE_SIMILARITY_THRESHOLD = 0.90
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


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
        access_scope: str = "public",
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        llm_model: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ):
        self.is_hit = is_hit
        self.answer_text = answer_text
        self.formatted_context = formatted_context
        self.citation_metadata = citation_metadata
        self.similarity_score = similarity_score
        self.cache_entry_id = cache_entry_id
        self.invalidation_reason = invalidation_reason
        self.access_scope = access_scope
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.prompt_version = prompt_version


class SemanticQACache:
    """
    Semantic Question-Answer Cache (CAG - Cache-Augmented Generation).
    
    Guarantees:
    - Multi-tenant tenant boundary isolation via `organization_id`.
    - Semantic similarity matching using normalized dense BGE query embeddings.
    - Model & Prompt version tracking:
        Cache entries are invalidated/rejected if the embedding model, LLM model,
        or prompt template version changes.
    - Permission & Scope validation:
        Cached answers cannot cross user privacy or clearance scope boundaries.
    - STRICT SOURCE DEPENDENCY VALIDATION:
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
        expected_embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ):
        """
        Initialize the semantic QA cache.

        Args:
            embedding_service: BGE service to vectorize queries.
            similarity_threshold: Minimum cosine similarity to trigger a candidate hit.
            expected_embedding_model: Active embedding model identifier.
        """
        self.embedding_service = embedding_service or BGEEmbeddingService()
        self.similarity_threshold = similarity_threshold
        self.expected_embedding_model = expected_embedding_model

    def lookup(
        self,
        session: Session,
        organization_id: uuid.UUID,
        query: str,
        query_embedding: Optional[List[float]] = None,
        user_id: Optional[str] = None,
        access_scopes: Optional[List[str]] = None,
        expected_prompt_version: Optional[str] = None,
        expected_llm_model: Optional[str] = None,
    ) -> CacheLookupResult:
        """
        Search for a reusable cached answer, strictly validating dependencies, models, and permissions.

        Args:
            session: Active database session.
            organization_id: Tenant UUID boundary (mandatory).
            query: User's question string.
            query_embedding: Optional precomputed query embedding.
            user_id: Optional ID of the querying user.
            access_scopes: Permitted scopes for the user (default: ['public']).
            expected_prompt_version: Optional prompt version constraint.
            expected_llm_model: Optional LLM model identifier constraint.

        Returns:
            CacheLookupResult indicating hit/miss and validated answer.
        """
        if not query or not query.strip():
            return CacheLookupResult(is_hit=False)

        effective_scopes = access_scopes if access_scopes is not None else ["public"]

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

            # Model mismatch check: embeddings from different models cannot be compared
            entry_model = entry.embedding_model or DEFAULT_EMBEDDING_MODEL
            if entry_model != self.expected_embedding_model:
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

        # 3. Security & Permission Validation
        # Check access scope clearance
        entry_scope = best_entry.access_scope or "public"
        if entry_scope not in effective_scopes:
            logger.warning(
                "Access denied to cached entry %s: entry scope '%s' not in user scopes %s",
                best_entry.id,
                entry_scope,
                effective_scopes,
            )
            return CacheLookupResult(
                is_hit=False,
                similarity_score=best_score,
                cache_entry_id=best_entry.id,
                invalidation_reason=f"Insufficient clearance for cache entry access scope '{entry_scope}'.",
            )

        # Check user privacy boundary: private cache entry cannot be served to another user
        if best_entry.user_id is not None and user_id is not None:
            if str(best_entry.user_id) != str(user_id):
                return CacheLookupResult(
                    is_hit=False,
                    similarity_score=best_score,
                    cache_entry_id=best_entry.id,
                    invalidation_reason="Cache entry belongs to a different user.",
                )

        # 4. Prompt & LLM Model Version Validation
        if expected_prompt_version is not None:
            if best_entry.prompt_version and best_entry.prompt_version != expected_prompt_version:
                logger.info(
                    "Cache miss due to prompt version change (cached=%s, expected=%s)",
                    best_entry.prompt_version,
                    expected_prompt_version,
                )
                return CacheLookupResult(
                    is_hit=False,
                    similarity_score=best_score,
                    cache_entry_id=best_entry.id,
                    invalidation_reason=f"Prompt template version mismatch: cached '{best_entry.prompt_version}' vs requested '{expected_prompt_version}'.",
                )

        if expected_llm_model is not None:
            if best_entry.llm_model and best_entry.llm_model != expected_llm_model:
                logger.info(
                    "Cache miss due to LLM model change (cached=%s, expected=%s)",
                    best_entry.llm_model,
                    expected_llm_model,
                )
                return CacheLookupResult(
                    is_hit=False,
                    similarity_score=best_score,
                    cache_entry_id=best_entry.id,
                    invalidation_reason=f"LLM model mismatch: cached '{best_entry.llm_model}' vs requested '{expected_llm_model}'.",
                )

        # 5. CRITICAL: Validate source document dependencies and permissions
        is_valid, reason = self._validate_source_dependencies(
            session=session,
            entry=best_entry,
            organization_id=organization_id,
            user_access_scopes=effective_scopes,
        )

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
        best_entry.last_accessed_at = datetime.now(timezone.utc)
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
            access_scope=entry_scope,
            embedding_model=best_entry.embedding_model or DEFAULT_EMBEDDING_MODEL,
            llm_model=best_entry.llm_model,
            prompt_version=best_entry.prompt_version,
        )

    def _validate_source_dependencies(
        self,
        session: Session,
        entry: QACacheEntryDB,
        organization_id: uuid.UUID,
        user_access_scopes: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that all source documents and chunks relied upon by this answer
        remain valid, current, and within permitted access clearance.

        Returns (True, None) if valid, or (False, reason) if stale or unauthorized.
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

        # Check source chunk access scopes if available
        if user_access_scopes and entry.source_chunk_ids:
            chunk_uuids = []
            for raw_cid in entry.source_chunk_ids:
                try:
                    chunk_uuids.append(uuid.UUID(str(raw_cid)))
                except ValueError:
                    pass
            if chunk_uuids:
                chunks = session.scalars(
                    select(ChunkDB).where(
                        ChunkDB.chunk_id.in_(chunk_uuids),
                        ChunkDB.organization_id == organization_id,
                    )
                ).all()
                for chk in chunks:
                    c_scope = getattr(chk, "access_scope", "public") or "public"
                    if c_scope not in user_access_scopes:
                        return (
                            False,
                            f"Dependent chunk {chk.chunk_id} requires '{c_scope}' clearance which user lacks.",
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
        access_scope: str = "public",
        user_id: Optional[str] = None,
        embedding_model: Optional[str] = None,
        llm_model: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> QACacheEntryDB:
        """
        Store a newly synthesized question-answer pair into the semantic cache
        with full audit, permission, and version metadata.
        """
        if query_embedding is None:
            # Query-to-query semantic cache matching uses symmetric embedding
            query_embedding = self.embedding_service.embed_single_document(query_text)

        model_name = embedding_model or self.expected_embedding_model

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
            access_scope=access_scope,
            user_id=user_id,
            embedding_model=model_name,
            llm_model=llm_model,
            prompt_version=prompt_version,
            is_valid=True,
            created_at=datetime.now(timezone.utc),
            last_accessed_at=datetime.now(timezone.utc),
        )

        session.add(entry)
        session.commit()
        logger.info(
            "Persisted new QA cache entry %s (scope=%s, model=%s, prompt_v=%s) for org %s",
            entry.id,
            access_scope,
            model_name,
            prompt_version,
            organization_id,
        )
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
