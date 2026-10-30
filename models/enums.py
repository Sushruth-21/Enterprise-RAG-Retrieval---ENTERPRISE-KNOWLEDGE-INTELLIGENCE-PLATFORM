import enum


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of a document and its chunks in the pipeline."""
    CURRENT = "current"
    SUPERSEDED = "superseded"


class ProcessingStatus(str, enum.Enum):
    """Embedding/ingestion processing state for chunks."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
