from __future__ import annotations
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile, File

from app.ingestion.client import IngestionClient
from app.mcp.client import MCPClient
from app.schemas import DocumentListResponse, DocumentUploadResponse, DocumentInfo

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


@router.post("/documents/upload", response_model=DocumentUploadResponse, summary="Upload a document")
async def upload_document(
    file: UploadFile = File(...),
    organization_id: str = Form("public"),
    document_name: Optional[str] = Form(None),
    version_label: str = Form("1.0"),
    supersedes_id: Optional[str] = Form(None),
    effective_date: Optional[date] = Form(None),
) -> DocumentUploadResponse:
    """Upload a document for ingestion and indexing."""
    import os
    from app.config import get_settings

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    max_size = get_settings().INGESTION_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds the {get_settings().INGESTION_MAX_FILE_SIZE_MB}MB limit",
        )

    ingestion = IngestionClient()
    result = await ingestion.ingest_document(
        file_bytes=file_bytes,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        organization_id=organization_id,
        document_name=document_name,
        version_label=version_label,
        supersedes_id=supersedes_id,
        effective_date=effective_date,
    )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=503,
            detail=f"Ingestion service error: {result.get('error', 'Unknown error')}",
        )

    return DocumentUploadResponse(
        document_id=result.get("document_id", "unknown"),
        document_name=result.get("document_name", file.filename or "unknown"),
        status=result.get("status", "processing"),
        message=result.get("message", "Document submitted for processing"),
        version_id=result.get("version_id"),
        status_url=result.get("status_url"),
    )


@router.get("/documents", response_model=DocumentListResponse, summary="List all documents")
async def list_documents() -> DocumentListResponse:
    """List all ingested documents."""
    ingestion = IngestionClient()
    raw_docs = await ingestion.list_documents()

    documents = []
    for doc in raw_docs:
        try:
            documents.append(
                DocumentInfo(
                    document_id=doc.get("document_id", ""),
                    document_name=doc.get("document_name", ""),
                    version=doc.get("version", "1.0"),
                    is_current=doc.get("is_current", True),
                    doc_type=doc.get("doc_type", "unknown"),
                    page_count=doc.get("page_count", 0),
                    section_count=doc.get("section_count", 0),
                    uploaded_at=datetime.fromisoformat(
                        doc.get("uploaded_at", datetime.utcnow().isoformat())
                    ),
                )
            )
        except Exception as e:
            logger.warning("Skipping malformed document record: %s", e)

    return DocumentListResponse(documents=documents, total=len(documents))


@router.get("/documents/status/{version_id}", summary="Get document processing status")
async def get_processing_status(version_id: str):
    """Get asynchronous ingestion status for a document version."""
    ingestion = IngestionClient()
    status = await ingestion.get_processing_status(version_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Processing status not found for version '{version_id}'",
        )
    return status


@router.get("/documents/{document_id}", summary="Get document details")
async def get_document(document_id: str):
    """Get metadata for a specific document."""
    ingestion = IngestionClient()
    doc = await ingestion.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return doc


@router.get("/documents/{document_id}/versions", summary="Get document versions")
async def get_document_versions(document_id: str):
    """Get version history for a document via MCP."""
    mcp = MCPClient()
    version_info = await mcp.get_document_version(document_id)
    if not version_info:
        raise HTTPException(status_code=404, detail=f"Version info not found for '{document_id}'")
    return version_info
