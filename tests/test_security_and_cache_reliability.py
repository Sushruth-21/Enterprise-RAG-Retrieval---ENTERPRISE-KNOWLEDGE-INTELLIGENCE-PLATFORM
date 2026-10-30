from datetime import date, datetime, timedelta, timezone
import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB, QACacheEntry as QACacheEntryDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.api import app, set_session_factory
from retrieval.auth import create_access_token, decode_access_token
from retrieval.cache import SemanticQACache
from retrieval.embedding import BGEEmbeddingService


@pytest.fixture(scope="module")
def embedding_service():
    return BGEEmbeddingService(model_name="BAAI/bge-small-en-v1.5")


@pytest.fixture
def security_test_db(embedding_service):
    """Seed test database with two isolated organizations and different clearance scopes."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    set_session_factory(session_factory)

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    doc_a_public_id = uuid.uuid4()
    doc_a_confidential_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    with session_factory() as session:
        # Org A - Public document
        doc_a_pub = DocumentDB(
            id=doc_a_public_id,
            organization_id=org_a,
            name="Org A Public Policy",
            canonical_id="ORG-A-PUB",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/a_pub.pdf",
            file_hash="hash_a_pub",
        )
        # Org A - Confidential document
        doc_a_conf = DocumentDB(
            id=doc_a_confidential_id,
            organization_id=org_a,
            name="Org A Executive Compensation",
            canonical_id="ORG-A-CONF",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/a_conf.pdf",
            file_hash="hash_a_conf",
        )
        # Org B - Document
        doc_b = DocumentDB(
            id=doc_b_id,
            organization_id=org_b,
            name="Org B Strategy Plan",
            canonical_id="ORG-B-STRAT",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/b_strat.pdf",
            file_hash="hash_b",
        )
        session.add_all([doc_a_pub, doc_a_conf, doc_b])
        session.flush()

        text_a_pub = "Public working hours are Monday through Friday from 9 to 5."
        text_a_conf = "Executive bonus structure is strictly confidential and restricted."
        text_b = "Org B confidential merger strategies and targets."

        embs = embedding_service.embed_documents([text_a_pub, text_a_conf, text_b])

        chunk_a_pub = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_a,
            document_id=doc_a_public_id,
            document_name="Org A Public Policy",
            version="1.0",
            chunk_index=0,
            section_context="Public Section",
            page_number=1,
            content=text_a_pub,
            chunk_hash=hashlib.sha256(text_a_pub.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[0],
            access_scope="public",
        )
        chunk_a_conf = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_a,
            document_id=doc_a_confidential_id,
            document_name="Org A Executive Compensation",
            version="1.0",
            chunk_index=0,
            section_context="Confidential Section",
            page_number=1,
            content=text_a_conf,
            chunk_hash=hashlib.sha256(text_a_conf.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[1],
            access_scope="confidential",
        )
        chunk_b = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_b,
            document_id=doc_b_id,
            document_name="Org B Strategy Plan",
            version="1.0",
            chunk_index=0,
            section_context="Org B Section",
            page_number=1,
            content=text_b,
            chunk_hash=hashlib.sha256(text_b.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[2],
            access_scope="confidential",
        )
        session.add_all([chunk_a_pub, chunk_a_conf, chunk_b])
        session.commit()

    return {
        "engine": engine,
        "session_factory": session_factory,
        "org_a": org_a,
        "org_b": org_b,
        "doc_a_pub": doc_a_pub,
        "doc_a_conf": doc_a_conf,
        "doc_b": doc_b,
        "chunk_a_pub": chunk_a_pub,
        "chunk_a_conf": chunk_a_conf,
        "chunk_b": chunk_b,
    }


def test_unauthorized_missing_and_invalid_token(security_test_db):
    """Verify 401 Unauthorized when token is missing, malformed, or expired."""
    client = TestClient(app)

    # 1. Missing Authorization header
    resp = client.post(
        "/retrieval/search",
        json={"query": "working hours"},
    )
    assert resp.status_code == 401
    assert "Authorization header" in resp.json()["detail"]

    # 2. Malformed token
    resp_bad = client.post(
        "/retrieval/search",
        json={"query": "working hours"},
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert resp_bad.status_code == 401

    # 3. Expired token
    expired_token = create_access_token(
        user_id="user_old",
        organization_id=security_test_db["org_a"],
        expires_delta=timedelta(seconds=-10),  # expired in past
    )
    resp_exp = client.post(
        "/retrieval/search",
        json={"query": "working hours"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp_exp.status_code == 401
    assert "expired" in resp_exp.json()["detail"].lower()


def test_cross_tenant_access_rejection(security_test_db):
    """Verify that a user from Org A cannot access data from Org B (403 Forbidden)."""
    client = TestClient(app)
    org_a = security_test_db["org_a"]
    org_b = security_test_db["org_b"]

    token_a = create_access_token(
        user_id="user_a",
        organization_id=org_a,
        access_scopes=["public", "internal", "confidential"],
    )

    # User A tries to explicitly request Org B data
    resp = client.post(
        "/retrieval/search",
        json={
            "organization_id": str(org_b),
            "query": "merger strategies",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "Cross-tenant access prohibited" in resp.json()["detail"]


def test_access_scope_enforcement_public_vs_confidential(security_test_db):
    """
    Verify document-level access permissions:
    - User with 'public' scope cannot see 'confidential' chunks.
    - User with 'confidential' scope can see both 'public' and 'confidential' chunks.
    """
    client = TestClient(app)
    org_a = security_test_db["org_a"]

    token_public = create_access_token(
        user_id="contractor_1",
        organization_id=org_a,
        access_scopes=["public"],
    )
    token_exec = create_access_token(
        user_id="exec_1",
        organization_id=org_a,
        access_scopes=["public", "internal", "confidential"],
    )

    # 1. Contractor with public scope queries for compensation / executive bonus
    resp_pub = client.post(
        "/retrieval/search",
        json={"query": "Executive bonus structure compensation"},
        headers={"Authorization": f"Bearer {token_public}"},
    )
    assert resp_pub.status_code == 200
    results_pub = resp_pub.json()["results"]
    for r in results_pub:
        assert r["access_scope"] == "public"
        assert "strictly confidential" not in r["content"]

    # 2. Executive with confidential scope queries
    resp_exec = client.post(
        "/retrieval/search",
        json={"query": "Executive bonus structure compensation"},
        headers={"Authorization": f"Bearer {token_exec}"},
    )
    assert resp_exec.status_code == 200
    results_exec = resp_exec.json()["results"]
    found_confidential = any(r["access_scope"] == "confidential" for r in results_exec)
    assert found_confidential is True


def test_cache_reliability_permission_boundary(security_test_db, embedding_service):
    """Verify that cached answers with 'confidential' scope cannot be retrieved by 'public' users."""
    session_factory = security_test_db["session_factory"]
    org_a = security_test_db["org_a"]
    doc_a_conf = security_test_db["doc_a_conf"]
    chunk_a_conf = security_test_db["chunk_a_conf"]

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.85)

    with session_factory() as session:
        # Store confidential answer
        cache.store_answer(
            session=session,
            organization_id=org_a,
            query_text="What is executive compensation bonus?",
            answer_text="Executives receive 50% performance bonus.",
            formatted_context="Executive section",
            source_document_ids=[doc_a_conf.id],
            source_chunk_ids=[chunk_a_conf.chunk_id],
            access_scope="confidential",
            prompt_version="v1.0",
            llm_model="qwen2.5:3b",
        )

        # 1. Public user lookup: must be rejected / miss
        lookup_pub = cache.lookup(
            session=session,
            organization_id=org_a,
            query="What is executive compensation bonus?",
            access_scopes=["public"],
        )
        assert lookup_pub.is_hit is False
        assert "Insufficient clearance" in (lookup_pub.invalidation_reason or "")

        # 2. Executive user lookup: must hit!
        lookup_exec = cache.lookup(
            session=session,
            organization_id=org_a,
            query="What is executive compensation bonus?",
            access_scopes=["public", "internal", "confidential"],
        )
        assert lookup_exec.is_hit is True
        assert "50% performance bonus" in lookup_exec.answer_text


def test_cache_reliability_prompt_and_model_versioning(security_test_db, embedding_service):
    """Verify cache misses when prompt version or embedding/LLM model changes."""
    session_factory = security_test_db["session_factory"]
    org_a = security_test_db["org_a"]
    doc_a_pub = security_test_db["doc_a_pub"]
    chunk_a_pub = security_test_db["chunk_a_pub"]

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.85)

    with session_factory() as session:
        cache.store_answer(
            session=session,
            organization_id=org_a,
            query_text="What are office working hours?",
            answer_text="Working hours are 9 to 5.",
            formatted_context="Work schedule",
            source_document_ids=[doc_a_pub.id],
            source_chunk_ids=[chunk_a_pub.chunk_id],
            access_scope="public",
            embedding_model="BAAI/bge-small-en-v1.5",
            llm_model="gemini-2.0-flash",
            prompt_version="v1.0",
        )

        # 1. Same prompt version: HIT
        hit = cache.lookup(
            session=session,
            organization_id=org_a,
            query="What are office working hours?",
            access_scopes=["public"],
            expected_prompt_version="v1.0",
            expected_llm_model="gemini-2.0-flash",
        )
        assert hit.is_hit is True

        # 2. Changed prompt version: MISS
        miss_prompt = cache.lookup(
            session=session,
            organization_id=org_a,
            query="What are office working hours?",
            access_scopes=["public"],
            expected_prompt_version="v2.0",
        )
        assert miss_prompt.is_hit is False
        assert "Prompt template version mismatch" in miss_prompt.invalidation_reason

        # 3. Changed LLM model: MISS
        miss_llm = cache.lookup(
            session=session,
            organization_id=org_a,
            query="What are office working hours?",
            access_scopes=["public"],
            expected_llm_model="anthropic/claude-3-5",
        )
        assert miss_llm.is_hit is False
        assert "LLM model mismatch" in miss_llm.invalidation_reason

        # 4. Changed embedding model in cache instance: MISS
        other_cache = SemanticQACache(
            embedding_service=embedding_service,
            expected_embedding_model="text-embedding-3-small",
        )
        miss_emb = other_cache.lookup(
            session=session,
            organization_id=org_a,
            query="What are office working hours?",
            access_scopes=["public"],
        )
        assert miss_emb.is_hit is False


def test_cache_dependency_invalidation_on_superseded_document(security_test_db, embedding_service):
    """Verify that when a source document becomes superseded, the cache entry is invalidated."""
    session_factory = security_test_db["session_factory"]
    org_a = security_test_db["org_a"]
    doc_a_pub = security_test_db["doc_a_pub"]
    chunk_a_pub = security_test_db["chunk_a_pub"]

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.85)

    with session_factory() as session:
        cache.store_answer(
            session=session,
            organization_id=org_a,
            query_text="What are the daily hours?",
            answer_text="9 AM to 5 PM daily.",
            formatted_context="Context text",
            source_document_ids=[doc_a_pub.id],
            source_chunk_ids=[chunk_a_pub.chunk_id],
            access_scope="public",
        )

        # Before superseding: HIT
        assert cache.lookup(session=session, organization_id=org_a, query="What are the daily hours?").is_hit is True

        # Document is superseded
        doc = session.get(DocumentDB, doc_a_pub.id)
        doc.status = DocumentStatus.SUPERSEDED
        session.commit()

        # After superseding: MISS and entry automatically invalidated
        lookup_after = cache.lookup(session=session, organization_id=org_a, query="What are the daily hours?")
        assert lookup_after.is_hit is False
        assert "superseded" in (lookup_after.invalidation_reason or "").lower()

        # Verify entry marked is_valid = False in database
        entry = session.get(QACacheEntryDB, lookup_after.cache_entry_id)
        assert entry.is_valid is False
