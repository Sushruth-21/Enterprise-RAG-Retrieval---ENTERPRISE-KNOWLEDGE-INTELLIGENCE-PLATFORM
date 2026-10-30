from uuid import UUID


class VersioningError(Exception):
    """Base exception for version management failures."""
    pass


class DuplicateDocumentError(VersioningError):
    """Raised when an identical file hash is already ingested for the organization."""

    def __init__(self, file_hash: str, existing_document_id: UUID, organization_id: UUID):
        self.file_hash = file_hash
        self.existing_document_id = existing_document_id
        self.organization_id = organization_id
        super().__init__(
            f"Document with file_hash '{file_hash}' already exists in organization "
            f"'{organization_id}' (Document ID: {existing_document_id}). Ingestion skipped."
        )


class DocumentNotFoundError(VersioningError):
    """Raised when a cited supersedes_id does not exist."""

    def __init__(self, document_id: UUID, organization_id: UUID):
        self.document_id = document_id
        self.organization_id = organization_id
        super().__init__(
            f"Predecessor document '{document_id}' not found in organization '{organization_id}'."
        )


class TenantViolationError(VersioningError):
    """Raised when attempting to link lineage across different tenant boundaries."""
    pass
