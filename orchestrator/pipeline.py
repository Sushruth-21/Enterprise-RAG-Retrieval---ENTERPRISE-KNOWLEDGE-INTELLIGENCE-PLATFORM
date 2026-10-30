import hashlib
import logging
import time
import uuid
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from chunking import split_document_into_chunks
from models.db import Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from models.schemas import ChunkModel, DocumentCreate
from parsers import parse_document
from parsers.models import ParsedDocument
from versioning import DuplicateDocumentError, VersionControlManager
from .models import IngestionRequest, IngestionResult

logger = logging.getLogger("document_intelligence.orchestrator")


class IngestionOrchestrator:
    """
    Coordinates the end-to-end Document Intelligence Ingestion Pipeline:
    1. File ingestion & SHA-256 hashing.
    2. Idempotency & duplicate check.
    3. Structural parsing (PDF, DOCX, TXT, Markdown).
    4. Structure-aware chunking with table grouping and context prepending.
    5. Transactional database handoff (document registration & chunk bulk insert).
    """

    @classmethod
    def ingest_document(
        cls,
        session: Session,
        request: IngestionRequest,
        raise_on_error: bool = False,
    ) -> IngestionResult:
        """
        Executes the complete document ingestion pipeline.
        """
        start_time = time.perf_counter()
        file_path = Path(request.file_path)
        logger.info(
            f"=== [INGESTION START] File: '{file_path.name}' | Tenant: {request.organization_id} "
            f"| Canonical ID: {request.canonical_id} | Version: {request.version} ==="
        )

        # -------------------------------------------------------------
        # Step 1: File Validation & SHA-256 Hashing
        # -------------------------------------------------------------
        if not file_path.exists():
            error_msg = f"Source document file not found at '{file_path}'"
            logger.error(f"[HASHING FAILED] {error_msg}")
            if raise_on_error:
                raise FileNotFoundError(error_msg)
            return cls._build_failure_result(
                request=request,
                error_message=error_msg,
                start_time=start_time,
            )

        file_hash = cls.compute_file_hash(file_path)
        file_size_kb = round(file_path.stat().st_size / 1024, 2)
        logger.info(
            f"[STAGE 1 - HASHING] SHA-256: {file_hash} | Size: {file_size_kb} KB"
        )

        # -------------------------------------------------------------
        # Step 2: Idempotency & Duplicate Check
        # -------------------------------------------------------------
        existing_doc = VersionControlManager.check_duplicate_file(
            session=session,
            organization_id=request.organization_id,
            file_hash=file_hash,
        )
        if existing_doc:
            error_msg = (
                f"Duplicate file detected (hash={file_hash[:12]}...). "
                f"Already ingested as document '{existing_doc.name}' (ID: {existing_doc.id})."
            )
            logger.warning(f"[STAGE 2 - DUPLICATE SKIP] {error_msg}")
            if raise_on_error:
                raise DuplicateDocumentError(
                    file_hash=file_hash,
                    existing_document_id=existing_doc.id,
                    organization_id=request.organization_id,
                )
            return IngestionResult(
                document_id=existing_doc.id,
                organization_id=request.organization_id,
                document_name=existing_doc.name,
                canonical_id=existing_doc.canonical_id,
                version=existing_doc.version,
                status=existing_doc.status,
                file_hash=file_hash,
                total_pages=0,
                total_chunks=0,
                processing_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
                success=False,
                error_message=error_msg,
                metadata={"action": "skipped_duplicate", "existing_document_id": str(existing_doc.id)},
            )

        # -------------------------------------------------------------
        # Step 3: Format-Specific Parsing
        # -------------------------------------------------------------
        logger.info(f"[STAGE 3 - PARSING] Routing to parser for '{file_path.suffix}'...")
        parsed_doc: ParsedDocument = parse_document(file_path)

        if not parsed_doc.success:
            error_msg = f"Parsing failure: {parsed_doc.error_message}"
            logger.error(f"[STAGE 3 - PARSING FAILED] {error_msg}")
            if raise_on_error:
                raise RuntimeError(error_msg)
            return cls._build_failure_result(
                request=request,
                error_message=error_msg,
                start_time=start_time,
                file_hash=file_hash,
            )

        doc_name = request.name or parsed_doc.title or file_path.stem.replace("_", " ").title()
        logger.info(
            f"[STAGE 3 - PARSING COMPLETED] Title: '{doc_name}' | Pages: {parsed_doc.total_pages} "
            f"| Structural Elements: {len(parsed_doc.elements)} | Tables: {len(parsed_doc.tables)}"
        )

        # -------------------------------------------------------------
        # Step 4: Structure-Aware Chunking
        # -------------------------------------------------------------
        new_doc_id = uuid.uuid4()
        logger.info(
            f"[STAGE 4 - CHUNKING] Generating structure-aware chunks (target tokens: "
            f"{request.min_tokens_per_chunk}-{request.max_tokens_per_chunk})..."
        )

        chunks: List[ChunkModel] = split_document_into_chunks(
            parsed_doc=parsed_doc,
            document_id=new_doc_id,
            organization_id=request.organization_id,
            document_name=doc_name,
            version=request.version,
            document_status=DocumentStatus.CURRENT,
            embedding_model=request.embedding_model,
            min_tokens=request.min_tokens_per_chunk,
            max_tokens=request.max_tokens_per_chunk,
        )

        logger.info(
            f"[STAGE 4 - CHUNKING COMPLETED] Generated {len(chunks)} chunks with context breadcrumbs "
            f"and SHA-256 chunk hashes."
        )

        # -------------------------------------------------------------
        # Step 5: Database Handoff & Version Management
        # -------------------------------------------------------------
        logger.info(
            f"[STAGE 5 - DATABASE HANDOFF] Executing transaction: registering document {new_doc_id} "
            f"and bulk-inserting {len(chunks)} chunks..."
        )

        doc_create = DocumentCreate(
            organization_id=request.organization_id,
            name=doc_name,
            canonical_id=request.canonical_id,
            version=request.version,
            effective_date=request.effective_date,
            supersedes_id=request.supersedes_id,
            file_uri=request.file_uri or str(file_path.resolve()),
            file_hash=file_hash,
            mime_type=request.mime_type or parsed_doc.file_type,
        )

        try:
            new_doc, cascaded_count = VersionControlManager.register_document_version(
                session=session,
                document_data={**doc_create.model_dump(), "id": new_doc_id},
                chunks=chunks,
                supersedes_id=request.supersedes_id,
            )
            session.commit()
            logger.info(
                f"[STAGE 5 - TRANSACTION COMMITTED] Document {new_doc.id} active. "
                f"Inserted {len(chunks)} chunks (status=pending, embedding=NULL). "
                f"Cascaded {cascaded_count} prior chunks to 'superseded'."
            )
        except Exception as e:
            session.rollback()
            logger.error(f"[STAGE 5 - TRANSACTION FAILED] Rolled back: {str(e)}", exc_info=True)
            if raise_on_error:
                raise
            return cls._build_failure_result(
                request=request,
                error_message=f"Database transaction failure: {str(e)}",
                start_time=start_time,
                file_hash=file_hash,
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"=== [INGESTION SUCCESS] Document '{doc_name}' ingested in {duration_ms} ms ==="
        )

        return IngestionResult(
            document_id=new_doc.id,
            organization_id=request.organization_id,
            document_name=new_doc.name,
            canonical_id=new_doc.canonical_id,
            version=new_doc.version,
            status=new_doc.status,
            file_hash=file_hash,
            total_pages=parsed_doc.total_pages,
            total_chunks=len(chunks),
            superseded_chunks_count=cascaded_count,
            superseded_doc_id=request.supersedes_id,
            processing_time_ms=duration_ms,
            success=True,
            metadata={
                "file_type": parsed_doc.file_type,
                "file_size_kb": file_size_kb,
                "table_count": len(parsed_doc.tables),
                "embedding_model": request.embedding_model,
            },
        )

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Computes the SHA-256 hash of a file's raw binary contents in 64KB blocks."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _build_failure_result(
        request: IngestionRequest,
        error_message: str,
        start_time: float,
        file_hash: str = "",
    ) -> IngestionResult:
        return IngestionResult(
            document_id=uuid.uuid4(),
            organization_id=request.organization_id,
            document_name=request.name or "Unknown",
            canonical_id=request.canonical_id,
            version=request.version,
            status=DocumentStatus.CURRENT,
            file_hash=file_hash,
            total_pages=0,
            total_chunks=0,
            processing_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
            success=False,
            error_message=error_message,
        )
