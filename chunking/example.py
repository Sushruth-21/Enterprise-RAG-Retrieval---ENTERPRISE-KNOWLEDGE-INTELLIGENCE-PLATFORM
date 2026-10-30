import sys
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from models.enums import DocumentStatus, ProcessingStatus
from parsers.models import ElementType, ParsedDocument, StructuralElement
from chunking import split_document_into_chunks, count_tokens


def run_chunking_demonstration():
    print("=" * 80)
    print("Intelligent Structure-Aware Chunking: Demonstration")
    print("=" * 80)

    # 1. Create synthetic ParsedDocument with Title, Headings, Paragraphs, and a Table
    doc_elements = [
        # Title
        StructuralElement(
            element_type=ElementType.TITLE,
            content="Global Information Security and Compliance Standard",
            page_number=1,
            heading_hierarchy=["Global Information Security"],
            heading_level=1,
        ),
        # Section 1
        StructuralElement(
            element_type=ElementType.HEADING_1,
            content="1. Access Control & Key Management",
            page_number=1,
            heading_hierarchy=["Global Information Security", "1. Access Control & Key Management"],
            heading_level=1,
        ),
        StructuralElement(
            element_type=ElementType.PARAGRAPH,
            content=(
                "All systems storing customer data must enforce hardware-backed multi-factor authentication (MFA). "
                "Session keys must be rotated at least every 90 days or immediately upon team member offboarding."
            ),
            page_number=1,
            heading_hierarchy=["Global Information Security", "1. Access Control & Key Management"],
        ),
        # Section 2 with Table and Preceding Explanatory Text
        StructuralElement(
            element_type=ElementType.HEADING_2,
            content="1.1 Infrastructure Security Tiers",
            page_number=2,
            heading_hierarchy=[
                "Global Information Security",
                "1. Access Control & Key Management",
                "1.1 Infrastructure Security Tiers",
            ],
            heading_level=2,
        ),
        # Explanatory text introducing the table
        StructuralElement(
            element_type=ElementType.PARAGRAPH,
            content=(
                "The following security matrix outlines required isolation controls, replication factors, "
                "and backup schedules across each deployment tier:"
            ),
            page_number=2,
            heading_hierarchy=[
                "Global Information Security",
                "1. Access Control & Key Management",
                "1.1 Infrastructure Security Tiers",
            ],
        ),
        # Table element
        StructuralElement(
            element_type=ElementType.TABLE,
            content=(
                "| Tier Level | Environment | Encryption At Rest | Replication Factor | RPO Target |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| Tier-1 | Production Core | AES-256-GCM | 3x Multi-Region | < 1 minute |\n"
                "| Tier-2 | Production Analytics | AES-256-CBC | 2x Single-Region | < 1 hour |\n"
                "| Tier-3 | Staging / QA | Platform Default | 1x Local | < 24 hours |"
            ),
            page_number=2,
            heading_hierarchy=[
                "Global Information Security",
                "1. Access Control & Key Management",
                "1.1 Infrastructure Security Tiers",
            ],
        ),
        # Concluding paragraph
        StructuralElement(
            element_type=ElementType.PARAGRAPH,
            content=(
                "Any deviations from this tiering matrix must receive written authorization from the CISO office "
                "prior to workload migration."
            ),
            page_number=2,
            heading_hierarchy=[
                "Global Information Security",
                "1. Access Control & Key Management",
                "1.1 Infrastructure Security Tiers",
            ],
        ),
    ]

    parsed_doc = ParsedDocument(
        file_path="s3://enterprise-policies/infosec-std-2024.pdf",
        file_type="pdf",
        title="Global Information Security and Compliance Standard",
        elements=doc_elements,
        total_pages=2,
        success=True,
    )

    # 2. Invoke Chunker
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    chunks = split_document_into_chunks(
        parsed_doc=parsed_doc,
        document_id=doc_id,
        organization_id=org_id,
        version="2.1",
        document_status=DocumentStatus.CURRENT,
        min_tokens=100,
        max_tokens=600,
    )

    print(f"\nTotal Chunks Produced: {len(chunks)}")
    print(f"Organization ID: {org_id}")
    print(f"Document ID:     {doc_id}\n")

    for c in chunks:
        tokens = count_tokens(c.content)
        print("-" * 80)
        print(f"Chunk #{c.chunk_index} | ID: {c.chunk_id}")
        print(f"  Page:              {c.page_number}")
        print(f"  Section Context:   {c.section_context}")
        print(f"  Chunk SHA-256:     {c.chunk_hash}")
        print(f"  Processing Status: {c.processing_status.value}")
        print(f"  Token Count:       {tokens} tokens")
        print(f"  Content Preview:\n")
        for line in c.content.splitlines():
            print(f"    {line}")
        print()

    # Assertions demonstrating contract compliance
    assert len(chunks) > 0
    assert chunks[0].chunk_index == 0
    assert chunks[0].processing_status == ProcessingStatus.PENDING
    assert all(c.chunk_hash is not None and len(c.chunk_hash) == 64 for c in chunks)
    print("=" * 80)
    print("Demonstration completed successfully with 100% contract compliance!")
    print("=" * 80)


if __name__ == "__main__":
    run_chunking_demonstration()
