"""
Mock MCP Server — simulates Person 4's MCP server.
Run on port 8001 while Person 4 builds the real thing.

Usage:
    uvicorn mock_mcp_server:app --port 8001
"""
from __future__ import annotations
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock MCP Server", version="1.0.0")

MOCK_PASSAGES = [
    {
        "chunk_id": "chunk_001",
        "document_id": "policy_travel_v2",
        "document_name": "Travel Policy",
        "version": "2.0",
        "is_current": True,
        "section": "5.2",
        "page": 12,
        "content": "Employees are entitled to claim accommodation expenses up to ₹5,000 per night.",
        "access_scope": "public",
        "score": 0.90,
    },
    {
        "chunk_id": "chunk_003",
        "document_id": "policy_it_security_v1",
        "document_name": "IT Security Policy",
        "version": "1.1",
        "is_current": True,
        "section": "3.1",
        "page": 5,
        "content": "All employee passwords must be a minimum of 12 characters.",
        "access_scope": "public",
        "score": 0.85,
    },
]


# ── Request schemas ───────────────────────────

class SearchRequest(BaseModel):
    query: str
    department: Optional[str] = None
    doc_type: Optional[str] = None
    version: Optional[str] = None

class DocRequest(BaseModel):
    document_id: str

class SectionRequest(BaseModel):
    document_id: str
    section: str

class PassageRequest(BaseModel):
    chunk_id: str

class CompareRequest(BaseModel):
    doc_id_v1: str
    doc_id_v2: str


# ── Endpoints ─────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "mock_mcp"}


@app.post("/tools/search_documents")
def search_documents(req: SearchRequest) -> List[dict]:
    return MOCK_PASSAGES


@app.post("/tools/get_document_details")
def get_document_details(req: DocRequest) -> dict:
    return {
        "document_id": req.document_id,
        "document_name": "Travel Policy",
        "version": "2.0",
        "is_current": True,
        "doc_type": "policy",
        "sections": ["1. Purpose", "2. Scope", "3. Air Travel", "4. Ground Travel", "5. Accommodation", "6. Meals"],
        "page_count": 18,
    }


@app.post("/tools/get_document_version")
def get_document_version(req: DocRequest) -> dict:
    return {
        "document_id": req.document_id,
        "current_version": "2.0",
        "effective_date": "2024-01-15",
        "supersedes": "1.0",
        "versions": [
            {"version": "2.0", "is_current": True, "effective_date": "2024-01-15"},
            {"version": "1.0", "is_current": False, "effective_date": "2023-01-15", "superseded_by": "2.0"},
        ],
    }


@app.post("/tools/get_policy_section")
def get_policy_section(req: SectionRequest) -> dict:
    return {
        "document_id": req.document_id,
        "section": req.section,
        "content": "This is a mock section content for section " + req.section,
        "page": 12,
        "version": "2.0",
    }


@app.post("/tools/get_source_passage")
def get_source_passage(req: PassageRequest) -> dict:
    for p in MOCK_PASSAGES:
        if p["chunk_id"] == req.chunk_id:
            return p
    return {}


@app.post("/tools/compare_document_versions")
def compare_document_versions(req: CompareRequest) -> dict:
    return {
        "doc_id_v1": req.doc_id_v1,
        "doc_id_v2": req.doc_id_v2,
        "changed_sections": [
            {
                "section": "5.2",
                "change_type": "modified",
                "v1_content": "Accommodation limit: ₹3,500 per night",
                "v2_content": "Accommodation limit: ₹5,000 per night",
            }
        ],
        "summary": "Accommodation expense limit increased from ₹3,500 to ₹5,000 per night.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
