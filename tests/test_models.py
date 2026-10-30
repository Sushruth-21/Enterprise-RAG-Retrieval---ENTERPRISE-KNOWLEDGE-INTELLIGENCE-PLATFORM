import hashlib
import uuid
from datetime import date
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import (
    Base,
    ChunkDB,
    ChunkModel,
    DocumentDB,
    DocumentModel,
    DocumentStatus,
    ProcessingStatus,
)


def test_chunk_pydantic_strictly_requires_all_fields_with_defaults():
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    sample_text = "Employees are eligible for a daily per diem rate of $75."
    chunk_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

    chunk = ChunkModel(
        chunk_id=chunk_id,
        organization_id=org_id,
        document_id=doc_id,
        document_name="Corporate Travel Policy",
        version="2.0",
        chunk_index=0,
        section_context="2.0 Reimbursement > 2.1 Per Diem",
        page_number=3,
        content=sample_text,
        chunk_hash=chunk_hash,
        document_status=DocumentStatus.CURRENT,
    )

    assert chunk.chunk_id == chunk_id
    assert chunk.organization_id == org_id
    assert chunk.document_id == doc_id
    assert chunk.document_name == "Corporate Travel Policy"
    assert chunk.version == "2.0"
    assert chunk.chunk_index == 0
    assert chunk.section_context == "2.0 Reimbursement > 2.1 Per Diem"
    assert chunk.page_number == 3
    assert chunk.content == sample_text
    assert chunk.chunk_hash == chunk_hash
    # Defaults verification
    assert chunk.embedding_model == "BAAI/bge-small-en-v1.5"
    assert chunk.processing_status == ProcessingStatus.PENDING
    assert chunk.document_status == DocumentStatus.CURRENT


def test_chunk_pydantic_validation_failure_on_missing_fields():
    # Omitting organization_id and chunk_hash should raise ValidationError
    with pytest.raises(ValidationError):
        ChunkModel(
            document_id=uuid.uuid4(),
            document_name="Policy Doc",
            version="1.0",
            chunk_index=0,
            content="Sample content",
            document_status=DocumentStatus.CURRENT,
            # organization_id, page_number, section_context, chunk_hash missing
        )


def test_document_pydantic_validation():
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    file_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    doc = DocumentModel(
        id=doc_id,
        organization_id=org_id,
        name="Security Policy 2024",
        canonical_id="SEC-POL-001",
        version="1.0",
        status=DocumentStatus.CURRENT,
        effective_date=date(2024, 1, 1),
        file_uri="s3://doc-bucket/policies/sec-pol-001.pdf",
        file_hash=file_hash,
        supersedes_id=None,
    )

    assert doc.id == doc_id
    assert doc.organization_id == org_id
    assert doc.name == "Security Policy 2024"
    assert doc.canonical_id == "SEC-POL-001"
    assert doc.status == DocumentStatus.CURRENT
    assert doc.file_hash == file_hash
    assert doc.supersedes_id is None


def test_sqlalchemy_lineage_and_chunks_multi_tenant():
    """Verify SQLite in-memory table creation, tenant boundary, sequential order, and lineage."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    org_id = uuid.uuid4()

    with Session(engine) as session:
        # 1. Insert original document v1
        doc_v1_id = uuid.uuid4()
        doc_v1 = DocumentDB(
            id=doc_v1_id,
            organization_id=org_id,
            name="Employee Handbook 2023",
            canonical_id="HR-HANDBOOK",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2023, 1, 1),
            file_uri="s3://bucket/handbook_2023.pdf",
            file_hash="1111111111111111111111111111111111111111111111111111111111111111",
        )
        session.add(doc_v1)
        session.commit()

        # 2. Add sequential chunks to v1
        chunk_0 = ChunkDB(
            organization_id=org_id,
            document_id=doc_v1.id,
            document_name=doc_v1.name,
            version=doc_v1.version,
            chunk_index=0,
            section_context="1. Benefits",
            page_number=1,
            content="Health insurance is provided after 30 days.",
            chunk_hash="aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111",
            document_status=doc_v1.status,
        )
        chunk_1 = ChunkDB(
            organization_id=org_id,
            document_id=doc_v1.id,
            document_name=doc_v1.name,
            version=doc_v1.version,
            chunk_index=1,
            section_context="2. Leave",
            page_number=2,
            content="Employees receive 20 days of paid time off.",
            chunk_hash="bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
            document_status=doc_v1.status,
        )
        session.add_all([chunk_0, chunk_1])
        session.commit()

        # Verify defaults in DB
        assert chunk_0.embedding_model == "BAAI/bge-small-en-v1.5"
        assert chunk_0.processing_status == ProcessingStatus.PENDING

        # 3. Insert superseded v2 document
        doc_v2_id = uuid.uuid4()
        doc_v2 = DocumentDB(
            id=doc_v2_id,
            organization_id=org_id,
            name="Employee Handbook 2024",
            canonical_id="HR-HANDBOOK",
            version="2.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            supersedes_id=doc_v1.id,  # Points to v1
            file_uri="s3://bucket/handbook_2024.pdf",
            file_hash="2222222222222222222222222222222222222222222222222222222222222222",
        )
        # Mark v1 and its chunks as superseded
        doc_v1.status = DocumentStatus.SUPERSEDED
        chunk_0.document_status = DocumentStatus.SUPERSEDED
        chunk_1.document_status = DocumentStatus.SUPERSEDED

        session.add(doc_v2)
        session.commit()

        # 4. Multi-tenant sequential retrieval check
        chunks = session.scalars(
            select(ChunkDB)
            .where(
                ChunkDB.organization_id == org_id,
                ChunkDB.document_id == doc_v1_id,
            )
            .order_by(ChunkDB.chunk_index)
        ).all()

        assert len(chunks) == 2
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1
        assert all(c.document_status == DocumentStatus.SUPERSEDED for c in chunks)

        # 5. Verify lineage graph traversal
        reloaded_v2 = session.scalar(select(DocumentDB).where(DocumentDB.id == doc_v2_id))
        assert reloaded_v2 is not None
        assert reloaded_v2.superseded_document.id == doc_v1_id
        assert reloaded_v2.superseded_document.status == DocumentStatus.SUPERSEDED
