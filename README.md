# 🏢 Enterprise Knowledge Intelligence Platform
> **Hackfusion 2.0 National Hackathon — Enterprise Knowledge Assistant**  
> *A production-grade, hybrid local + cloud RAG system ensuring zero-hallucination policy intelligence with exact section citations.*

---

## 🌟 Overview
Employees struggle to find the right clause across policies, SOPs, and manuals, frequently reading superseded versions while generic AI tools hallucinate answers.

This platform solves this by:
1. **Strict Grounding:** Answering strictly from ingested documents, citing exact document name, version, section, and page number.
2. **Explicit Abstention:** Classifying responses as `answered`, `partially_answered`, or `not_covered`.
3. **Version Intelligence:** Handling conflicting document versions by explicitly preferring the current policy while retaining superseded history for auditability.
4. **Hybrid Intelligence:** Running local quantized models (Qwen 2.5 3B on an RTX 4050 GPU) with automatic failover to cloud LLMs (Gemini 2.0 Flash) for high-complexity queries.
5. **FastMCP Integration:** Enterprise tool calling via the Model Context Protocol.

---

## 👥 Architecture & Team Allocation

| Member | Primary Ownership | Status |
|---|---|---|
| **Person 1 (Lead)** | AI Brain, FastAPI Backend, Ollama, LangGraph Orchestrator & Integration | **Ready & Tested** |
| **Person 2** | Document Ingestion, Docling/PyMuPDF, Structure-aware Chunking | Mock & Interface Ready |
| **Person 3** | PostgreSQL + pgvector, Hybrid Search (BGE + BM25), GraphRAG | Mock & Interface Ready |
| **Person 4** | FastMCP Tool Server (6 Enterprise Tools) | Mock & Interface Ready |
| **Person 5** | React + Vite + Tailwind UI, Citation Viewer, Batch Mode | API Ready |

---

## ⚡ Quick Start for Development

### 1. Install Dependencies
```bash
cd backend
py -m pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and insert your free GEMINI_API_KEY from Google AI Studio
```

### 3. Launch with Mock Teammate Services (1-Click)
```powershell
.\run_dev_with_mocks.ps1
```
Or with Windows Command Prompt:
```cmd
run_dev_with_mocks.bat
```

### 4. Run Automated Verification Tests
```bash
py test_system.py
```

### 5. Interactive Swagger API Docs
Visit: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📖 Complete Documentation
For the complete step-by-step developer manual, see:
👉 [**PERSON1_HANDOVER_AND_EXECUTION_GUIDE.md**](./PERSON1_HANDOVER_AND_EXECUTION_GUIDE.md)
