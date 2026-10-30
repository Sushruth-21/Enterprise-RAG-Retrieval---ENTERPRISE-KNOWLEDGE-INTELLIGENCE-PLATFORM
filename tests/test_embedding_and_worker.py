import hashlib
import uuid
from datetime import date
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.embedding import BGEEmbeddingService
from retrieval.worker import EmbeddingWorker


@pytest.fixture(scope="module")
def embedding_service():
    """Shared embedding service instance for testing."""
    return BGEEmbeddingService(model_name="BAAI/bge-small-en-v1.5")


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite database engine for worker testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_bge_embedding_service_dimensions_and_normalization(embedding_service):
    """Verify BGE embedding generator outputs 384-dim normalized vectors."""
    docs = [
        "Company travel expenses must be submitted within 30 days of trip completion.",
        "Meal per diem allowance is capped at $75 per calendar day.",
    ]
    embeddings = embedding_service.embed_documents(docs)

    assert len(embeddings) == 2
    for vec in embeddings:
        assert len(vec) == 384
        # Verify L2 norm is approximately 1.0
        norm = sum(x * x for x in vec) ** 0.5
        assert pytest.approx(norm, rel=1e-3) == 1.0


def test_bge_query_embedding_instruction_prefix(embedding_service):
    """Verify query embedding embeds with BGE query instruction prefix."""
    query = "What is the per diem limit for travel meals?"
    q_vec = embedding_service.embed_query(query)

    assert len(q_vec) == 384
    norm = sum(x * x for x in q_vec) ** 0.5
    assert pytest.approx(norm, rel=1e-3) == 1.0


def test_embedding_worker_batch_processing_and_deduplication(sqlite_engine, embedding_service):
    """Verify worker processes pending chunks, assigns embeddings, and reuses identical hashes."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    content_text = "Standard expense report submission rules."
    c_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

    with Session(sqlite_engine) as session:
        # Create parent document
        doc = DocumentDB(
            id=doc_id,
            organization_id=org_id,
            name="Policy 1",
            canonical_id="POL-01",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/pol1.pdf",
            file_hash="dummy_hash_1",
        )
        session.add(doc)

        # Chunk 1: pending
        chunk1 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name="Policy 1",
            version="1.0",
            chunk_index=0,
            section_context="Expenses > Filing",
            page_number=1,
            content=content_text,
            chunk_hash=c_hash,
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.PENDING,
        )
        # Chunk 2: different content
        content_text_2 = "Receipts required for all purchases over $25."
        chunk2 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name="Policy 1",
            version="1.0",
            chunk_index=1,
            section_context="Expenses > Receipts",
            page_number=1,
            content=content_text_2,
            chunk_hash=hashlib.sha256(content_text_2.encode("utf-8")).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.PENDING,
        )
        session.add_all([chunk1, chunk2])
        session.commit()

        # Run worker for batch
        worker = EmbeddingWorker(embedding_service=embedding_service)
        processed_count = worker.process_batch(session, batch_size=10, organization_id=org_id)
        assert processed_count == 2

        # Check completed status and non-null embeddings
        c1_reloaded = session.scalar(select(ChunkDB).where(ChunkDB.chunk_id == chunk1.chunk_id))
        c2_reloaded = session.scalar(select(ChunkDB).where(ChunkDB.chunk_id == chunk2.chunk_id))
        assert c1_reloaded.processing_status == ProcessingStatus.COMPLETED
        assert c2_reloaded.processing_status == ProcessingStatus.COMPLETED
        assert len(c1_reloaded.embedding) == 384
        assert len(c2_reloaded.embedding) == 384

        # Add Chunk 3: identical content and hash as Chunk 1
        chunk3 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name="Policy 1",
            version="1.0",
            chunk_index=2,
            section_context="Expenses > Filing Duplicate",
            page_number=2,
            content=content_text,
            chunk_hash=c_hash,
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.PENDING,
        )
        session.add(chunk3)
        session.commit()

        # Process Chunk 3: worker should deduplicate and reuse Chunk 1's embedding
        processed_dedup = worker.process_batch(session, batch_size=10, organization_id=org_id)
        assert processed_dedup == 1

        c3_reloaded = session.scalar(select(ChunkDB).where(ChunkDB.chunk_id == chunk3.chunk_id))
        assert c3_reloaded.processing_status == ProcessingStatus.COMPLETED
        assert c3_reloaded.embedding == c1_reloaded.embedding


def test_embedding_worker_error_handling(sqlite_engine):
    """Verify worker marks chunks as FAILED if embedding generation encounters an error."""
    class FailingEmbeddingService:
        def embed_documents(self, texts, batch_size=32):
            raise RuntimeError("Inference hardware unavailable")

    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    with Session(sqlite_engine) as session:
        doc = DocumentDB(
            id=doc_id,
            organization_id=org_id,
            name="Policy Err",
            canonical_id="POL-ERR",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/err.pdf",
            file_hash="dummy_err_hash",
        )
        session.add(doc)

        chunk = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name="Policy Err",
            version="1.0",
            chunk_index=0,
            section_context="Error Section",
            page_number=1,
            content="Error trigger content",
            chunk_hash=hashlib.sha256(b"Error trigger content").hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.PENDING,
        )
        session.add(chunk)
        session.commit()

        worker = EmbeddingWorker(embedding_service=FailingEmbeddingService())
        with pytest.raises(RuntimeError):
            worker.process_batch(session, batch_size=10, organization_id=org_id)

        # Confirm chunk was marked as FAILED
        reloaded = session.scalar(select(ChunkDB).where(ChunkDB.chunk_id == chunk.chunk_id))
        assert reloaded.processing_status == ProcessingStatus.FAILED
