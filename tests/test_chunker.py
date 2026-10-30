import hashlib
import uuid
import pytest

from chunking import StructureAwareChunker, split_document_into_chunks, count_tokens
from models.enums import DocumentStatus, ProcessingStatus
from models.schemas import ChunkModel
from parsers.models import ElementType, ParsedDocument, StructuralElement


def test_structure_aware_chunking_table_grouping():
    """Verify that tables are kept intact and grouped with preceding introductory text."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    elements = [
        StructuralElement(
            element_type=ElementType.HEADING_1,
            content="1. Reimbursement Policy",
            page_number=1,
            heading_hierarchy=["Corporate Handbook", "1. Reimbursement Policy"],
        ),
        StructuralElement(
            element_type=ElementType.PARAGRAPH,
            content="Employees can submit expense claims via the online portal.",
            page_number=1,
            heading_hierarchy=["Corporate Handbook", "1. Reimbursement Policy"],
        ),
        StructuralElement(
            element_type=ElementType.PARAGRAPH,
            content="The following schedule outlines daily expense caps:",
            page_number=1,
            heading_hierarchy=["Corporate Handbook", "1. Reimbursement Policy"],
        ),
        StructuralElement(
            element_type=ElementType.TABLE,
            content=(
                "| Category | Cap |\n"
                "| --- | --- |\n"
                "| Breakfast | $25 |\n"
                "| Lunch | $35 |\n"
                "| Dinner | $60 |"
            ),
            page_number=1,
            heading_hierarchy=["Corporate Handbook", "1. Reimbursement Policy"],
        ),
    ]

    parsed_doc = ParsedDocument(
        file_path="handbook.pdf",
        file_type="pdf",
        title="Corporate Handbook",
        elements=elements,
        total_pages=1,
        success=True,
    )

    chunks = split_document_into_chunks(
        parsed_doc=parsed_doc,
        document_id=doc_id,
        organization_id=org_id,
        min_tokens=50,
        max_tokens=400,
    )

    assert len(chunks) >= 1
    # Find chunk containing the table
    table_chunks = [c for c in chunks if "| Category | Cap |" in c.content]
    assert len(table_chunks) == 1

    tbl_chunk = table_chunks[0]
    # Check table was grouped with introductory sentence
    assert "The following schedule outlines daily expense caps:" in tbl_chunk.content
    assert "| Breakfast | $25 |" in tbl_chunk.content


def test_context_preservation_and_hashing():
    """Verify section_context prepending and SHA-256 calculation."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    elements = [
        StructuralElement(
            element_type=ElementType.HEADING_1,
            content="2. Data Privacy",
            page_number=3,
            heading_hierarchy=["Legal", "2. Data Privacy"],
        ),
        StructuralElement(
            element_type=ElementType.PARAGRAPH,
            content="Customer PII must be encrypted at rest with keys managed in KMS.",
            page_number=3,
            heading_hierarchy=["Legal", "2. Data Privacy"],
        ),
    ]

    parsed_doc = ParsedDocument(
        file_path="legal.docx",
        file_type="docx",
        title="Legal Guidelines",
        elements=elements,
        total_pages=3,
        success=True,
    )

    chunks = split_document_into_chunks(
        parsed_doc=parsed_doc,
        document_id=doc_id,
        organization_id=org_id,
    )

    assert len(chunks) == 1
    c = chunks[0]

    # Context verification
    assert c.section_context == "Legal > 2. Data Privacy"
    assert c.content.startswith("[Legal > 2. Data Privacy]\n\n")

    # Hash verification
    expected_hash = hashlib.sha256(c.content.encode("utf-8")).hexdigest()
    assert c.chunk_hash == expected_hash

    # Sequential ordering and status
    assert c.chunk_index == 0
    assert c.processing_status == ProcessingStatus.PENDING
    assert c.document_status == DocumentStatus.CURRENT
    assert c.page_number == 3


def test_large_table_splitting_preserves_headers():
    """Verify that oversized tables are split with repeated header rows."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    # Create a tall markdown table
    headers = "| ID | Transaction Reference | Amount | Status | Notes |\n| --- | --- | --- | --- | --- |"
    rows = [f"| {i} | TXN-REF-2024-{i:04d} | ${i * 10}.00 | Approved | Transaction verified |" for i in range(1, 40)]
    large_table_content = headers + "\n" + "\n".join(rows)

    elements = [
        StructuralElement(
            element_type=ElementType.TABLE,
            content=large_table_content,
            page_number=1,
            heading_hierarchy=["Financials", "Transactions"],
        )
    ]

    parsed_doc = ParsedDocument(
        file_path="ledger.txt",
        file_type="txt",
        title="Ledger",
        elements=elements,
        total_pages=1,
        success=True,
    )

    chunker = StructureAwareChunker(min_tokens=100, max_tokens=250)
    chunks = chunker.chunk_document(
        parsed_doc=parsed_doc,
        document_id=doc_id,
        organization_id=org_id,
    )

    assert len(chunks) > 1
    # Verify every sub-chunk containing rows preserves the table header
    for c in chunks:
        assert "| ID | Transaction Reference | Amount | Status | Notes |" in c.content
        assert "| --- | --- | --- | --- | --- |" in c.content

    # Verify sequential chunk indexing
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
