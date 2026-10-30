from __future__ import annotations
import logging
import os
from datetime import date, datetime
from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse

from app.auth.security import UserPayload, get_optional_current_user
from app.config import get_settings
from app.ingestion.client import IngestionClient
from app.schemas import DocumentInfo, DocumentListResponse, DocumentUploadResponse

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


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload a document",
)
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: Optional[str] = Form(None),
    organization_id: Optional[str] = Form(None),
    document_name: Optional[str] = Form(None),
    version_label: str = Form("1.0"),
    supersedes_id: Optional[str] = Form(None),
    effective_date: Optional[date] = Form(None),
    user: Optional[UserPayload] = Depends(get_optional_current_user),
) -> DocumentUploadResponse:
    """
    Upload a document for parsing, chunking, and embedding.
    Enforces RBAC: only users with admin/compliance_officer roles can upload if authenticated.
    Dual-compatible with Person 4 frontend and Person 1 backend tests.
    """
    # Enforce RBAC permission if authenticated user token is provided
    if user and not user.is_admin():
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Role '{user.role}' lacks administrative clearance to upload or modify documents.",
        )

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

    effective_org = workspace_id or organization_id or (str(user.organization_id) if user else "public")
    clean_name = document_name or file.filename or "unknown_file"

    ingestion = IngestionClient()
    result = await ingestion.ingest_document(
        file_bytes=file_bytes,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        organization_id=effective_org,
        document_name=clean_name,
        version_label=version_label,
        supersedes_id=supersedes_id,
        effective_date=effective_date,
    )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=503,
            detail=f"Ingestion service error: {result.get('error', 'Unknown error')}",
        )

    doc_id = str(result.get("document_id") or "unknown")
    doc_name = str(result.get("document_name") or clean_name)
    status_str = str(result.get("status") or "indexed")
    page_count = int(result.get("total_pages") or result.get("page_count") or 1)
    chunk_count = int(result.get("total_chunks") or result.get("chunk_count") or 0)

    return DocumentUploadResponse(
        id=doc_id,
        workspaceId=effective_org,
        name=doc_name,
        format=ext.lstrip(".") or "txt",
        sizeBytes=len(file_bytes),
        pageCount=page_count,
        chunkCount=chunk_count,
        document_id=doc_id,
        document_name=doc_name,
        status=status_str,
        message=result.get("message", "Document submitted for processing"),
        version_id=result.get("version_id"),
        status_url=result.get("status_url"),
    )


@router.get(
    "/documents",
    summary="List all documents",
)
async def list_documents(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    as_list: Optional[bool] = Query(False),
) -> Any:
    """
    List all ingested documents.
    If query param 'workspace_id' or 'format' is passed, or as_list=true,
    returns List[DocumentItem] directly matching Person 4 frontend specifications.
    Otherwise returns DocumentListResponse { documents: [...], total: int } for Person 1 tests.
    """
    ingestion = IngestionClient()
    raw_docs = await ingestion.list_documents()

    documents: List[DocumentInfo] = []
    for doc in raw_docs:
        try:
            d_name = doc.get("document_name", "")
            d_format = doc.get("format") or doc.get("doc_type") or os.path.splitext(d_name)[1].lstrip(".") or "txt"
            d_ws = doc.get("workspace_id") or doc.get("organization_id") or "default"

            # Filter if requested
            if workspace_id and d_ws != workspace_id and workspace_id != "default":
                continue
            if format and d_format.lower() != format.lower():
                continue

            documents.append(
                DocumentInfo(
                    id=doc.get("document_id", ""),
                    workspaceId=d_ws,
                    name=d_name,
                    format=d_format,
                    sizeBytes=int(doc.get("size_bytes", doc.get("sizeBytes", 1024))),
                    pageCount=int(doc.get("page_count", doc.get("pageCount", 1))),
                    chunkCount=int(doc.get("chunk_count", doc.get("chunkCount", doc.get("section_count", 0)))),
                    document_id=doc.get("document_id", ""),
                    document_name=d_name,
                    version=doc.get("version", "1.0"),
                    is_current=doc.get("is_current", True),
                    doc_type=d_format,
                    page_count=int(doc.get("page_count", 1)),
                    section_count=int(doc.get("section_count", 0)),
                    uploaded_at=datetime.fromisoformat(
                        doc.get("uploaded_at", datetime.utcnow().isoformat())
                    ),
                )
            )
        except Exception as e:
            logger.warning("Skipping malformed document record: %s", e)

    # Return pure list if frontend query params present or requested
    if workspace_id is not None or format is not None or as_list or request.headers.get("x-frontend") == "true":
        return [doc.model_dump() for doc in documents]

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
    """Get version history for a document from Person 2's Ingestion service."""
    ingestion = IngestionClient()
    doc_info = await ingestion.get_document(document_id)
    if not doc_info:
        raise HTTPException(status_code=404, detail=f"Document version info not found for '{document_id}'")
    return doc_info
