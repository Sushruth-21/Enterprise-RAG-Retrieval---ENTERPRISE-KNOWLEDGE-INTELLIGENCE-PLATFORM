# Document Intelligence Pipeline: Execution Roadmap

## Pipeline Phasing & Implementation Queue

### [x] Phase 1: Models & Database Schema
- [x] SQLAlchemy 2.0 and Pydantic V2 models for `Document` and `Chunk`.
- [x] Multi-tenant permissions (`organization_id`).
- [x] Deduplication and incremental embedding contracts (`file_hash`, `chunk_hash`, `embedding_model`, `processing_status`).
- [x] Lineage and version control schema (`supersedes_id`, self-referencing relationship).
- [x] Automated test suite verifying schema integrity.

### [x] Phase 2: Core Document Parsers
- [x] Intermediate `ParsedDocument`, `StructuralElement`, and `ParsedTable` models.
- [x] Defensive `BaseParser` preventing crashes on malformed files.
- [x] PDF parser with dual-engine (PyMuPDF layout + Docling) and table extraction.
- [x] DOCX parser mapping Word styles (`Title`, `Heading 1-3`) and table grids.
- [x] Markdown and plain text parsers with page awareness.
- [x] Factory routing and automated test suite.

---

### [x] Phase 3 (Task 1): Structure-Aware Chunking (Completed)
- [x] Implemented StructureAwareChunker respecting paragraph and table boundaries.
- [x] Intelligent table grouping with preceding explanatory text.
- [x] Row-by-row table splitting preserving header schema for oversized tables.
- [x] Context preservation with prepended section_context breadcrumbs.
- [x] Content hashing (SHA-256) per chunk for incremental embeddings.
- [x] Strict mapping to ChunkModel with sequential chunk_index and processing_status='pending'.
- [x] Unit tests and runnable demonstration script (chunking/example.py).

---

### [x] Phase 4 (Task 2): Version Control Manager (Completed)
- [x] Implemented VersionControlManager for transactional document lineage.
- [x] File hash idempotency check (rejects duplicate uploads per organization).
- [x] Explicit supersedes_id lineage requirement (no filename guessing).
- [x] Atomic transactional cascade: updates predecessor status to 'superseded'.
- [x] Cascades status update to ALL related chunks in the database table to 'superseded'.
- [x] Sets new document and its chunks to 'current'.
- [x] Tenant boundary validation (rejects cross-tenant lineage links).
- [x] Unit tests in tests/test_versioning.py (5 passed).

---

### [x] Phase 5 (Task 3): Ingestion Orchestrator (Completed)
- [x] Implemented IngestionOrchestrator pipeline coordinator.
- [x] SHA-256 raw file hashing in 64KB blocks.
- [x] Idempotency check with graceful duplicate skip.
- [x] Automatic format parser dispatching via factory.
- [x] Structure-aware chunk generation with breadcrumbs and chunk hashes.
- [x] Database handoff: bulk inserts chunks into PostgreSQL table with processing_status='pending' and embedding=NULL.
- [x] Version control metadata assignment and atomic predecessor status cascading.
- [x] Comprehensive structured stage-by-stage logging.
- [x] Unit tests in tests/test_orchestrator.py (3 passed).

---

### [x] Phase 6 (Task 4): Testing & Validation (Completed)
- [x] Implemented mock document generator script in scripts/generate_mock_documents.py (PDF, DOCX, TXT, MD).
- [x] End-to-end tests for parsing module simulating PDF and DOCX inputs.
- [x] Chunker validation verifying tables aren't split, headings are preserved, and chunk hashes match.
- [x] Version manager test ensuring older documents and all related chunks are flagged as 'superseded' transactionally.
- [x] Full test suite with 24 passed tests in tests/ (4.07s execution time).
