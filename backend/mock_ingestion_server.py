"""
Mock Ingestion Server — simulates Person 2's document ingestion service.
Run on port 8003 while Person 2 builds the real thing.

Usage:
    uvicorn mock_ingestion_server:app --port 8003
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import List

from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel

app = FastAPI(title="Mock Ingestion Server", version="1.0.0")

# In-memory document store (for mock)
_documents = [
    {
        "document_id": "policy_travel_v2",
        "document_name": "Travel Policy v2.0",
        "version": "2.0",
        "is_current": True,
        "doc_type": "policy",
        "page_count": 18,
        "section_count": 12,
        "uploaded_at": "2024-01-15T09:00:00",
    },
    {
        "document_id": "policy_travel_v1",
        "document_name": "Travel Policy v1.0",
        "version": "1.0",
        "is_current": False,
        "doc_type": "policy",
        "page_count": 14,
        "section_count": 9,
        "uploaded_at": "2023-01-15T09:00:00",
    },
    {
        "document_id": "policy_it_security_v1",
        "document_name": "IT Security Policy v1.1",
        "version": "1.1",
        "is_current": True,
        "doc_type": "policy",
        "page_count": 22,
        "section_count": 15,
        "uploaded_at": "2024-03-01T10:00:00",
    },
    {
        "document_id": "policy_hr_handbook_v3",
        "document_name": "HR Employee Handbook v3.0",
        "version": "3.0",
        "is_current": True,
        "doc_type": "handbook",
        "page_count": 45,
        "section_count": 28,
        "uploaded_at": "2024-06-01T08:00:00",
    },
    {
        "document_id": "policy_leave_v2",
        "document_name": "Leave Management Policy v2.0",
        "version": "2.0",
        "is_current": True,
        "doc_type": "policy",
        "page_count": 12,
        "section_count": 8,
        "uploaded_at": "2024-04-01T09:00:00",
    },
]


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock_ingestion"}


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    organization_id: str = Form("public"),
    document_name: str = Form(""),
    version_label: str = Form("1.0"),
    supersedes_id: str = Form(""),
    effective_date: str = Form(""),
) -> dict:
    """Accept a document upload and return a mock processing response."""
    content = await file.read()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    filename = document_name or file.filename or "unknown"
    new_doc = {
        "document_id": doc_id,
        "document_name": filename,
        "version": version_label,
        "is_current": True,
        "doc_type": "policy" if ".pdf" in filename.lower() else "document",
        "page_count": max(1, len(content) // 3000),  # rough estimate
        "section_count": max(1, len(content) // 10000),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    _documents.append(new_doc)
    return {
        "document_id": doc_id,
        "document_name": filename,
        "status": "processing",
        "message": f"Document '{filename}' received ({len(content)} bytes). Processing started.",
    }


@app.get("/documents")
def list_documents() -> List[dict]:
    return _documents


@app.get("/documents/{document_id}")
def get_document(document_id: str):
    for doc in _documents:
        if doc["document_id"] == document_id:
            return doc
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
