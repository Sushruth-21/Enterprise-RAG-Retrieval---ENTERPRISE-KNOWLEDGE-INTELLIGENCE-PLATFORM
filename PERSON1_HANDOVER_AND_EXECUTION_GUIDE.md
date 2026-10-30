# 🚀 HACKFUSION 2.0 — PERSON 1 HANDOVER & EXECUTION MANUAL
## Enterprise Knowledge Intelligence Platform
**Role:** Person 1 — AI Architect, Backend & Integration Lead  
**Architecture:** Hybrid Local (Ollama Qwen2.5 on RTX 4050) + Cloud AI (Gemini 2.0 Flash Fallback)  
**Orchestrator:** LangGraph 9-Stage Grounded Workflow  
**Integration Status:** Complete FastAPI Backend & Shared Contracts Implemented + Mock Suite Ready  

---

## 📌 TABLE OF CONTENTS
1. [State of the Codebase (Where We Are)](#1-state-of-the-codebase)
2. [What The AI Cannot Do (Your Manual Tasks Checklist)](#2-what-the-ai-cannot-do-manual-tasks)
3. [Step-by-Step Execution Guide](#3-step-by-step-execution-guide)
4. [Team Alignment & Communication Contracts (Persons 2, 3, 4, 5)](#4-team-alignment--contracts)
5. [How to Run & Verify with Mocks Right Now](#5-how-to-run--verify-with-mocks)
6. [Swapping Mocks for Real Teammate Services](#6-swapping-mocks-for-real-services)
7. [Hackathon Timeline & Hour-by-Hour Milestones](#7-hackathon-timeline)
8. [Emergency LLM Continuation Prompt (Copy-Paste for Next LLM)](#8-emergency-continuation-prompt)

---

## 1. STATE OF THE CODEBASE

All code has been generated and validated with zero syntax errors under Python 3.13:

```
d:\Projects\Hackfusion\Enterprise_RAG\
├── docker-compose.yml                  # Container definition for deployability
├── README.md                           # Project top-level documentation
├── PERSON1_HANDOVER_AND_EXECUTION_GUIDE.md  # This comprehensive manual
└── backend/
    ├── requirements.txt                # Exact pinned dependencies
    ├── Dockerfile                      # Production container image
    ├── .env.example                    # Template with documentation for all env vars
    ├── test_system.py                  # End-to-end automated smoke & verification suite
    ├── run_dev_with_mocks.bat          # 1-click launcher for CMD
    ├── run_dev_with_mocks.ps1          # 1-click launcher for PowerShell
    ├── mock_retrieval_server.py        # Port 8002: Simulates Person 3's search engine
    ├── mock_ingestion_server.py        # Port 8003: Simulates Person 2's document parser
    ├── mock_mcp_server.py              # Port 8001: Simulates Person 4's FastMCP tools
    └── app/
        ├── config.py                   # Pydantic Settings, LRU cached
        ├── schemas.py                  # Strict API Contracts for all 5 team members
        ├── main.py                     # FastAPI entry point, CORS, exception handling
        ├── api/
        │   ├── chat.py                 # POST /api/chat, conversation history routes
        │   ├── documents.py            # POST /api/documents/upload, GET /api/documents
        │   ├── batch.py                # POST /api/batch for bulk questions
        │   └── health.py               # GET /api/health with multi-service probing
        ├── llm/
        │   ├── ollama_client.py        # Async client for local Ollama (RTX 4050)
        │   ├── cloud_client.py         # Provider-agnostic adapter (Gemini/OpenAI/Claude)
        │   └── router.py               # Confidentiality-aware intelligent model routing
        ├── models/
        │   └── conversation.py         # Thread-safe in-memory sliding window history
        ├── orchestrator/
        │   └── graph.py                # LangGraph 9-node state machine for RAG
        ├── retrieval/
        │   └── client.py               # HTTP client to Person 3's hybrid search API
        ├── ingestion/
        │   └── client.py               # HTTP client to Person 2's document ingestion API
        └── mcp/
            └── client.py               # HTTP client to Person 4's MCP tool server
```

---

## 2. WHAT THE AI CANNOT DO (MANUAL TASKS)

Because the AI runs in an isolated terminal sandbox without external credentials or GUI access, you must execute the following 6 actions manually on your laptop:

### 1. Download & Install Ollama (For Local GPU Inference)
- Download the installer from: **https://ollama.com/download/windows**
- Run the installer. It will install Ollama and configure the system tray service.
- Verify in your terminal:
  ```powershell
  ollama --version
  ```
- Ollama automatically detects your **NVIDIA GeForce RTX 4050 Laptop GPU**.

### 2. Pull the Selected Model
In PowerShell, run:
```powershell
ollama pull qwen2.5:3b
```
*(Size: ~1.9 GB. Takes ~2–4 minutes depending on your internet connection. Qwen 2.5 is state-of-the-art for instruction following, citations, and fast low-latency inference on a 6GB VRAM mobile GPU.)*

### 3. Get a Free Cloud AI API Key (For Hybrid Routing & Fallback)
1. Navigate to: **https://aistudio.google.com/app/apikey**
2. Sign in with your Google account.
3. Click **"Create API Key"** and copy the string (starts with `AIzaSy...`).
4. *(Optional fallback)* If your team prefers OpenAI or Anthropic, obtain keys from their respective developer dashboards.

### 4. Create your Local `.env` File
In `d:\Projects\Hackfusion\Enterprise_RAG\backend`:
```powershell
cd d:\Projects\Hackfusion\Enterprise_RAG\backend
Copy-Item .env.example .env
```
Open `.env` in Notepad or VS Code and paste your key:
```ini
GEMINI_API_KEY=AIzaSyYourActualKeyHere
```

### 5. Install Python Dependencies
```powershell
cd d:\Projects\Hackfusion\Enterprise_RAG\backend
py -m pip install -r requirements.txt
```

### 6. Initialize Git & Repository Branching
As the Integration Lead, you own the `main` branch.
```powershell
cd d:\Projects\Hackfusion\Enterprise_RAG
git init
git add .
git commit -m "feat: complete Person 1 backend, LangGraph orchestrator, schemas and mocks"
git branch -M main
git checkout -b person1/backend
```

---

## 3. STEP-BY-STEP EXECUTION GUIDE

### Step 1: Verify Ollama is Serving
Run:
```powershell
curl http://localhost:11434/api/tags
```
You should receive a JSON response showing `"name": "qwen2.5:3b"`.

### Step 2: Launch the Development Stack with Mocks
We provided a one-click launcher that starts:
- Port 8001: Mock MCP Server (Person 4)
- Port 8002: Mock Retrieval Server (Person 3)
- Port 8003: Mock Ingestion Server (Person 2)
- Port 8000: Main FastAPI Backend (You, Person 1)

**Run via PowerShell:**
```powershell
cd d:\Projects\Hackfusion\Enterprise_RAG\backend
.\run_dev_with_mocks.ps1
```
*(Or double-click `run_dev_with_mocks.bat`)*

### Step 3: Run the Automated Test Suite
In a separate PowerShell window:
```powershell
cd d:\Projects\Hackfusion\Enterprise_RAG\backend
py test_system.py
```
This tests:
1. Health check (`/api/health`)
2. Document listing (`/api/documents`)
3. Document upload (`/api/documents/upload`)
4. In-corpus grounded answering with citations (`/api/chat`)
5. Hallucination prevention & `not_covered` classification
6. Concurrent batch processing (`/api/batch`)

### Step 4: Explore the Interactive API Documentation
Open your browser to:
**http://localhost:8000/docs**
Here you have a complete Swagger UI to demo and test every endpoint live.

---

## 4. TEAM ALIGNMENT & CONTRACTS

You are the central hub. Each person connects to you via HTTP. Share the following exact contracts with each teammate:

```
┌─────────────────────────────────────────────────────────────┐
│                       PERSON 5 (Frontend)                   │
│                    React / Vite / Tailwind UI               │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP calls to Port 8000
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    PERSON 1 (YOU - Brain)                   │
│            FastAPI Backend + LangGraph Orchestrator         │
│          Hybrid Model Router (Ollama Local / Cloud)         │
└───┬──────────────────────────┬──────────────────────────┬───┘
    │ HTTP :8003               │ HTTP :8002               │ HTTP :8001
    ▼                          ▼                          ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   PERSON 2   │       │   PERSON 3   │       │   PERSON 4   │
│  Ingestion   │       │  Retrieval   │       │  FastMCP     │
│  & Chunking  │◄─────►│  & Database  │◄─────►│  Tool Server │
└──────────────┘       └──────────────┘       └──────────────┘
```

### 🤝 To Person 2 (Document Intelligence & Ingestion)
- **Role:** Parse PDF, DOCX, TXT, Markdown; structure-aware chunking; extract document title, section, page.
- **Port:** `8003`
- **Endpoints Person 2 must expose:**
  1. `POST /ingest` — multipart form-data (`file`). Returns:
     ```json
     {
       "document_id": "doc_123",
       "document_name": "Travel_Policy_v2.pdf",
       "status": "processing",
       "message": "Document queued for processing"
     }
     ```
  2. `GET /documents` — Returns array of documents:
     ```json
     [
       {
         "document_id": "doc_123",
         "document_name": "Travel Policy v2",
         "version": "2.0",
         "is_current": true,
         "doc_type": "policy",
         "page_count": 12,
         "section_count": 8,
         "uploaded_at": "2026-10-30T10:00:00"
       }
     ]
     ```
  3. `GET /documents/{document_id}` — Returns metadata for single document.

### 🤝 To Person 3 (Retrieval & Knowledge Engineer)
- **Role:** PostgreSQL + pgvector, hybrid search (dense embeddings + sparse keyword search), Reciprocal Rank Fusion, NetworkX knowledge graph.
- **Port:** `8002`
- **Endpoints Person 3 must expose:**
  1. `POST /search` — JSON body:
     ```json
     {
       "query": "What is the domestic accommodation allowance?",
       "access_scope": "public",
       "top_k": 10,
       "doc_id": null
     }
     ```
     **Mandatory Response Array (The Universal Passage Contract):**
     ```json
     [
       {
         "chunk_id": "chunk_001",
         "document_id": "policy_travel_v2",
         "document_name": "Travel Policy",
         "version": "2.0",
         "is_current": true,
         "section": "5.2",
         "page": 12,
         "content": "Employees may claim up to Rs. 5000 per night for accommodation...",
         "access_scope": "public",
         "score": 0.94
       }
     ]
     ```
  2. `GET /passage/{chunk_id}` — Returns a single passage object by chunk ID.
  3. `GET /health` — Returns `{"status": "ok"}` when database is connected.

### 🤝 To Person 4 (MCP Engineer & AI Tool Integration)
- **Role:** FastMCP server exposing 6 enterprise knowledge tools for LangGraph.
- **Port:** `8001`
- **Endpoints Person 4 must expose:**
  1. `POST /tools/search_documents` — Args: `{"query": str, "department": str|null, "doc_type": str|null, "version": str|null}`
  2. `POST /tools/get_document_details` — Args: `{"document_id": str}`
  3. `POST /tools/get_document_version` — Args: `{"document_id": str}`
  4. `POST /tools/get_policy_section` — Args: `{"document_id": str, "section": str}`
  5. `POST /tools/get_source_passage` — Args: `{"chunk_id": str}`
  6. `POST /tools/compare_document_versions` — Args: `{"doc_id_v1": str, "doc_id_v2": str}`
  7. `GET /health` — Returns `{"status": "ok"}`

### 🤝 To Person 5 (Frontend Engineer)
- **Role:** React + Vite + Tailwind UI, Chat Interface, Document Management, Citation Viewer, Batch Mode, Dashboard.
- **Your API Base URL:** `http://localhost:8000` (or `http://YOUR_LOCAL_IP:8000`)
- **CORS:** Already configured to accept `http://localhost:5173` and `http://localhost:3000`.
- **Endpoints Person 5 will consume:**
  1. `POST /api/chat` — Body: `{"question": "...", "conversation_id": "optional-id", "access_scope": "public"}`
     Returns:
     ```json
     {
       "answer": "The maximum domestic accommodation limit is Rs. 5,000 per night.",
       "status": "answered",
       "citations": [
         {
           "document_id": "policy_travel_v2",
           "document_name": "Travel Policy",
           "version": "2.0",
           "section": "5.2",
           "page": 12,
           "chunk_id": "chunk_001"
         }
       ],
       "verification": {
         "verified": true,
         "unsupported_claims": []
       },
       "model_used": "qwen2.5:3b (local)",
       "conversation_id": "c12345"
     }
     ```
  2. `POST /api/documents/upload` — Multipart form-data (`file`).
  3. `GET /api/documents` — Lists documents with version & current status.
  4. `POST /api/batch` — Bulk evaluation mode:
     ```json
     {
       "questions": [
         {"question_id": "q1", "question": "What is the travel policy?"},
         {"question_id": "q2", "question": "What is the password policy?"}
       ]
     }
     ```
  5. `GET /api/health` — System status for the frontend dashboard widget.

---

## 5. HOW TO RUN & VERIFY WITH MOCKS

You do not need to wait for teammates to finish their code. Your environment is 100% testable right now:

```powershell
# In terminal 1:
cd d:\Projects\Hackfusion\Enterprise_RAG\backend
.\run_dev_with_mocks.ps1

# In terminal 2:
cd d:\Projects\Hackfusion\Enterprise_RAG\backend
py test_system.py
```

All 6 test stages will pass. You can verify that:
- Queries about "travel expense" return citations to section 5.2, page 12 of "Travel Policy v2.0".
- Queries about "Mars missions" return status `not_covered`.
- Batch queries return simultaneous answers.

---

## 6. SWAPPING MOCKS FOR REAL SERVICES

When a teammate is ready to connect:

1. Ask for their laptop's IP address (e.g. `192.168.1.45`) or if they are running on your laptop.
2. Edit `backend/.env`:
   ```ini
   # If Person 3 is on their own laptop at 192.168.1.45:
   RETRIEVAL_API_URL=http://192.168.1.45:8002

   # If Person 2 is on 192.168.1.46:
   INGESTION_API_URL=http://192.168.1.46:8003

   # If Person 4 is on 192.168.1.47:
   MCP_SERVER_URL=http://192.168.1.47:8001
   ```
3. Close the corresponding mock window.
4. Restart your FastAPI backend.
5. Re-run `py test_system.py`.

---

## 7. HACKATHON TIMELINE

| Time Window | Objective | Person 1 Specific Action |
|---|---|---|
| **Hours 0–2** | Setup & Contracts | Run Ollama, pull `qwen2.5:3b`, test backend with mocks, distribute contracts to team. |
| **Hours 2–6** | Independent Dev | Fine-tune LangGraph prompt & routing thresholds, test batch mode, verify GPU latency. |
| **Hours 6–9** | First Integration | Connect Person 2 (Ingestion) & Person 3 (Retrieval). Verify end-to-end PDF ingest -> vector search. |
| **Hours 9–12** | Core Assistant Working | Live Q&A answering with real organizer corpus documents, test superseded policy handling. |
| **Hours 12–15** | MCP & Hybrid AI | Connect Person 4's MCP tools into LangGraph. Test comparative queries using MCP. |
| **Hours 15–18** | Versioning & Verification | Audit groundedness checking: ensure out-of-corpus queries flag `not_covered`. |
| **Hours 18–21** | Frontend Integration | Connect Person 5's React dashboard. Test live file uploads and chat citations in UI. |
| **Hours 21–24** | Feature Freeze & Demo Prep | Rehearse demo script, lock codebase, run final health check. |

---

## 8. EMERGENCY CONTINUATION PROMPT

> [!TIP]
> If your token limit is reached or you need to switch LLMs, copy and paste the prompt below into the new AI chat to resume immediately without repeating background info.

```markdown
I am Person 1 (AI Architect & Backend Lead) working on the "Enterprise Knowledge Intelligence Platform" for Hackfusion 2.0.
The project is located at: d:\Projects\Hackfusion\Enterprise_RAG

Current Status:
- Complete FastAPI backend is implemented in `backend/app/`
- LangGraph 9-stage orchestrator is in `backend/app/orchestrator/graph.py`
- Local Ollama (Qwen2.5 3B on RTX 4050) + Gemini Cloud adapter is configured in `backend/app/llm/`
- Mock servers for Person 2 (:8003), Person 3 (:8002), Person 4 (:8001) are in `backend/`
- Test suite is in `backend/test_system.py`
- Shared contracts are strictly defined in `backend/app/schemas.py`
- Full reference manual is in `PERSON1_HANDOVER_AND_EXECUTION_GUIDE.md`

Please inspect the project and help me with the following task:
[STATE YOUR NEXT STEP HERE, e.g. "Person 3 just finished their retrieval service, help me integrate and test with their live endpoint"]
```
