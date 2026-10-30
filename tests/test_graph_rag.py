from datetime import date
import hashlib
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.db import Base, Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from retrieval.graph import GraphRAGRetriever, KnowledgeGraphManager
from retrieval.models import SearchResult


@pytest.fixture
def graph_db():
    """Setup test database with related policy documents and sequential chunks."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    org_id = uuid.uuid4()
    doc_main_id = uuid.uuid4()
    doc_ref_id = uuid.uuid4()
    doc_old_id = uuid.uuid4()

    with Session(engine, expire_on_commit=False) as session:
        # 1. Main Policy (Travel)
        doc_main = DocumentDB(
            id=doc_main_id,
            organization_id=org_id,
            name="Travel Policy 2024",
            canonical_id="CORP-TRV-01",
            version="2.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/travel.pdf",
            file_hash="hash_main",
        )

        # 2. Referenced Security Policy
        doc_ref = DocumentDB(
            id=doc_ref_id,
            organization_id=org_id,
            name="Information Security Policy",
            canonical_id="CORP-SEC-01",
            version="1.0",
            status=DocumentStatus.CURRENT,
            effective_date=date(2024, 1, 1),
            file_uri="s3://test/sec.pdf",
            file_hash="hash_ref",
        )

        # 3. Old Superseded Document
        doc_old = DocumentDB(
            id=doc_old_id,
            organization_id=org_id,
            name="Travel Policy 2020",
            canonical_id="CORP-TRV-01",
            version="1.0",
            status=DocumentStatus.SUPERSEDED,
            effective_date=date(2020, 1, 1),
            file_uri="s3://test/old.pdf",
            file_hash="hash_old",
        )
        doc_main.supersedes_id = doc_old_id

        session.add_all([doc_main, doc_ref, doc_old])
        session.flush()

        # Chunks for main doc (sequential)
        c0_text = "Section 1: General provisions for international travel."
        c1_text = "Section 2: Employees must adhere to laptop handling rules in CORP-SEC-01 while abroad."
        c2_text = "Section 3: Return travel expense reimbursements must be submitted within 30 days."

        chunk0 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_main_id,
            document_name="Travel Policy 2024",
            version="2.0",
            chunk_index=0,
            section_context="1.0 Overview",
            page_number=1,
            content=c0_text,
            chunk_hash=hashlib.sha256(c0_text.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
        )
        chunk1 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_main_id,
            document_name="Travel Policy 2024",
            version="2.0",
            chunk_index=1,
            section_context="2.0 Device Security",
            page_number=2,
            content=c1_text,
            chunk_hash=hashlib.sha256(c1_text.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
        )
        chunk2 = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_main_id,
            document_name="Travel Policy 2024",
            version="2.0",
            chunk_index=2,
            section_context="3.0 Expenses",
            page_number=3,
            content=c2_text,
            chunk_hash=hashlib.sha256(c2_text.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
        )

        # Chunk for referenced security policy
        c_sec_text = "Laptops transported overseas must utilize full disk encryption and VPN."
        chunk_sec = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_ref_id,
            document_name="Information Security Policy",
            version="1.0",
            chunk_index=0,
            section_context="Device Encryption",
            page_number=1,
            content=c_sec_text,
            chunk_hash=hashlib.sha256(c_sec_text.encode()).hexdigest(),
            document_status=DocumentStatus.CURRENT,
            processing_status=ProcessingStatus.COMPLETED,
        )

        # Chunk for superseded doc
        c_old_text = "Superseded 2020 clause."
        chunk_old = ChunkDB(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_old_id,
            document_name="Travel Policy 2020",
            version="1.0",
            chunk_index=0,
            section_context="Old Provisions",
            page_number=1,
            content=c_old_text,
            chunk_hash=hashlib.sha256(c_old_text.encode()).hexdigest(),
            document_status=DocumentStatus.SUPERSEDED,
            processing_status=ProcessingStatus.COMPLETED,
        )

        session.add_all([chunk0, chunk1, chunk2, chunk_sec, chunk_old])
        session.commit()

    return engine, org_id, chunk0, chunk1, chunk2, chunk_sec, chunk_old


def test_knowledge_graph_structure(graph_db):
    """Verify KnowledgeGraphManager builds correct nodes and relational edges."""
    engine, org_id, c0, c1, c2, c_sec, _ = graph_db
    kg = KnowledgeGraphManager()

    with Session(engine, expire_on_commit=False) as session:
        g = kg.get_or_build_graph(session, org_id)

        assert g.number_of_nodes() >= 8
        assert g.has_node(f"chunk:{c1.chunk_id}")
        assert g.has_node("entity:CORP-SEC-01")

        # Verify next_chunk and prev_chunk edges
        assert g.has_edge(f"chunk:{c0.chunk_id}", f"chunk:{c1.chunk_id}")
        assert g.has_edge(f"chunk:{c1.chunk_id}", f"chunk:{c2.chunk_id}")
        assert g.has_edge(f"chunk:{c1.chunk_id}", f"chunk:{c0.chunk_id}")

        # Verify cross-reference edge from c1 to doc_ref
        assert g.has_edge(f"chunk:{c1.chunk_id}", f"doc:{c_sec.document_id}")


def test_graph_rag_expansion_and_superseded_filtering(graph_db):
    """Verify GraphRAGRetriever expands adjacent chunks and never retrieves superseded nodes."""
    engine, org_id, c0, c1, c2, c_sec, c_old = graph_db
    kg = KnowledgeGraphManager()
    graph_retriever = GraphRAGRetriever(kg_manager=kg)

    with Session(engine, expire_on_commit=False) as session:
        # Provide seed result: chunk 1
        seed = [
            SearchResult(
                chunk_id=c1.chunk_id,
                document_id=c1.document_id,
                document_name=c1.document_name,
                canonical_id="CORP-TRV-01",
                version="2.0",
                section_context=c1.section_context,
                page_number=c1.page_number,
                content=c1.content,
                score=0.92,
                rank=1,
            )
        ]

        expanded = graph_retriever.expand_graph_context(
            session=session,
            organization_id=org_id,
            seed_results=seed,
            include_adjacent_chunks=True,
            current_only=True,
            top_k=10,
        )

        returned_cids = {r.chunk_id for r in expanded}
        # Must include seed c1
        assert c1.chunk_id in returned_cids
        # Must expand to adjacent chunks c0 and c2
        assert c0.chunk_id in returned_cids
        assert c2.chunk_id in returned_cids
        # Must follow cross reference to security chunk
        assert c_sec.chunk_id in returned_cids
        # Must NEVER return superseded chunk
        assert c_old.chunk_id not in returned_cids
