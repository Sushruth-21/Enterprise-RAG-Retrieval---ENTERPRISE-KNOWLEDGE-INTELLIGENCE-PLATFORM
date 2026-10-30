import hashlib
import uuid
from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from orchestrator import IngestionOrchestrator, IngestionRequest
from scripts.generate_mock_documents import (
    generate_mock_docx,
    generate_mock_markdown,
    generate_mock_pdf,
    generate_mock_text,
)


@pytest.fixture
def db_session():
    """Provides a fresh in-memory database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def mock_docs_dir(tmp_path: Path) -> Path:
    """Generates all 4 format mock documents into a temporary directory."""
    d = tmp_path / "mock_docs"
    d.mkdir(parents=True, exist_ok=True)
    generate_mock_markdown(d / "sample_policy.md")
    generate_mock_text(d / "sample_policy.txt")
    generate_mock_docx(d / "sample_architecture.docx")
    generate_mock_pdf(d / "sample_milestones.pdf")
    return d


# =========================================================================
# 1. Parsing & End-to-End Ingestion for PDF & DOCX
# =========================================================================
def test_pdf_and_docx_pipeline_ingestion(db_session: Session, mock_docs_dir: Path):
    org_id = uuid.uuid4()

    # 1. Ingest DOCX
    docx_req = IngestionRequest(
        file_path=mock_docs_dir / "sample_architecture.docx",
        organization_id=org_id,
        canonical_id="ARCH-DOC",
        version="1.0",
        effective_date=date(2024, 1, 1),
    )
    docx_res = IngestionOrchestrator.ingest_document(db_session, docx_req)
    assert docx_res.success is True
    assert docx_res.total_chunks > 0
    assert docx_res.metadata["table_count"] >= 1

    # Verify DOCX table preservation in database chunks
    docx_chunks = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == docx_res.document_id)
    ).all()
    # Ensure database contains Markdown table syntax (| ... |)
    assert any("| PostgreSQL 16 |" in c.content for c in docx_chunks)
    assert any("| Workload Type |" in c.content for c in docx_chunks)

    # 2. Ingest PDF
    pdf_req = IngestionRequest(
        file_path=mock_docs_dir / "sample_milestones.pdf",
        organization_id=org_id,
        canonical_id="MILESTONE-DOC",
        version="1.0",
        effective_date=date(2024, 1, 1),
    )
    pdf_res = IngestionOrchestrator.ingest_document(db_session, pdf_req)
    assert pdf_res.success is True
    assert pdf_res.total_pages == 2
    assert pdf_res.total_chunks > 0

    # Verify PDF table preservation in database chunks
    pdf_chunks = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == pdf_res.document_id)
    ).all()
    assert any("DocumentFormat" in c.content or "Throughput" in c.content for c in pdf_chunks)
    assert any("PyMuPDF" in c.content for c in pdf_chunks)


# =========================================================================
# 2. Chunker Validation: Table Unsplit, Headings Preserved, Hash Accuracy
# =========================================================================
def test_chunker_validation_table_integrity_and_hashes(db_session: Session, mock_docs_dir: Path):
    org_id = uuid.uuid4()

    req = IngestionRequest(
        file_path=mock_docs_dir / "sample_policy.md",
        organization_id=org_id,
        canonical_id="SEC-POLICY",
        version="1.0",
        effective_date=date(2024, 1, 1),
    )
    res = IngestionOrchestrator.ingest_document(db_session, req)
    assert res.success is True

    chunks = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == res.document_id)
    ).all()

    # A. Verify table is not split across multiple fragments
    table_chunks = [c for c in chunks if "| Deployment Tier | Environment |" in c.content]
    assert len(table_chunks) == 1
    tbl_c = table_chunks[0]

    # Verify all 3 tiers exist inside the single chunk
    assert "Tier-1" in tbl_c.content
    assert "Tier-2" in tbl_c.content
    assert "Tier-3" in tbl_c.content

    # B. Verify heading / section context is preserved
    for c in chunks:
        assert c.section_context is not None and len(c.section_context) > 0
        assert c.content.startswith(f"[{c.section_context}]\n\n")

    # C. Verify SHA-256 chunk hash accuracy
    for c in chunks:
        recomputed_hash = hashlib.sha256(c.content.encode("utf-8")).hexdigest()
        assert c.chunk_hash == recomputed_hash


# =========================================================================
# 3. Version Manager: Transactional Cascading of 'superseded' Status
# =========================================================================
def test_version_manager_transactional_supersede(db_session: Session, mock_docs_dir: Path):
    org_id = uuid.uuid4()

    # Step 1: Ingest Original Version 1.0 (sample_policy.txt)
    v1_req = IngestionRequest(
        file_path=mock_docs_dir / "sample_policy.txt",
        organization_id=org_id,
        canonical_id="CORP-REIMBURSEMENT",
        version="1.0",
        effective_date=date(2023, 1, 1),
    )
    v1_res = IngestionOrchestrator.ingest_document(db_session, v1_req)
    assert v1_res.success is True
    v1_id = v1_res.document_id

    # Verify v1 is current
    v1_doc = db_session.scalar(select(DocumentDB).where(DocumentDB.id == v1_id))
    assert v1_doc.status == DocumentStatus.CURRENT
    v1_chunks = db_session.scalars(select(ChunkDB).where(ChunkDB.document_id == v1_id)).all()
    assert all(c.document_status == DocumentStatus.CURRENT for c in v1_chunks)
    assert all(c.processing_status == ProcessingStatus.PENDING for c in v1_chunks)

    # Step 2: Create modified Version 2.0 file
    v2_file = mock_docs_dir / "sample_policy_v2.txt"
    v2_content = """EMPLOYEE EXPENSE AND REIMBURSEMENT POLICY v2.0
===============================================

1. SUBMISSION GUIDELINES
Updated reimbursement window: submit claims within 15 days of travel.
\f
2. DAILY PER DIEM CAPS
| Category | Global Cap |
| --- | --- |
| Daily Meals | $150.00 |
"""
    v2_file.write_text(v2_content, encoding="utf-8")

    # Step 3: Ingest Version 2.0 with explicit supersedes_id
    v2_req = IngestionRequest(
        file_path=v2_file,
        organization_id=org_id,
        canonical_id="CORP-REIMBURSEMENT",
        version="2.0",
        effective_date=date(2024, 1, 1),
        supersedes_id=v1_id,
    )
    v2_res = IngestionOrchestrator.ingest_document(db_session, v2_req)
    assert v2_res.success is True
    v2_id = v2_res.document_id

    # Step 4: Verify Old v1 Document and ALL v1 Chunks are 'superseded'
    v1_doc_after = db_session.scalar(select(DocumentDB).where(DocumentDB.id == v1_id))
    assert v1_doc_after.status == DocumentStatus.SUPERSEDED

    v1_chunks_after = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == v1_id)
    ).all()
    assert len(v1_chunks_after) > 0
    assert all(c.document_status == DocumentStatus.SUPERSEDED for c in v1_chunks_after)

    # Step 5: Verify New v2 Document and ALL v2 Chunks are 'current'
    v2_doc = db_session.scalar(select(DocumentDB).where(DocumentDB.id == v2_id))
    assert v2_doc.status == DocumentStatus.CURRENT
    assert v2_doc.supersedes_id == v1_id

    v2_chunks = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == v2_id)
    ).all()
    assert len(v2_chunks) > 0
    assert all(c.document_status == DocumentStatus.CURRENT for c in v2_chunks)
    assert all(c.processing_status == ProcessingStatus.PENDING for c in v2_chunks)
