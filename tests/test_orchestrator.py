import logging
import uuid
from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from orchestrator import IngestionOrchestrator, IngestionRequest, IngestionResult


@pytest.fixture
def db_session():
    """Provides an in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_markdown_file(tmp_path: Path) -> Path:
    content = """# Corporate Expense Reimbursement Policy

<!-- Page 1 -->
## 1. General Guidelines
All travel expenses must be submitted within 30 days of trip completion.
Original receipts must accompany all reimbursement requests exceeding $25.

<!-- Page 2 -->
## 2. Daily Per Diem Caps
The following table outlines our standard meal allowance across global tiers:

| Tier | Region | Breakfast | Lunch | Dinner |
| --- | --- | --- | --- | --- |
| Tier 1 | North America / EMEA | $20 | $30 | $50 |
| Tier 2 | APAC / LATAM | $15 | $25 | $40 |

Expenses exceeding these caps require pre-approval from the departmental director.
"""
    file_path = tmp_path / "expense_policy_v1.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_end_to_end_orchestrator_ingestion(db_session: Session, sample_markdown_file: Path, caplog):
    caplog.set_level(logging.INFO)
    org_id = uuid.uuid4()

    request = IngestionRequest(
        file_path=sample_markdown_file,
        organization_id=org_id,
        name="Corporate Expense Reimbursement Policy",
        canonical_id="CORP-FIN-POL-001",
        version="1.0",
        effective_date=date(2024, 1, 1),
    )

    result = IngestionOrchestrator.ingest_document(
        session=db_session,
        request=request,
    )

    assert result.success is True
    assert result.document_id is not None
    assert result.status == DocumentStatus.CURRENT
    assert result.total_chunks > 0
    assert result.total_pages == 2
    assert result.file_hash == IngestionOrchestrator.compute_file_hash(sample_markdown_file)

    # Verify Database State: Document
    doc = db_session.scalar(select(DocumentDB).where(DocumentDB.id == result.document_id))
    assert doc is not None
    assert doc.status == DocumentStatus.CURRENT
    assert doc.canonical_id == "CORP-FIN-POL-001"
    assert doc.version == "1.0"

    # Verify Database State: Chunks
    chunks = db_session.scalars(
        select(ChunkDB)
        .where(ChunkDB.document_id == result.document_id)
        .order_by(ChunkDB.chunk_index)
    ).all()

    assert len(chunks) == result.total_chunks
    assert chunks[0].chunk_index == 0
    assert all(c.processing_status == ProcessingStatus.PENDING for c in chunks)
    assert all(c.document_status == DocumentStatus.CURRENT for c in chunks)
    assert all(c.organization_id == org_id for c in chunks)

    # Verify log messages
    assert any("[STAGE 1 - HASHING]" in msg for msg in caplog.messages)
    assert any("[STAGE 3 - PARSING COMPLETED]" in msg for msg in caplog.messages)
    assert any("[STAGE 4 - CHUNKING COMPLETED]" in msg for msg in caplog.messages)
    assert any("[STAGE 5 - TRANSACTION COMMITTED]" in msg for msg in caplog.messages)


def test_orchestrator_duplicate_rejection(db_session: Session, sample_markdown_file: Path):
    org_id = uuid.uuid4()

    req = IngestionRequest(
        file_path=sample_markdown_file,
        organization_id=org_id,
        canonical_id="CORP-FIN-POL-001",
        version="1.0",
        effective_date=date(2024, 1, 1),
    )

    # First ingestion succeeds
    res1 = IngestionOrchestrator.ingest_document(db_session, req)
    assert res1.success is True

    # Duplicate ingestion fails gracefully without error
    res2 = IngestionOrchestrator.ingest_document(db_session, req, raise_on_error=False)
    assert res2.success is False
    assert "duplicate" in res2.error_message.lower()


def test_orchestrator_superseding_workflow(db_session: Session, tmp_path: Path):
    org_id = uuid.uuid4()

    # Create v1 file
    f_v1 = tmp_path / "contract_v1.txt"
    f_v1.write_text("1. Scope\nOriginal contract terms and conditions.\n", encoding="utf-8")

    req_v1 = IngestionRequest(
        file_path=f_v1,
        organization_id=org_id,
        name="Contract",
        canonical_id="CONTRACT-2024",
        version="1.0",
        effective_date=date(2024, 1, 1),
    )
    res_v1 = IngestionOrchestrator.ingest_document(db_session, req_v1)
    assert res_v1.success is True

    # Create v2 file
    f_v2 = tmp_path / "contract_v2.txt"
    f_v2.write_text("1. Scope\nAmended contract terms with updated indemnification.\n", encoding="utf-8")

    req_v2 = IngestionRequest(
        file_path=f_v2,
        organization_id=org_id,
        name="Contract Amendment",
        canonical_id="CONTRACT-2024",
        version="2.0",
        effective_date=date(2024, 6, 1),
        supersedes_id=res_v1.document_id,  # Explicit lineage
    )
    res_v2 = IngestionOrchestrator.ingest_document(db_session, req_v2)
    assert res_v2.success is True
    assert res_v2.superseded_chunks_count > 0

    # Verify v1 document is 'superseded'
    v1_doc = db_session.scalar(select(DocumentDB).where(DocumentDB.id == res_v1.document_id))
    assert v1_doc.status == DocumentStatus.SUPERSEDED

    # Verify all v1 chunks are 'superseded'
    v1_chunks = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == res_v1.document_id)
    ).all()
    assert all(c.document_status == DocumentStatus.SUPERSEDED for c in v1_chunks)

    # Verify v2 document and chunks are 'current'
    v2_doc = db_session.scalar(select(DocumentDB).where(DocumentDB.id == res_v2.document_id))
    assert v2_doc.status == DocumentStatus.CURRENT
    assert v2_doc.supersedes_id == res_v1.document_id
    v2_chunks = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == res_v2.document_id)
    ).all()
    assert all(c.document_status == DocumentStatus.CURRENT for c in v2_chunks)
