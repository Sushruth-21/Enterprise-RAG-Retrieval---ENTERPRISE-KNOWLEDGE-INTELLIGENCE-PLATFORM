import os
import uuid
from datetime import date, datetime
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB, QACacheEntry as QACacheEntryDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.cache import SemanticQACache
from retrieval.embedding import BGEEmbeddingService
from retrieval.fulltext_search import FullTextRetriever
from retrieval.hybrid import HybridRetriever
from retrieval.vector_search import VectorRetriever
from retrieval.worker import EmbeddingWorker


def get_postgres_url() -> str:
    """Retrieve PostgreSQL connection string from environment or standard test configuration."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5433")
    db = os.getenv("POSTGRES_DB", "enterprise_retrieval")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture(scope="module")
def pg_engine():
    """Module-level fixture to connect to PostgreSQL with pgvector enabled."""
    url = get_postgres_url()
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            # Verify PostgreSQL and pgvector extension
            res = conn.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")).fetchone()
            if not res:
                pytest.skip("PostgreSQL connection succeeded but 'vector' extension is not installed.")
        # Ensure tables exist
        Base.metadata.create_all(engine)
        return engine
    except Exception as e:
        pytest.skip(f"PostgreSQL infrastructure unavailable at {url}: {e}")


@pytest.fixture(scope="module")
def embedding_service():
    """Actual BGE embedding service for real inference."""
    return BGEEmbeddingService(model_name="BAAI/bge-small-en-v1.5")


@pytest.fixture
def pg_session(pg_engine):
    """Yields a clean SQLAlchemy session connected to real PostgreSQL."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()


def test_1_pg_insert_organization_document_and_chunks(pg_session):
    """Verify inserting Document and Chunk records into real PostgreSQL tables."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Enterprise Remote Work Policy",
        canonical_id="CORP-REMOTE-01",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://enterprise-policies/remote_work.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.flush()

    chunk = ChunkDB(
        chunk_id=chunk_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=0,
        section_context="1.0 Eligibility > 1.1 Scope",
        page_number=1,
        content="Full-time employees with at least 6 months tenure are eligible to apply for remote work.",
        chunk_hash=f"chunk_hash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.PENDING,
    )
    pg_session.add(chunk)
    pg_session.commit()

    # Query back using PostgreSQL
    loaded_doc = pg_session.scalar(select(DocumentDB).where(DocumentDB.id == doc_id))
    loaded_chunk = pg_session.scalar(select(ChunkDB).where(ChunkDB.chunk_id == chunk_id))

    assert loaded_doc is not None
    assert loaded_doc.organization_id == org_id
    assert loaded_chunk is not None
    assert loaded_chunk.document_id == doc_id
    assert loaded_chunk.processing_status == ProcessingStatus.PENDING


def test_2_pg_bge_embeddings_and_vector_storage(pg_session, embedding_service):
    """Generate actual BGE embeddings and persist into PostgreSQL Vector(384) column."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    text_content = "Employees working remotely receive a one-time home office equipment stipend of $500."

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Equipment Stipend Guide",
        canonical_id="CORP-EQP-01",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://policies/equipment.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.flush()

    # Generate real BGE vector
    vec = embedding_service.embed_single_document(text_content)
    assert len(vec) == 384

    chunk = ChunkDB(
        chunk_id=chunk_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=0,
        section_context="Stipends > Equipment",
        page_number=2,
        content=text_content,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vec,
    )
    pg_session.add(chunk)
    pg_session.commit()

    # Verify native pgvector query directly with psycopg2/SQLAlchemy text
    row = pg_session.execute(
        text("SELECT chunk_id, embedding <=> :query_vec AS dist FROM chunks WHERE chunk_id = :cid"),
        {"query_vec": str(vec), "cid": str(chunk_id)},
    ).fetchone()

    assert row is not None
    # Distance to itself must be approximately 0.0
    assert row.dist < 0.001


def test_3_pg_native_vector_cosine_distance_search(pg_session, embedding_service):
    """Verify VectorRetriever executes native PostgreSQL cosine distance (<=>) queries."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Healthcare Policy 2024",
        canonical_id="CORP-BEN-01",
        version="2.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://policies/health.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.flush()

    t1 = "Dental and vision coverage begins on the first calendar day of the month following hire date."
    t2 = "Vehicle parking reimbursement is capped at $150 per month in urban office garages."

    vecs = embedding_service.embed_documents([t1, t2])

    c1 = ChunkDB(
        chunk_id=c1_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=0,
        section_context="Benefits > Dental & Vision",
        page_number=3,
        content=t1,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vecs[0],
    )
    c2 = ChunkDB(
        chunk_id=c2_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=1,
        section_context="Parking > Commute",
        page_number=4,
        content=t2,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vecs[1],
    )
    pg_session.add_all([c1, c2])
    pg_session.commit()

    retriever = VectorRetriever(embedding_service=embedding_service)
    results = retriever.search(
        session=pg_session,
        organization_id=org_id,
        query="When does dental insurance start?",
        top_k=2,
        current_only=True,
    )

    assert len(results) >= 1
    top = results[0]
    assert top.chunk_id == c1_id
    assert "Dental and vision" in top.content
    assert top.source_method == "dense"
    assert "distance" in top.metadata


def test_4_pg_native_fulltext_search(pg_session):
    """Verify FullTextRetriever executes native PostgreSQL to_tsvector @@ websearch_to_tsquery."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    c_id = uuid.uuid4()

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Security Policy",
        canonical_id="CORP-SEC-01",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://policies/sec.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.flush()

    content = "Multi-factor authentication (MFA) using FIDO2 hardware security keys is strictly enforced."
    chunk = ChunkDB(
        chunk_id=c_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=0,
        section_context="Authentication Protocols",
        page_number=1,
        content=content,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
    )
    pg_session.add(chunk)
    pg_session.commit()

    retriever = FullTextRetriever()
    results = retriever.search(
        session=pg_session,
        organization_id=org_id,
        query="FIDO2 hardware security keys",
        top_k=5,
        current_only=True,
    )

    assert len(results) == 1
    assert results[0].chunk_id == c_id
    assert "FIDO2" in results[0].content
    assert results[0].source_method == "sparse"
    assert "ts_rank" in results[0].metadata


def test_5_pg_hybrid_reciprocal_rank_fusion(pg_session, embedding_service):
    """Verify HybridRetriever fuses native PostgreSQL vector and tsvector results."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    c_id = uuid.uuid4()

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Parental Leave Policy",
        canonical_id="CORP-HR-08",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://policies/parental.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.flush()

    content = "Eligible parents receive 16 weeks of fully paid parental bonding leave."
    vec = embedding_service.embed_single_document(content)

    chunk = ChunkDB(
        chunk_id=c_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=0,
        section_context="Family Benefits > Parental Leave",
        page_number=1,
        content=content,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vec,
    )
    pg_session.add(chunk)
    pg_session.commit()

    hybrid = HybridRetriever(
        vector_retriever=VectorRetriever(embedding_service=embedding_service),
        fulltext_retriever=FullTextRetriever(),
        rrf_k=60,
    )

    results = hybrid.search(
        session=pg_session,
        organization_id=org_id,
        query="paid parental leave bonding weeks",
        top_k=5,
        current_only=True,
    )

    assert len(results) >= 1
    assert results[0].chunk_id == c_id
    assert results[0].source_method == "hybrid"
    assert results[0].score > 0.0


def test_6_pg_tenant_isolation(pg_session, embedding_service):
    """Verify PostgreSQL queries strictly isolate tenant data."""
    org_alpha = uuid.uuid4()
    org_beta = uuid.uuid4()

    doc_alpha_id = uuid.uuid4()
    doc_beta_id = uuid.uuid4()

    doc_a = DocumentDB(
        id=doc_alpha_id,
        organization_id=org_alpha,
        name="Alpha Policy",
        canonical_id="ALPHA-01",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://alpha/doc.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    doc_b = DocumentDB(
        id=doc_beta_id,
        organization_id=org_beta,
        name="Beta Policy",
        canonical_id="BETA-01",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://beta/doc.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add_all([doc_a, doc_b])
    pg_session.flush()

    content = "Confidential business operations plan for project Neptune."
    vec = embedding_service.embed_single_document(content)

    c_a = ChunkDB(
        chunk_id=uuid.uuid4(),
        organization_id=org_alpha,
        document_id=doc_alpha_id,
        document_name=doc_a.name,
        version=doc_a.version,
        chunk_index=0,
        section_context="Operations",
        page_number=1,
        content=content,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vec,
    )
    pg_session.add(c_a)
    pg_session.commit()

    retriever = VectorRetriever(embedding_service=embedding_service)

    # Search as Org Beta -> MUST return 0 results
    results_beta = retriever.search(
        session=pg_session,
        organization_id=org_beta,
        query="project Neptune operations plan",
        top_k=5,
        current_only=True,
    )
    assert len(results_beta) == 0

    # Search as Org Alpha -> MUST return result
    results_alpha = retriever.search(
        session=pg_session,
        organization_id=org_alpha,
        query="project Neptune operations plan",
        top_k=5,
        current_only=True,
    )
    assert len(results_alpha) == 1
    assert results_alpha[0].chunk_id == c_a.chunk_id


def test_7_pg_current_vs_superseded_filtering(pg_session, embedding_service):
    """Verify PostgreSQL queries never retrieve superseded versions when current_only=True."""
    org_id = uuid.uuid4()
    doc_v1_id = uuid.uuid4()
    doc_v2_id = uuid.uuid4()

    doc_v1 = DocumentDB(
        id=doc_v1_id,
        organization_id=org_id,
        name="Severance Guidelines",
        canonical_id="CORP-SEV-01",
        version="1.0",
        status=DocumentStatus.SUPERSEDED,
        effective_date=date(2021, 1, 1),
        file_uri="s3://policies/sev_v1.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    doc_v2 = DocumentDB(
        id=doc_v2_id,
        organization_id=org_id,
        name="Severance Guidelines",
        canonical_id="CORP-SEV-01",
        version="2.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://policies/sev_v2.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
        supersedes_id=doc_v1_id,
    )
    pg_session.add_all([doc_v1, doc_v2])
    pg_session.flush()

    c1_text = "Legacy 2021 severance package grants 1 week of salary per year of service."
    c2_text = "Modern 2024 severance package grants 2 weeks of salary per year of service plus 3 months health."
    vecs = embedding_service.embed_documents([c1_text, c2_text])

    c1 = ChunkDB(
        chunk_id=uuid.uuid4(),
        organization_id=org_id,
        document_id=doc_v1_id,
        document_name=doc_v1.name,
        version=doc_v1.version,
        chunk_index=0,
        section_context="Severance",
        page_number=1,
        content=c1_text,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.SUPERSEDED,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vecs[0],
    )
    c2 = ChunkDB(
        chunk_id=uuid.uuid4(),
        organization_id=org_id,
        document_id=doc_v2_id,
        document_name=doc_v2.name,
        version=doc_v2.version,
        chunk_index=0,
        section_context="Severance",
        page_number=1,
        content=c2_text,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vecs[1],
    )
    pg_session.add_all([c1, c2])
    pg_session.commit()

    retriever = VectorRetriever(embedding_service=embedding_service)

    # Current only
    results_current = retriever.search(
        session=pg_session,
        organization_id=org_id,
        query="severance pay formula weeks per year",
        top_k=5,
        current_only=True,
    )
    assert len(results_current) == 1
    assert results_current[0].chunk_id == c2.chunk_id
    assert "2 weeks" in results_current[0].content

    # Including historical
    results_all = retriever.search(
        session=pg_session,
        organization_id=org_id,
        query="severance pay formula weeks per year",
        top_k=5,
        current_only=False,
    )
    returned_cids = {r.chunk_id for r in results_all}
    assert c1.chunk_id in returned_cids
    assert c2.chunk_id in returned_cids


def test_8_pg_effective_date_filtering(pg_session, embedding_service):
    """Verify PostgreSQL temporal queries respect effective date constraints."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    c_id = uuid.uuid4()

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Future Bonus Incentive Plan",
        canonical_id="CORP-BONUS-25",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2026, 1, 1),
        file_uri="s3://policies/bonus_2026.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.flush()

    content = "Annual executive performance bonuses are pegged to net recurring EBITDA margin."
    vec = embedding_service.embed_single_document(content)

    chunk = ChunkDB(
        chunk_id=c_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name=doc.name,
        version=doc.version,
        chunk_index=0,
        section_context="Incentive Compensation",
        page_number=1,
        content=content,
        chunk_hash=f"chash_{uuid.uuid4().hex}",
        document_status=DocumentStatus.CURRENT,
        processing_status=ProcessingStatus.COMPLETED,
        embedding=vec,
    )
    pg_session.add(chunk)
    pg_session.commit()

    retriever = VectorRetriever(embedding_service=embedding_service)

    # Query with as_of_date in 2025 (before effective date 2026-01-01) -> MUST NOT return
    res_2025 = retriever.search(
        session=pg_session,
        organization_id=org_id,
        query="executive performance bonus EBITDA",
        as_of_date=date(2025, 6, 1),
    )
    assert len(res_2025) == 0

    # Query with as_of_date in 2026 -> MUST return
    res_2026 = retriever.search(
        session=pg_session,
        organization_id=org_id,
        query="executive performance bonus EBITDA",
        as_of_date=date(2026, 6, 1),
    )
    assert len(res_2026) == 1
    assert res_2026[0].chunk_id == c_id


def test_9_pg_concurrent_embedding_workers_skip_locked(pg_engine, embedding_service):
    """Verify EmbeddingWorker uses PostgreSQL FOR UPDATE SKIP LOCKED without concurrency conflict."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    with session_factory() as session:
        doc = DocumentDB(
            id=doc_id,
            organization_id=org_id,
            name="Concurrent Worker Document",
            canonical_id="CORP-CONC-01",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://policies/concurrent.pdf",
            file_hash=f"hash_{uuid.uuid4().hex}",
        )
        session.add(doc)
        session.flush()

        chunks = []
        for i in range(4):
            c = ChunkDB(
                chunk_id=uuid.uuid4(),
                organization_id=org_id,
                document_id=doc_id,
                document_name=doc.name,
                version=doc.version,
                chunk_index=i,
                section_context=f"Section {i}",
                page_number=1,
                content=f"Concurrent test content chunk number {i} for worker execution.",
                chunk_hash=f"chash_conc_{i}_{uuid.uuid4().hex}",
                document_status=DocumentStatus.CURRENT,
                processing_status=ProcessingStatus.PENDING,
            )
            chunks.append(c)
        session.add_all(chunks)
        session.commit()

    worker = EmbeddingWorker(embedding_service=embedding_service)

    # Worker 1 takes batch size 2
    with session_factory() as s1:
        # Simulate worker 1 opening transaction with FOR UPDATE SKIP LOCKED
        count_w1 = worker.process_batch(s1, batch_size=2, organization_id=org_id)
        assert count_w1 == 2

    # Worker 2 takes next available pending batch
    with session_factory() as s2:
        count_w2 = worker.process_batch(s2, batch_size=2, organization_id=org_id)
        assert count_w2 == 2

    # Verify all 4 chunks completed
    with session_factory() as check_session:
        completed = check_session.scalars(
            select(ChunkDB)
            .where(ChunkDB.document_id == doc_id, ChunkDB.processing_status == ProcessingStatus.COMPLETED)
        ).all()
        assert len(completed) == 4
        for chunk in completed:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 384


def test_10_pg_semantic_qa_cache_dependency_invalidation(pg_session, embedding_service):
    """Verify real PostgreSQL QACacheEntry storage and source dependency invalidation."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    doc = DocumentDB(
        id=doc_id,
        organization_id=org_id,
        name="Data Retention Policy",
        canonical_id="CORP-RET-01",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://policies/retention.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
    )
    pg_session.add(doc)
    pg_session.commit()

    cache = SemanticQACache(embedding_service=embedding_service, similarity_threshold=0.85)

    # 1. Store answer
    cache.store_answer(
        session=pg_session,
        organization_id=org_id,
        query_text="What is the audit log retention period?",
        answer_text="Audit logs must be retained for at least 7 years.",
        formatted_context="Policy specifies 7-year retention period for audit trails.",
        source_document_ids=[doc_id],
        source_chunk_ids=[chunk_id],
    )

    # 2. Lookup -> Cache Hit
    hit = cache.lookup(
        session=pg_session,
        organization_id=org_id,
        query="What is the audit log retention period?",
    )
    assert hit.is_hit is True
    assert "7 years" in hit.answer_text

    # 3. Supersede source document in PostgreSQL
    doc.status = DocumentStatus.SUPERSEDED
    pg_session.commit()

    # 4. Subsequent lookup MUST detect superseded source in PostgreSQL and invalidate
    miss = cache.lookup(
        session=pg_session,
        organization_id=org_id,
        query="What is the audit log retention period?",
    )
    assert miss.is_hit is False
    assert miss.invalidation_reason is not None
    assert "superseded" in miss.invalidation_reason.lower()

    # 5. Check in PostgreSQL that is_valid is now FALSE
    entry_db = pg_session.scalar(
        select(QACacheEntryDB).where(QACacheEntryDB.organization_id == org_id)
    )
    assert entry_db.is_valid is False
