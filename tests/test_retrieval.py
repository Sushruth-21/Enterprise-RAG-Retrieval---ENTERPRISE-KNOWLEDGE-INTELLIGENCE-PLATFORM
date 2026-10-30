from datetime import date
import hashlib
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.embedding import BGEEmbeddingService
from retrieval.fulltext_search import FullTextRetriever
from retrieval.hybrid import HybridRetriever
from retrieval.vector_search import VectorRetriever


@pytest.fixture(scope="module")
def embedding_service():
    return BGEEmbeddingService(model_name="BAAI/bge-small-en-v1.5")


@pytest.fixture
def populated_db(embedding_service):
    """Seed test database with multi-tenant, versioned, and superseded policy documents."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    doc_v1_id = uuid.uuid4()
    doc_v2_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    with Session(engine) as session:
        # Org A - Document V1 (SUPERSEDED)
        doc_v1 = DocumentDB(
            id=doc_v1_id,
            organization_id=org_a,
            name="Travel Policy",
            canonical_id="CORP-TRV-01",
            version="1.0",
            status=DocumentStatus.SUPERSEDED,
            effective_date=date(2022, 1, 1),
            file_uri="s3://test/travel_v1.pdf",
            file_hash="hash_v1",
        )
        # Org A - Document V2 (CURRENT)
        doc_v2 = DocumentDB(
            id=doc_v2_id,
            organization_id=org_a,
            name="Travel Policy",
            canonical_id="CORP-TRV-01",
            version="2.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/travel_v2.pdf",
            file_hash="hash_v2",
            supersedes_id=doc_v1_id,
        )
        # Org B - Document (CURRENT)
        doc_b = DocumentDB(
            id=doc_b_id,
            organization_id=org_b,
            name="Org B Travel Policy",
            canonical_id="ORGB-TRV-01",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/travel_b.pdf",
            file_hash="hash_b",
        )
        session.add_all([doc_v1, doc_v2, doc_b])
        session.flush()

        # Text chunks
        c1_text = "The old 2022 per diem meal allowance was capped strictly at $50 per day."
        c2_text = "Under the updated 2024 policy, the daily per diem rate for travel meals is $85."
        c3_text = "Org B confidential meal stipend is fixed at $120 per day."

        # Compute embeddings for chunks
        embs = embedding_service.embed_documents([c1_text, c2_text, c3_text])

        chunk_v1 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_a,
            document_id=doc_v1_id,
            document_name="Travel Policy",
            version="1.0",
            chunk_index=0,
            section_context="Reimbursements > Meal Rates",
            page_number=2,
            content=c1_text,
            chunk_hash=hashlib.sha256(c1_text.encode()).hexdigest(),
            document_status=DocumentStatus.SUPERSEDED,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[0],
        )

        chunk_v2 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_a,
            document_id=doc_v2_id,
            document_name="Travel Policy",
            version="2.0",
            chunk_index=0,
            section_context="Reimbursements > Meal Rates",
            page_number=2,
            content=c2_text,
            chunk_hash=hashlib.sha256(c2_text.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[1],
        )

        chunk_b = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_b,
            document_id=doc_b_id,
            document_name="Org B Travel Policy",
            version="1.0",
            chunk_index=0,
            section_context="Compensation > Travel",
            page_number=1,
            content=c3_text,
            chunk_hash=hashlib.sha256(c3_text.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
            embedding=embs[2],
        )

        session.add_all([chunk_v1, chunk_v2, chunk_b])
        session.commit()

    return engine, org_a, org_b, doc_v1_id, doc_v2_id


def test_vector_retriever_current_only_and_tenant_isolation(populated_db, embedding_service):
    """Verify VectorRetriever isolates tenants and excludes superseded policies."""
    engine, org_a, org_b, doc_v1_id, doc_v2_id = populated_db
    retriever = VectorRetriever(embedding_service=embedding_service)

    with Session(engine) as session:
        # Search Org A for meal per diem
        results = retriever.search(
            session=session,
            organization_id=org_a,
            query="What is the meal per diem rate?",
            top_k=5,
            current_only=True,
        )

        assert len(results) == 1
        top_match = results[0]
        # Must return V2, never superseded V1
        assert top_match.document_id == doc_v2_id
        assert top_match.version == "2.0"
        assert "$85" in top_match.content
        assert top_match.source_method == "dense"

        # Search Org B - must NOT leak Org A documents
        results_b = retriever.search(
            session=session,
            organization_id=org_b,
            query="meal allowance rate",
            top_k=5,
            current_only=True,
        )
        assert len(results_b) == 1
        assert "$120" in results_b[0].content


def test_vector_retriever_historical_snapshot(populated_db, embedding_service):
    """Verify VectorRetriever can query historical document versions when explicitly requested."""
    engine, org_a, _, doc_v1_id, _ = populated_db
    retriever = VectorRetriever(embedding_service=embedding_service)

    with Session(engine) as session:
        # Query with current_only=False and historical date cutoff
        results = retriever.search(
            session=session,
            organization_id=org_a,
            query="What was the per diem meal rate in 2022?",
            top_k=5,
            current_only=False,
            as_of_date=date(2022, 12, 31),
        )

        # Should match V1 since effective_date is 2022-01-01 <= 2022-12-31
        assert len(results) == 1
        assert results[0].document_id == doc_v1_id
        assert "$50" in results[0].content


def test_fulltext_retriever_bm25_lexical_search(populated_db):
    """Verify FullTextRetriever performs lexical search, tenant isolation, and status filtering."""
    engine, org_a, org_b, _, doc_v2_id = populated_db
    retriever = FullTextRetriever()

    with Session(engine) as session:
        results = retriever.search(
            session=session,
            organization_id=org_a,
            query="updated 2024 policy per diem rate",
            top_k=5,
            current_only=True,
        )

        assert len(results) == 1
        assert results[0].document_id == doc_v2_id
        assert results[0].source_method == "sparse"
        assert "$85" in results[0].content


def test_hybrid_retriever_reciprocal_rank_fusion(populated_db, embedding_service):
    """Verify HybridRetriever fuses dense and sparse results using RRF scores."""
    engine, org_a, _, _, doc_v2_id = populated_db
    hybrid = HybridRetriever(
        vector_retriever=VectorRetriever(embedding_service=embedding_service),
        fulltext_retriever=FullTextRetriever(),
        rrf_k=60,
    )

    with Session(engine) as session:
        results = hybrid.search(
            session=session,
            organization_id=org_a,
            query="per diem meal rate travel policy",
            top_k=5,
            current_only=True,
        )

        assert len(results) == 1
        item = results[0]
        assert item.document_id == doc_v2_id
        assert item.source_method == "hybrid"
        # Since it ranked #1 in both dense and sparse, RRF score should be 1/(60+1) + 1/(60+1) = 2/61 ~ 0.03278
        expected_score = 1.0 / 61.0 + 1.0 / 61.0
        assert pytest.approx(item.score, rel=1e-3) == expected_score
        assert item.metadata["dense_rank"] == 1
        assert item.metadata["sparse_rank"] == 1
