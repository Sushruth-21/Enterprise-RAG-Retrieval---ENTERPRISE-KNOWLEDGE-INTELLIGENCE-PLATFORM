# 🚀 Enterprise Knowledge Intelligence Platform (EKP)
### Hackfusion 2.0 — Grounded Enterprise RAG & Intelligence

---

## 🌟 Overview
Employees struggle to find the right clause across policies, SOPs, and manuals, frequently reading superseded versions while generic AI tools hallucinate answers.

This platform solves this by:
1. **Strict Grounding:** Answering strictly from ingested documents, citing exact document name, version, section, and page number.
2. **Explicit Abstention:** Classifying responses as `answered`, `partially_answered`, or `not_covered`.
3. **Version Intelligence:** Handling conflicting document versions by explicitly preferring the current policy while retaining superseded history for auditability (`canonical_id` + `supersedes_id` lineage).
4. **Hybrid Intelligence:** Running local quantized models (Qwen 2.5 3B via Ollama on CPU/GPU) with automatic failover to cloud LLMs (Gemini 2.0 Flash) for complex multi-turn queries.
5. **Two-Tier Hybrid OCR:** Offline RapidOCR (~35ms) + Gemini 2.0 Flash Vision fallback for distorted/noisy scans and tables.
6. **FastMCP Integration:** Enterprise tool calling via the Model Context Protocol.

---

## 👥 Architecture & Team Allocation

| Member | Primary Ownership | Status |
|---|---|---|
| **Person 1 (Lead)** | AI Brain, FastAPI Backend, Ollama, LangGraph Orchestrator & Integration | **Merged & Active** |
| **Person 2** | Document Ingestion, Hybrid OCR, Structure-Aware Chunking, Versioning Engine | **Integrated & Verified (29 Tests Passing)** |
| **Person 3** | PostgreSQL + pgvector, Hybrid Search (BGE + BM25), GraphRAG | Ready for Handover |
| **Person 4** | FastMCP Tool Server (Enterprise Tools) | Mock & Interface Ready |
| **Person 5** | React + Vite + Tailwind UI, Citation Viewer, Batch Mode | API Ready |

---

## 📂 Integrated Repository Structure

```
.
├── backend/                               # Person 1: FastAPI Central Backend & Orchestrator (Port 8000)
│   ├── app/
│   │   ├── api/                           # Chat, documents, batch, and health endpoints
│   │   ├── llm/                           # Ollama (Qwen 2.5) + Gemini Cloud clients & Router
│   │   ├── orchestrator/                  # LangGraph 9-stage state machine
│   │   ├── ingestion/                     # Client calling Person 2's ingestion service (Port 8003)
│   │   └── schemas.py                     # Shared API contracts
│   ├── mock_retrieval_server.py           # Port 8002: Simulates Person 3's search
│   ├── mock_mcp_server.py                 # Port 8001: Simulates Person 4's MCP
│   └── test_system.py                     # Full end-to-end integration test suite
├── parsers/                               # Person 2: Multi-format parsing engine
│   ├── pdf_parser.py                      # PyMuPDF + Docling + Scanned OCR fallback
│   ├── docx_parser.py                     # Style-hierarchy & table grid extractor
│   ├── markdown_parser.py                 # Heading and table parser
│   ├── text_parser.py                     # Heuristic section layout parser
│   ├── image_parser.py                    # Standalone image parser (.png, .jpg, .tiff, etc.)
│   └── factory.py                         # Unified parse_document() factory
├── ocr/                                   # Person 2: Two-Tier Hybrid OCR
│   ├── offline_engine.py                  # Fast offline RapidOCR (ONNX Runtime, ~35ms)
│   ├── online_engine.py                   # High-fidelity Gemini 2.0 Flash Vision fail-safe
│   └── hybrid_engine.py                   # Automated confidence-threshold routing (<0.65)
├── chunking/                              # Person 2: Structure-aware chunker
│   ├── chunker.py                         # Table-preserving context-prepending chunker
│   └── tokenizer.py                       # Token counting with heuristic fallback
├── versioning/                            # Person 2: Document lineage & transactional manager
│   └── manager.py                         # Canonical ID, supersedes_id, SHA-256 deduplication
├── models/                                # Person 2: Database and schema definitions
│   ├── db.py                              # SQLAlchemy Document & Chunk models
│   └── schemas.py                         # Pydantic V2 models
├── orchestrator/                          # Person 2: End-to-end ingestion orchestrator
│   └── pipeline.py                        # IngestionOrchestrator pipeline coordinator
├── tests/                                 # Person 2 unit & validation tests (29 passing)
├── docker-compose.yml                     # Multi-service container orchestration
└── PERSON1_HANDOVER_AND_EXECUTION_GUIDE.md # Person 1 architecture & handover manual
```

---

## ⚡ Quick Start & Verification

### 1. Run Person 2 Test Suite
```bash
python -m pytest tests/ -v
```

### 2. Launch Person 1 Backend with Mocks
```powershell
cd backend
python test_system.py
```
