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

---

### [x] Phase 7: Person 3 - Retrieval Schema & Vector Storage (Completed)
- [x] Extended `Chunk` database model with pgvector `Vector(384)` dense embedding column.
- [x] Created `QACacheEntry` database and Pydantic models with multi-tenant isolation and source dependency tracking.
- [x] Preserved 100% backward compatibility with Person 2 models and SQLite test harness.

---

### [x] Phase 8: BGE Embeddings & Concurrent Worker (Completed)
- [x] Implemented `BGEEmbeddingService` using `BAAI/bge-small-en-v1.5` with ONNX Runtime inference and L2 normalization.
- [x] Asymmetric query instruction prefixing (`Represent this sentence for searching relevant passages: `).
- [x] Implemented `EmbeddingWorker` with atomic `FOR UPDATE SKIP LOCKED` batching and tenant boundary enforcement.
- [x] Incremental embedding deduplication reusing precomputed embeddings for identical chunk hashes.
- [x] Unit tests in `tests/test_embedding_and_worker.py` (4 passed).

---

### [x] Phase 9: Vector, Full-Text & Hybrid RRF Retrieval (Completed)
- [x] Implemented `VectorRetriever` with PostgreSQL pgvector cosine distance `<=>` and non-Postgres in-memory cosine fallback.
- [x] Implemented `FullTextRetriever` with PostgreSQL `to_tsvector`/`ts_rank_cd` and Okapi BM25 fallback.
- [x] Implemented `HybridRetriever` using Reciprocal Rank Fusion ($k=60$) fusing dense and sparse candidate rankings.
- [x] Enforced strict tenant isolation (`organization_id`) and superseded policy filtering (`document_status == 'current'`).
- [x] Unit tests in `tests/test_retrieval.py` (4 passed).

---

### [x] Phase 10: BGE Reranker & Context Construction (Completed)
- [x] Implemented `BGEReranker` cross-encoder using `BAAI/bge-reranker-base` with sigmoid probability calibration.
- [x] Implemented `ContextBuilder` assembling formatted prompt context with source citation metadata headers.
- [x] Enforced context window token and character budgets without splitting citation headers.
- [x] Unit tests in `tests/test_reranker_and_context.py` (3 passed).

---

### [x] Phase 11: NetworkX-Based GraphRAG (Completed)
- [x] Implemented `KnowledgeGraphManager` building hierarchical DiGraphs (documents, sections, chunks, entities, lineage).
- [x] Implemented `GraphRAGRetriever` expanding seed chunks via adjacent chunk healing (`prev_chunk`, `next_chunk`), section siblings, cross-policy references, and Personalized PageRank (PPR).
- [x] Unit tests in `tests/test_graph_rag.py` (2 passed).

---

### [x] Phase 12: Semantic QA Caching with Dependency Validation (Completed)
- [x] Implemented `SemanticQACache` (CAG approach) with dense semantic query similarity matching.
- [x] Enforced strict dependency validation: invalidates cached answers if any underlying document is superseded or altered.
- [x] Multi-tenant isolation and proactive document invalidation API.
- [x] Unit tests in `tests/test_qa_cache.py` (3 passed).

---

### [x] Phase 13: FastAPI Integration & Retrieval Evaluation (Completed)
- [x] Implemented FastAPI router (`/retrieval/search`, `/retrieval/context`, `/retrieval/qa`, `/retrieval/graph-search`, `/retrieval/cache/invalidate`, `/retrieval/evaluate`).
- [x] Implemented `RetrievalEvaluator` computing Precision@K, Recall@K, Mean Reciprocal Rank (MRR), and NDCG@K.
- [x] Unit tests in `tests/test_api_and_evaluation.py` (7 passed).
- [x] Full test suite now passing 48/48 tests across the repository.

---

### [x] Phase 14: Real PostgreSQL + pgvector Integration & Alembic Migrations (Completed)
- [x] Provisioned live PostgreSQL 16.15 cluster with native `pgvector 0.8.7` extension.
- [x] Initialized Alembic database migration environment with dynamic URL resolution (`alembic.ini`, `alembic/env.py`).
- [x] Generated and applied initial migration (`50f4f80b98af_initial_schema_with_pgvector_and_qa_.py`) creating `vector` extension, `documents`, `chunks` (with `Vector(384)`), `qa_cache_entries`, and indexes.
- [x] Created separate PostgreSQL integration test suite in `tests/test_postgres_integration.py` (10 passed).
- [x] Verified native pgvector `<=>` cosine distance search, `to_tsvector` FTS, hybrid RRF, tenant isolation, version filtering, `FOR UPDATE SKIP LOCKED` worker concurrency, and semantic cache dependency invalidation against live PostgreSQL.
- [x] Complete test suite passing: 58/58 tests (48 SQLite unit tests + 10 real PostgreSQL integration tests).
