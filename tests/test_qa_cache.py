from datetime import date
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.db import Base, Document as DocumentDB
from models.enums import DocumentStatus
from retrieval.cache import SemanticQACache
from retrieval.embedding import BGEEmbeddingService


@pytest.fixture(scope="module")
def embedding_service():
    return BGEEmbeddingService(model_name="BAAI/bge-small-en-v1.5")


@pytest.fixture
def cache_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_semantic_qa_cache_hit_and_tenant_isolation(cache_db, embedding_service):
    """Verify semantic cache hits on rephrased queries and preserves tenant boundaries."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.82)

    with Session(cache_db, expire_on_commit=False) as session:
        # Create active source document
        doc = DocumentDB(
            id=doc_id,
            organization_id=org_a,
            name="Travel Expense Policy",
            canonical_id="CORP-TRV-01",
            version="2.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/travel.pdf",
            file_hash="hash_travel",
        )
        session.add(doc)
        session.commit()

        # Store answer for Org A
        cache.store_answer(
            session=session,
            organization_id=org_a,
            query_text="What is the daily per diem meal allowance?",
            answer_text="The daily per diem meal allowance is $85 per day under 2024 policy.",
            formatted_context="Policy section 2.1 specifies $85 daily rate.",
            source_document_ids=[doc_id],
            source_chunk_ids=[chunk_id],
            citation_metadata={"doc_name": "Travel Expense Policy", "page": 3},
        )

        # 1. Lookup with semantically equivalent query in Org A
        rephrased_query = "What is the meal per diem allowance per day?"
        result_a = cache.lookup(
            session=session,
            organization_id=org_a,
            query=rephrased_query,
        )

        assert result_a.is_hit is True
        assert "$85" in result_a.answer_text
        assert result_a.similarity_score >= 0.82
        assert result_a.citation_metadata["page"] == 3

        # 2. Lookup in Org B (different tenant) - MUST be a cache miss
        result_b = cache.lookup(
            session=session,
            organization_id=org_b,
            query=rephrased_query,
        )
        assert result_b.is_hit is False


def test_semantic_qa_cache_invalidates_on_superseded_source(cache_db, embedding_service):
    """
    CRITICAL RULE: Never reuse cached answers without validating source dependencies.
    Verify that when a source document becomes SUPERSEDED, the cache entry is invalidated.
    """
    org_id = uuid.uuid4()
    doc_v1_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.82)

    with Session(cache_db, expire_on_commit=False) as session:
        # Create Document V1
        doc_v1 = DocumentDB(
            id=doc_v1_id,
            organization_id=org_id,
            name="Security Passwords",
            canonical_id="CORP-SEC-01",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2022, 1, 1),
            file_uri="s3://test/sec_v1.pdf",
            file_hash="hash_sec1",
        )
        session.add(doc_v1)
        session.commit()

        # Cache answer dependent on Doc V1
        cache.store_answer(
            session=session,
            organization_id=org_id,
            query_text="What is the minimum password length requirement?",
            answer_text="Passwords must be at least 8 characters long.",
            formatted_context="Context from Doc V1",
            source_document_ids=[doc_v1_id],
            source_chunk_ids=[chunk_id],
        )

        # Verify initial hit
        hit1 = cache.lookup(session, org_id, "What is the password length requirement?")
        assert hit1.is_hit is True

        # Now supersede Doc V1 (e.g. Doc V2 arrives with 16 characters requirement)
        doc_v1.status = DocumentStatus.SUPERSEDED
        session.commit()

        # Subsequent lookup MUST detect superseded source document and invalidate
        hit2 = cache.lookup(session, org_id, "What is the password length requirement?")
        assert hit2.is_hit is False
        assert hit2.invalidation_reason is not None
        assert "superseded" in hit2.invalidation_reason.lower()


def test_explicit_document_invalidation(cache_db, embedding_service):
    """Verify proactive cache invalidation when a document is updated."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.80)

    with Session(cache_db, expire_on_commit=False) as session:
        doc = DocumentDB(
            id=doc_id,
            organization_id=org_id,
            name="PTO Policy",
            canonical_id="CORP-HR-04",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2023, 1, 1),
            file_uri="s3://test/pto.pdf",
            file_hash="hash_pto",
        )
        session.add(doc)
        session.commit()

        cache.store_answer(
            session=session,
            organization_id=org_id,
            query_text="How many PTO days do new hires receive?",
            answer_text="New hires receive 15 PTO days.",
            formatted_context="Context for PTO",
            source_document_ids=[doc_id],
            source_chunk_ids=[uuid.uuid4()],
        )

        # Invalidate for document
        invalidated_count = cache.invalidate_for_document(session, org_id, doc_id)
        assert invalidated_count == 1

        # Next lookup should miss
        miss = cache.lookup(session, org_id, "How many PTO days do new hires get?")
        assert miss.is_hit is False
