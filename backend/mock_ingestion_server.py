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

# Clean production: No hardcoded mock documents
_documents: List[dict] = []


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
    """Accept a document upload and return a processing response."""
    content = await file.read()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    filename = document_name or file.filename or "unknown"
    new_doc = {
        "document_id": doc_id,
        "document_name": filename,
        "version": version_label,
        "is_current": True,
        "doc_type": "policy" if ".pdf" in filename.lower() else "document",
        "page_count": max(1, len(content) // 3000),
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
    # Check KnowledgeVault
    try:
        from app.storage.vault import KnowledgeVault
        vault = KnowledgeVault.get_instance()
        vault_docs = vault.list_documents()
        if vault_docs:
            return vault_docs
    except Exception:
        pass
    return _documents


@app.get("/documents/{document_id}")
def get_document(document_id: str):
    try:
        from app.storage.vault import KnowledgeVault
        vault = KnowledgeVault.get_instance()
        doc = vault.get_document(document_id)
        if doc:
            return doc
    except Exception:
        pass

    for doc in _documents:
        if doc["document_id"] == document_id:
            return doc
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
