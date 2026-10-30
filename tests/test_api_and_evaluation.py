from datetime import date
import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.api import app, set_session_factory
from retrieval.embedding import BGEEmbeddingService
from retrieval.evaluation import (
    BenchmarkQuery,
    RetrievalEvaluator,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)


from sqlalchemy.pool import StaticPool

@pytest.fixture(scope="module")
def embedding_service():
    return BGEEmbeddingService(model_name="BAAI/bge-small-en-v1.5")


@pytest.fixture
def api_test_db(embedding_service):
    """Seed test database with documents and chunks for FastAPI endpoint tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    set_session_factory(session_factory)

    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    with session_factory() as session:
        doc = DocumentDB(
            id=doc_id,
            organization_id=org_id,
            name="Employee Handbook",
            canonical_id="CORP-HB-01",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/handbook.pdf",
            file_hash="hash_hb",
        )
        session.add(doc)
        session.flush()

        text1 = "Standard working hours are 9:00 AM to 5:00 PM Monday through Friday."
        text2 = "Employees receive 20 days of paid time off per calendar year."
        embs = embedding_service.embed_documents([text1, text2])

        c1 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name="Employee Handbook",
            version="1.0",
            chunk_index=0,
            section_context="1.0 Work Schedule",
            page_number=1,
            content=text1,
            chunk_hash=hashlib.sha256(text1.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[0],
        )
        c2 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name="Employee Handbook",
            version="1.0",
            chunk_index=1,
            section_context="2.0 PTO",
            page_number=2,
            content=text2,
            chunk_hash=hashlib.sha256(text2.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[1],
        )
        session.add_all([c1, c2])
        session.commit()

    return engine, org_id, doc_id, c1, c2


def test_retrieval_evaluation_metrics_unit():
    """Verify precision, recall, MRR, and NDCG math functions."""
    id1, id2, id3, id4 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    relevant = {id1, id3}

    # Case 1: Perfect retrieval [id1, id3]
    retrieved_perfect = [id1, id3, id2, id4]
    assert compute_precision_at_k(retrieved_perfect, relevant, k=2) == 1.0
    assert compute_recall_at_k(retrieved_perfect, relevant, k=2) == 1.0
    assert compute_reciprocal_rank(retrieved_perfect, relevant) == 1.0
    assert compute_ndcg_at_k(retrieved_perfect, relevant, k=2) == 1.0

    # Case 2: Hit at rank 2 [id2, id1]
    retrieved_rank2 = [id2, id1, id4]
    assert compute_precision_at_k(retrieved_rank2, relevant, k=2) == 0.5
    assert compute_recall_at_k(retrieved_rank2, relevant, k=2) == 0.5
    assert compute_reciprocal_rank(retrieved_rank2, relevant) == 0.5


def test_fastapi_search_endpoint(api_test_db):
    """Verify POST /retrieval/search executes hybrid search with BGE reranking."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    response = client.post(
        "/retrieval/search",
        json={
            "organization_id": str(org_id),
            "query": "working hours schedule",
            "top_k": 5,
            "use_reranker": True,
            "current_only": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] >= 1
    assert data["results"][0]["document_id"] == str(doc_id)
    assert "9:00 AM" in data["results"][0]["content"]


def test_fastapi_context_endpoint(api_test_db):
    """Verify POST /retrieval/context builds prompt context with citations."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    response = client.post(
        "/retrieval/context",
        json={
            "organization_id": str(org_id),
            "query": "paid time off days",
            "top_k": 3,
            "max_tokens": 1000,
        },
    )

    assert response.status_code == 200
    data = response.json()
    ctx = data["context"]
    assert ctx["chunk_count"] >= 1
    assert "Employee Handbook" in ctx["context_text"]
    assert "20 days" in ctx["context_text"]
    assert len(ctx["citations"]) >= 1


def test_fastapi_qa_endpoint_cache_and_fallback(api_test_db):
    """Verify POST /retrieval/qa semantic QA cache and retrieval fallback."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    # 1. First call: cache miss, falls back to retrieval
    resp1 = client.post(
        "/retrieval/qa",
        json={
            "organization_id": str(org_id),
            "query": "What are the standard working hours?",
            "use_cache": True,
        },
    )
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["cache_hit"] is False
    assert "9:00 AM" in d1["formatted_context"]

    # 2. Store answer into cache
    store_resp = client.post(
        "/retrieval/cache/store",
        json={
            "organization_id": str(org_id),
            "query_text": "What are the standard working hours?",
            "answer_text": "Standard working hours are 9:00 AM to 5:00 PM.",
            "formatted_context": d1["formatted_context"],
            "source_document_ids": [str(doc_id)],
            "source_chunk_ids": [str(c1.chunk_id)],
        },
    )
    assert store_resp.status_code == 200

    # 3. Subsequent call: cache hit!
    resp2 = client.post(
        "/retrieval/qa",
        json={
            "organization_id": str(org_id),
            "query_text": "What are the standard working hours?",
            "query": "What are the standard working hours?",
            "use_cache": True,
            "similarity_threshold": 0.85,
        },
    )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["cache_hit"] is True
    assert "9:00 AM" in d2["answer_text"]


def test_fastapi_graph_search_endpoint(api_test_db):
    """Verify POST /retrieval/graph-search expands context via GraphRAG."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    resp = client.post(
        "/retrieval/graph-search",
        json={
            "organization_id": str(org_id),
            "query": "working hours",
            "top_k": 5,
            "include_adjacent_chunks": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] >= 1


def test_fastapi_cache_invalidate_endpoint(api_test_db):
    """Verify POST /retrieval/cache/invalidate invalidates cache entries."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    resp = client.post(
        "/retrieval/cache/invalidate",
        json={
            "organization_id": str(org_id),
            "document_id": str(doc_id),
        },
    )
    assert resp.status_code == 200
    assert "invalidated_count" in resp.json()


def test_fastapi_evaluate_endpoint(api_test_db):
    """Verify POST /retrieval/evaluate benchmarks retrieval quality."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    benchmarks = [
        {
            "query": "working hours",
            "expected_chunk_ids": [str(c1.chunk_id)],
            "expected_document_ids": [str(doc_id)],
        }
    ]

    resp = client.post(
        "/retrieval/evaluate",
        json={
            "organization_id": str(org_id),
            "benchmarks": benchmarks,
            "top_k": 3,
            "strategy": "hybrid",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "hybrid"
    assert data["total_queries"] == 1
    assert data["mrr"] > 0.0
    assert data["mean_precision_at_k"] > 0.0
