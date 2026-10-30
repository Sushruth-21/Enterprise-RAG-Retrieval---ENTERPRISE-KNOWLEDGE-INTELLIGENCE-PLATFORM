import hashlib
import uuid
from datetime import date
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from models.schemas import ChunkModel, DocumentCreate
from versioning import (
    DocumentNotFoundError,
    DuplicateDocumentError,
    TenantViolationError,
    VersionControlManager,
)


@pytest.fixture
def db_session():
    """Provides an in-memory SQLite database session for transactional testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_mock_chunks(org_id: uuid.UUID, doc_id: uuid.UUID, count: int = 3) -> list[ChunkModel]:
    chunks = []
    for i in range(count):
        content = f"[Section: Test] This is test chunk content number {i}."
        chunks.append(
            ChunkModel(
                chunk_id=uuid.uuid4(),
                organization_id=org_id,
                document_id=doc_id,
                document_name="Test Doc",
                version="1.0",
                chunk_index=i,
                section_context="Test",
                page_number=1,
                content=content,
                chunk_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                document_status=DocumentStatus.CURRENT,
            )
        )
    return chunks


def test_duplicate_file_hash_detection(db_session: Session):
    org_id = uuid.uuid4()
    file_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    doc_create_1 = DocumentCreate(
        organization_id=org_id,
        name="Employee Policy 2023.pdf",
        canonical_id="HR-POL-01",
        version="1.0",
        effective_date=date(2023, 1, 1),
        file_uri="s3://bucket/policy_v1.pdf",
        file_hash=file_hash,
    )

    # 1. First registration should succeed
    new_doc, _ = VersionControlManager.register_document_version(
        session=db_session,
        document_data=doc_create_1,
    )
    db_session.commit()
    assert new_doc.id is not None

    # 2. Duplicate upload of identical file hash in same org should raise DuplicateDocumentError
    doc_create_dup = DocumentCreate(
        organization_id=org_id,
        name="Employee Policy 2023 Renamed.pdf",  # Different filename, same hash!
        canonical_id="HR-POL-01",
        version="1.0.1",
        effective_date=date(2023, 1, 1),
        file_uri="s3://bucket/policy_renamed.pdf",
        file_hash=file_hash,
    )

    with pytest.raises(DuplicateDocumentError) as exc_info:
        VersionControlManager.register_document_version(
            session=db_session,
            document_data=doc_create_dup,
        )

    assert exc_info.value.existing_document_id == new_doc.id


def test_duplicate_file_hash_allowed_across_different_tenants(db_session: Session):
    org_1 = uuid.uuid4()
    org_2 = uuid.uuid4()
    shared_hash = "1111222233334444111122223333444411112222333344441111222233334444"

    doc_1 = DocumentCreate(
        organization_id=org_1,
        name="Contract.pdf",
        canonical_id="CONTRACT",
        version="1.0",
        effective_date=date(2024, 1, 1),
        file_uri="s3://bucket1/contract.pdf",
        file_hash=shared_hash,
    )
    doc_2 = DocumentCreate(
        organization_id=org_2,
        name="Contract.pdf",
        canonical_id="CONTRACT",
        version="1.0",
        effective_date=date(2024, 1, 1),
        file_uri="s3://bucket2/contract.pdf",
        file_hash=shared_hash,
    )

    # Both should succeed because they are in different organizations
    res1, _ = VersionControlManager.register_document_version(db_session, doc_1)
    res2, _ = VersionControlManager.register_document_version(db_session, doc_2)
    db_session.commit()

    assert res1.id != res2.id


def test_transactional_superseding_cascades_to_all_chunks(db_session: Session):
    """
    Verify that superseding an old document:
    1. Sets old document status to 'superseded'.
    2. Cascades status update to ALL existing chunks in the table.
    3. Sets new document and its chunks to 'current'.
    """
    org_id = uuid.uuid4()
    v1_hash = "1111111111111111111111111111111111111111111111111111111111111111"
    v2_hash = "2222222222222222222222222222222222222222222222222222222222222222"

    # Step 1: Ingest Version 1 with 3 chunks
    doc_v1_create = DocumentCreate(
        organization_id=org_id,
        name="Information Security Standard v1.0",
        canonical_id="SEC-STD-001",
        version="1.0",
        effective_date=date(2023, 1, 1),
        file_uri="s3://bucket/sec_v1.pdf",
        file_hash=v1_hash,
    )
    mock_chunks_v1 = _create_mock_chunks(org_id=org_id, doc_id=uuid.uuid4(), count=3)

    v1_doc, _ = VersionControlManager.register_document_version(
        session=db_session,
        document_data=doc_v1_create,
        chunks=mock_chunks_v1,
    )
    db_session.commit()
    v1_id = v1_doc.id

    # Verify initial v1 state
    reloaded_v1 = db_session.scalar(select(DocumentDB).where(DocumentDB.id == v1_id))
    assert reloaded_v1.status == DocumentStatus.CURRENT
    v1_chunks = db_session.scalars(select(ChunkDB).where(ChunkDB.document_id == v1_id)).all()
    assert len(v1_chunks) == 3
    assert all(c.document_status == DocumentStatus.CURRENT for c in v1_chunks)

    # Step 2: Ingest Version 2 that explicitly supersedes v1
    doc_v2_create = DocumentCreate(
        organization_id=org_id,
        name="Information Security Standard v2.0 (Updated)",  # Arbitrary filename!
        canonical_id="SEC-STD-001",
        version="2.0",
        effective_date=date(2024, 1, 1),
        file_uri="s3://bucket/sec_v2_final_revision.pdf",
        file_hash=v2_hash,
        supersedes_id=v1_id,  # Explicit lineage pointer
    )
    mock_chunks_v2 = _create_mock_chunks(org_id=org_id, doc_id=uuid.uuid4(), count=4)

    v2_doc, cascaded_count = VersionControlManager.register_document_version(
        session=db_session,
        document_data=doc_v2_create,
        chunks=mock_chunks_v2,
        supersedes_id=v1_id,
    )
    db_session.commit()
    v2_id = v2_doc.id

    assert cascaded_count == 3
    assert v2_doc.supersedes_id == v1_id
    assert v2_doc.status == DocumentStatus.CURRENT

    # Verify old v1 document status was changed to 'superseded'
    reloaded_v1 = db_session.scalar(select(DocumentDB).where(DocumentDB.id == v1_id))
    assert reloaded_v1.status == DocumentStatus.SUPERSEDED

    # Verify ALL v1 chunks were cascaded to 'superseded'
    v1_chunks_after = db_session.scalars(
        select(ChunkDB).where(ChunkDB.document_id == v1_id)
    ).all()
    assert len(v1_chunks_after) == 3
    assert all(c.document_status == DocumentStatus.SUPERSEDED for c in v1_chunks_after)

    # Verify new v2 chunks are 'current'
    v2_chunks = db_session.scalars(select(ChunkDB).where(ChunkDB.document_id == v2_id)).all()
    assert len(v2_chunks) == 4
    assert all(c.document_status == DocumentStatus.CURRENT for c in v2_chunks)
    assert all(c.processing_status == ProcessingStatus.PENDING for c in v2_chunks)


def test_invalid_supersedes_id_rejection(db_session: Session):
    """Ensure non-existent supersedes_id raises DocumentNotFoundError."""
    org_id = uuid.uuid4()
    ghost_id = uuid.uuid4()

    doc_create = DocumentCreate(
        organization_id=org_id,
        name="New Policy.pdf",
        canonical_id="POL-01",
        version="2.0",
        effective_date=date(2024, 1, 1),
        file_uri="s3://bucket/new.pdf",
        file_hash="9999999999999999999999999999999999999999999999999999999999999999",
        supersedes_id=ghost_id,
    )

    with pytest.raises(DocumentNotFoundError):
        VersionControlManager.register_document_version(
            session=db_session,
            document_data=doc_create,
            supersedes_id=ghost_id,
        )


def test_cross_tenant_supersedes_rejection(db_session: Session):
    """Prevent tenant A from superseding a document belonging to tenant B."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Create document under Tenant B
    doc_b = DocumentCreate(
        organization_id=tenant_b,
        name="Tenant B Doc.pdf",
        canonical_id="DOC-B",
        version="1.0",
        effective_date=date(2024, 1, 1),
        file_uri="s3://bucket/doc_b.pdf",
        file_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    b_record, _ = VersionControlManager.register_document_version(db_session, doc_b)
    db_session.commit()

    # Tenant A attempts to supersede Tenant B's document
    doc_a = DocumentCreate(
        organization_id=tenant_a,
        name="Tenant A Doc.pdf",
        canonical_id="DOC-A",
        version="1.0",
        effective_date=date(2024, 1, 1),
        file_uri="s3://bucket/doc_a.pdf",
        file_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        supersedes_id=b_record.id,
    )

    with pytest.raises(TenantViolationError):
        VersionControlManager.register_document_version(
            session=db_session,
            document_data=doc_a,
            supersedes_id=b_record.id,
        )
