import logging
import uuid
from typing import List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus, ProcessingStatus
from models.schemas import ChunkModel, DocumentCreate
from .exceptions import (
    DocumentNotFoundError,
    DuplicateDocumentError,
    TenantViolationError,
)

logger = logging.getLogger("document_intelligence.versioning")


class VersionControlManager:
    """
    Manages document lifecycle, version lineage, duplicate detection,
    and transactional status cascades across PostgreSQL documents and chunks.
    """

    @staticmethod
    def check_duplicate_file(
        session: Session, organization_id: UUID, file_hash: str
    ) -> Optional[DocumentDB]:
        """
        Checks whether a file with identical SHA-256 hash has already been ingested
        for this organization.
        """
        stmt = select(DocumentDB).where(
            DocumentDB.organization_id == organization_id,
            DocumentDB.file_hash == file_hash,
        )
        return session.scalar(stmt)

    @classmethod
    def register_document_version(
        cls,
        session: Session,
        document_data: Union[DocumentCreate, dict],
        chunks: Optional[List[ChunkModel]] = None,
        supersedes_id: Optional[UUID] = None,
        allow_duplicate: bool = False,
    ) -> Tuple[DocumentDB, int]:
        """
        Executes an atomic database transaction to register a document and handle version lineage.

        Transactional Workflow:
        1. Checks for duplicate uploads via file_hash.
        2. Validates explicit supersedes_id (never relies on filenames).
        3. Sets superseded document status to 'superseded'.
        4. Cascades status update to ALL related chunks in the database:
           UPDATE chunks SET document_status = 'superseded' WHERE document_id = :supersedes_id
        5. Inserts the new Document with status = 'current' and explicit lineage pointer.
        6. Inserts all new chunks with document_status = 'current' and processing_status = 'pending'.

        :returns: Tuple of (new Document record, count of prior chunks cascaded).
        :raises DuplicateDocumentError: If identical file_hash exists in organization.
        :raises DocumentNotFoundError: If cited supersedes_id does not exist in organization.
        """
        # Normalize input dictionary
        if isinstance(document_data, DocumentCreate):
            doc_dict = document_data.model_dump()
        else:
            doc_dict = dict(document_data)

        org_id = doc_dict["organization_id"]
        file_hash = doc_dict["file_hash"]
        target_supersedes_id = supersedes_id or doc_dict.get("supersedes_id")

        # 1. Duplicate Detection Check
        if not allow_duplicate:
            existing = cls.check_duplicate_file(session, org_id, file_hash)
            if existing:
                logger.warning(
                    f"Duplicate file upload detected (hash={file_hash[:12]}...). "
                    f"Existing doc_id={existing.id} in org={org_id}."
                )
                raise DuplicateDocumentError(
                    file_hash=file_hash,
                    existing_document_id=existing.id,
                    organization_id=org_id,
                )

        chunks_cascaded_count = 0

        # Execute atomically inside transaction block
        with session.begin_nested():
            # 2. Lineage Resolution via Explicit supersedes_id
            if target_supersedes_id:
                predecessor = session.scalar(
                    select(DocumentDB).where(
                        DocumentDB.id == target_supersedes_id,
                        DocumentDB.organization_id == org_id,
                    )
                )

                if not predecessor:
                    # Check if it exists in another organization (tenant violation)
                    other_tenant_doc = session.scalar(
                        select(DocumentDB).where(DocumentDB.id == target_supersedes_id)
                    )
                    if other_tenant_doc:
                        raise TenantViolationError(
                            f"Predecessor document '{target_supersedes_id}' belongs to another organization."
                        )
                    raise DocumentNotFoundError(
                        document_id=target_supersedes_id, organization_id=org_id
                    )

                logger.info(
                    f"Superseding document {target_supersedes_id} ('{predecessor.name}') "
                    f"with new revision '{doc_dict.get('name')}'"
                )

                # 3. Transition Old Document Status -> 'superseded'
                predecessor.status = DocumentStatus.SUPERSEDED

                # 4. Cascade Status to ALL Related Chunks
                cascade_stmt = (
                    update(ChunkDB)
                    .where(
                        ChunkDB.document_id == target_supersedes_id,
                        ChunkDB.organization_id == org_id,
                    )
                    .values(document_status=DocumentStatus.SUPERSEDED)
                )
                result = session.execute(cascade_stmt)
                chunks_cascaded_count = result.rowcount
                logger.info(
                    f"Cascaded 'superseded' status to {chunks_cascaded_count} chunks "
                    f"for document {target_supersedes_id}"
                )

            # 5. Insert New Document with status = 'current'
            new_doc = DocumentDB(
                id=doc_dict.get("id", uuid.uuid4()),
                organization_id=org_id,
                name=doc_dict["name"],
                canonical_id=doc_dict["canonical_id"],
                version=doc_dict["version"],
                status=DocumentStatus.CURRENT,
                effective_date=doc_dict["effective_date"],
                supersedes_id=target_supersedes_id,
                file_uri=doc_dict["file_uri"],
                file_hash=file_hash,
                mime_type=doc_dict.get("mime_type"),
            )
            session.add(new_doc)
            session.flush()  # Flush to populate new_doc.id

            # 6. Insert New Chunks (if provided)
            if chunks:
                chunk_entities = []
                for chunk_model in chunks:
                    chunk_entities.append(
                        ChunkDB(
                            chunk_id=chunk_model.chunk_id,
                            organization_id=org_id,
                            document_id=new_doc.id,
                            document_name=new_doc.name,
                            version=new_doc.version,
                            chunk_index=chunk_model.chunk_index,
                            section_context=chunk_model.section_context,
                            page_number=chunk_model.page_number,
                            content=chunk_model.content,
                            chunk_hash=chunk_model.chunk_hash,
                            embedding_model=chunk_model.embedding_model,
                            processing_status=ProcessingStatus.PENDING,
                            document_status=DocumentStatus.CURRENT,
                        )
                    )
                session.add_all(chunk_entities)
                logger.info(
                    f"Inserted {len(chunk_entities)} new chunks for document {new_doc.id}"
                )

        logger.info(
            f"Successfully registered document {new_doc.id} (version={new_doc.version}, "
            f"status={new_doc.status.value})"
        )
        return new_doc, chunks_cascaded_count
