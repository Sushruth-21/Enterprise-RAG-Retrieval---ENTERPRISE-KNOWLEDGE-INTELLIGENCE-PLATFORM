from datetime import date
import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.api import app, set_session_factory
from retrieval.auth import create_access_token
from retrieval.embedding import BGEEmbeddingService
from retrieval.evaluation import (
    BenchmarkQuery,
    RetrievalEvaluator,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)


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
            access_scope="public",
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
            access_scope="public",
        )
        session.add_all([c1, c2])
        session.commit()

    return engine, org_id, doc_id, c1, c2


@pytest.fixture
def auth_headers(api_test_db):
    """Generate JWT authorization headers for the test organization."""
    _, org_id, _, _, _ = api_test_db
    token = create_access_token(
        user_id="test_worker_1",
        organization_id=org_id,
        role="admin",
        access_scopes=["public", "internal", "confidential"],
    )
    return {"Authorization": f"Bearer {token}"}


def test_retrieval_evaluation_metrics_unit():
    """Verify precision@k, recall@k, MRR, and NDCG@k metric calculations."""
    c1 = uuid.uuid4()
    c2 = uuid.uuid4()
    c3 = uuid.uuid4()
    c4 = uuid.uuid4()
    c5 = uuid.uuid4()

    retrieved = [c1, c2, c3, c4, c5]
    ground_truth = {c1, c3}

    # Precision@3 = 2 / 3
    p3 = compute_precision_at_k(retrieved, ground_truth, k=3)
    assert pytest.approx(p3, rel=1e-3) == 2.0 / 3.0

    # Recall@3 = 2 / 2 = 1.0
    r3 = compute_recall_at_k(retrieved, ground_truth, k=3)
    assert pytest.approx(r3, rel=1e-3) == 1.0

    # Reciprocal Rank = 1 / 1 (first item is relevant)
    rr = compute_reciprocal_rank(retrieved, ground_truth)
    assert rr == 1.0

    # Second item first: [c2, c1, c4] -> MRR = 0.5
    rr2 = compute_reciprocal_rank([c2, c1, c4], ground_truth)
    assert rr2 == 0.5

    # NDCG@3 with binary relevance
    ndcg3 = compute_ndcg_at_k(retrieved, ground_truth, k=3)
    assert 0.0 < ndcg3 <= 1.0


def test_evaluator_class_with_mocked_results():
    """Verify RetrievalEvaluator aggregation across a benchmark query set."""
    evaluator = RetrievalEvaluator()

    q1_chunk = uuid.uuid4()
    q2_chunk = uuid.uuid4()

    benchmarks = [
        BenchmarkQuery(
            query="test query 1",
            expected_chunk_ids=[q1_chunk],
        ),
        BenchmarkQuery(
            query="test query 2",
            expected_chunk_ids=[q2_chunk],
        ),
    ]

    from retrieval.models import SearchResult

    def dummy_search_fn(query_str: str, top_k: int):
        target = q1_chunk if "1" in query_str else q2_chunk
        return [
            SearchResult(
                chunk_id=target,
                document_id=uuid.uuid4(),
                document_name="Test Doc",
                version="1.0",
                section_context="Section",
                page_number=1,
                content="Sample content",
                score=0.95,
                rank=1,
                source_method="hybrid",
            )
        ]

    report = evaluator.evaluate_search_function(
        search_fn=dummy_search_fn,
        benchmarks=benchmarks,
        k=5,
        strategy_name="mock_hybrid",
    )

    assert report.total_queries == 2
    assert report.mean_precision_at_k == 0.2  # 1 hit in top 5
    assert report.mean_recall_at_k == 1.0
    assert report.mrr == 1.0
    assert report.mean_ndcg_at_k > 0.9


def test_fastapi_search_endpoint(api_test_db, auth_headers):
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
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] >= 1
    assert data["results"][0]["document_id"] == str(doc_id)
    assert "9:00 AM" in data["results"][0]["content"]


def test_fastapi_context_endpoint(api_test_db, auth_headers):
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
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    ctx = data["context"]
    assert ctx["chunk_count"] >= 1
    assert "Employee Handbook" in ctx["context_text"]
    assert "20 days" in ctx["context_text"]
    assert len(ctx["citations"]) >= 1


def test_fastapi_qa_endpoint_cache_and_fallback(api_test_db, auth_headers):
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
        headers=auth_headers,
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
        headers=auth_headers,
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
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["cache_hit"] is True
    assert "9:00 AM" in d2["answer_text"]


def test_fastapi_graph_search_endpoint(api_test_db, auth_headers):
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
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] >= 1


def test_fastapi_cache_invalidate_endpoint(api_test_db, auth_headers):
    """Verify POST /retrieval/cache/invalidate invalidates cache entries."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    resp = client.post(
        "/retrieval/cache/invalidate",
        json={
            "organization_id": str(org_id),
            "document_id": str(doc_id),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "invalidated_count" in resp.json()


def test_fastapi_evaluate_endpoint(api_test_db, auth_headers):
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
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "hybrid"
    assert data["total_queries"] == 1
    assert data["mrr"] > 0.0
    assert data["mean_precision_at_k"] > 0.0


def test_fastapi_backend_endpoints_and_health(api_test_db):
    """Verify root health check and Person 1 RetrievalClient compatibility endpoints."""
    engine, org_id, doc_id, c1, c2 = api_test_db
    client = TestClient(app)

    # 1. Health check
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "ok"
    assert h_resp.json()["service"] == "enterprise_retrieval"

    # 2. Passage Search (Person 1 contract)
    s_resp = client.post(
        "/search",
        json={
            "query": "working hours",
            "access_scope": "public",
            "top_k": 5,
        },
    )
    assert s_resp.status_code == 200
    passages = s_resp.json()
    assert len(passages) >= 1
    assert "9:00 AM" in passages[0]["content"]
    assert passages[0]["chunk_id"] == str(c1.chunk_id)

    # 3. Single passage by ID
    p_resp = client.get(f"/passage/{c1.chunk_id}")
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert p_data["chunk_id"] == str(c1.chunk_id)
    assert p_data["content"] == c1.content
