"""
Real Document Intelligence Ingestion Server (Person 2 Microservice)
Replaces mock_ingestion_server.py on Port 8003 with real parsing, Hybrid OCR, and structure-aware chunking.

Usage:
    uvicorn real_ingestion_server:app --port 8003
"""
from __future__ import annotations
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

# Ensure project root is in sys.path to access Person 2 modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from chunking import split_document_into_chunks
from parsers import parse_document
from parsers.models import ParsedDocument

logger = logging.getLogger("document_intelligence.service")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Real Document Intelligence Ingestion Service (Person 2)",
    version="2.0.0",
    description="Enterprise-grade document ingestion with structure-aware chunking and Two-Tier Hybrid OCR.",
)

# In-memory document index for runtime tracking
_documents_store: Dict[str, Dict[str, Any]] = {}
_document_chunks_store: Dict[str, List[Dict[str, Any]]] = {}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "real_document_intelligence_ingestion",
        "engine": "person2_production",
        "supported_formats": ["pdf", "docx", "txt", "md", "png", "jpg", "jpeg", "tiff", "webp"],
    }


def _build_document_description(
    parsed_doc: ParsedDocument, chunks: list, filename: str
) -> str:
    """Generate a meaningful document description from actual parsed content
    instead of a generic placeholder. Uses the first few chunks to summarise."""
    parts: List[str] = []

    # Use the parsed document title if available
    if parsed_doc.title and parsed_doc.title.lower() != filename.lower():
        parts.append(parsed_doc.title.strip())

    # Collect unique section headings (first 5)
    seen_sections: set = set()
    for chunk in chunks:
        ctx = getattr(chunk, "section_context", "") or ""
        if ctx and ctx not in seen_sections and len(seen_sections) < 5:
            seen_sections.add(ctx)
    if seen_sections:
        parts.append("Sections: " + " | ".join(sorted(seen_sections)))

    # Use the first chunk's content as an excerpt (first 200 chars)
    if chunks:
        first_text = (getattr(chunks[0], "content", "") or "").strip()
        if first_text:
            excerpt = first_text[:200].rstrip()
            if len(first_text) > 200:
                excerpt += "…"
            parts.append(excerpt)

    if parts:
        return " — ".join(parts)

    # Absolute fallback
    return f"{filename} ({parsed_doc.total_pages} pages)"


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    organization_id: str = Form("public"),
    document_name: str = Form(""),
    version_label: str = Form("1.0"),
    supersedes_id: str = Form(""),
    effective_date: str = Form(""),
) -> dict:
    """
    Accepts real document upload, executes structural parsing (with OCR for images/scans),
    computes structure-aware chunks, and records lineage metadata.
    """
    # Determine file suffix and filename correctly
    raw_filename = file.filename or ""
    filename = document_name or raw_filename or "unknown_file"
    suffix = Path(raw_filename).suffix.lower()
    if not suffix and document_name:
        suffix = Path(document_name).suffix.lower()
    if not suffix:
        suffix = ".txt"

    content = await file.read()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    logger.info(f"Ingesting real document '{filename}' ({len(content)} bytes, ext={suffix}) | Tenant: {organization_id}")

    # Write file to temporary storage for parser processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(content)
        tmp_path = Path(tmp_file.name)

    try:
        # Step 1: Real Multi-Format Parsing (PDF, DOCX, TXT, MD, Images/Scanned PDF OCR)
        parsed_doc: ParsedDocument = parse_document(tmp_path)

        # Step 2: Real Structure-Aware Chunking
        doc_uuid = uuid.uuid4()
        try:
            org_uuid = uuid.UUID(organization_id)
        except Exception:
            org_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, organization_id or "public")

        chunks = split_document_into_chunks(
            parsed_doc=parsed_doc,
            document_id=doc_uuid,
            organization_id=org_uuid,
            document_name=filename,
            version=version_label,
            min_tokens=200,
            max_tokens=600,
        )

        section_count = len([e for e in parsed_doc.elements if "HEADING" in str(e.element_type)])
        table_count = len(parsed_doc.tables)

        # Build a meaningful description from the actual parsed content
        description = _build_document_description(parsed_doc, chunks, filename)

        doc_entry = {
            "document_id": doc_id,
            "document_name": filename,
            "title": parsed_doc.title or filename,
            "version": version_label,
            "is_current": True,
            "doc_type": "policy" if ".pdf" in filename.lower() else "document",
            "page_count": max(1, parsed_doc.total_pages),
            "section_count": max(1, section_count),
            "table_count": table_count,
            "total_chunks": len(chunks),
            "uploaded_at": datetime.utcnow().isoformat(),
            "organization_id": organization_id,
            "supersedes_id": supersedes_id or None,
            "status": "completed",
            "description": description,
        }

        # Store FULL chunk content (not just previews) so /search can find them
        _documents_store[doc_id] = doc_entry
        _document_chunks_store[doc_id] = [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": doc_id,
                "document_name": filename,
                "version": version_label,
                "is_current": True,
                "index": c.chunk_index,
                "chunk_index": c.chunk_index,
                "section_context": c.section_context,
                "section": c.section_context,
                "page_number": c.page_number,
                "page": c.page_number,
                "chunk_hash": c.chunk_hash,
                "content": c.content,
                "access_scope": "public",
                "score": 0.0,
            }
            for c in chunks
        ]

        logger.info(
            f"Successfully processed '{filename}': {len(chunks)} chunks, {table_count} tables, {parsed_doc.total_pages} pages."
        )

        return {
            "document_id": doc_id,
            "document_name": filename,
            "status": "completed",
            "version": version_label,
            "page_count": doc_entry["page_count"],
            "section_count": doc_entry["section_count"],
            "total_chunks": len(chunks),
            "table_count": table_count,
            "message": f"Successfully parsed and chunked '{filename}' into {len(chunks)} contextual chunks.",
        }

    except Exception as exc:
        logger.error(f"Failed to ingest document '{filename}': {exc}", exc_info=True)
        return {
            "document_id": doc_id,
            "document_name": filename,
            "status": "failed",
            "error": str(exc),
        }
    finally:
        # Cleanup temporary file
        if tmp_path.exists():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.get("/documents")
def list_documents() -> List[dict]:
    """Returns all ingested documents."""
    return list(_documents_store.values())


@app.get("/documents/{document_id}")
def get_document(document_id: str):
    """Returns specific document details and its chunk previews."""
    doc = _documents_store.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        **doc,
        "chunks": _document_chunks_store.get(document_id, []),
    }


@app.get("/documents/{document_id}/chunks")
def get_document_chunks(document_id: str):
    """Returns chunks for a specific document."""
    chunks = _document_chunks_store.get(document_id)
    if chunks is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return chunks


@app.post("/search")
def search_chunks(query: dict):
    """Keyword search across all ingested document chunks.
    Returns results in DocumentPassage-compatible format so the
    retrieval client fallback can use them directly."""
    q = query.get("query", "").lower()
    top_k = query.get("top_k", 10)
    doc_id_filter = query.get("doc_id")

    if not q:
        return []

    results = []
    query_words = [w for w in q.split() if len(w) >= 3]

    for did, chunks in _document_chunks_store.items():
        if doc_id_filter and did != doc_id_filter:
            continue
        for chunk in chunks:
            content = chunk.get("content", "")
            content_lower = content.lower()
            if not content_lower:
                continue

            # Score by keyword overlap
            matches = sum(1 for w in query_words if w in content_lower)
            if matches == 0:
                continue

            score = round(min((matches / max(len(query_words), 1)) * 1.2, 1.0), 4)

            results.append({
                "chunk_id": chunk.get("chunk_id", ""),
                "document_id": did,
                "document_name": chunk.get("document_name", ""),
                "version": chunk.get("version", "1.0"),
                "is_current": chunk.get("is_current", True),
                "section": chunk.get("section_context", chunk.get("section", "")),
                "page": chunk.get("page_number", chunk.get("page", 1)),
                "content": content,
                "access_scope": chunk.get("access_scope", "public"),
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


@app.get("/status/{version_id}")
def get_status(version_id: str):
    return {
        "version_id": version_id,
        "status": "completed",
        "progress": 1.0,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
