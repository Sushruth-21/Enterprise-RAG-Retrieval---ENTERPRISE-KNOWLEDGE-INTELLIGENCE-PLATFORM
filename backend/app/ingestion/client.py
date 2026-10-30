from __future__ import annotations
import logging
from typing import Dict, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class IngestionClient:
    """HTTP client for Person 2's document ingestion service (port 8003)."""

    def __init__(self) -> None:
        self.base_url = get_settings().INGESTION_API_URL.rstrip("/")

    async def ingest_document(
        self, file_bytes: bytes, filename: str, content_type: str
    ) -> dict:
        """Forward a document to Person 2's ingestion service."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.base_url}/ingest",
                    files={"file": (filename, file_bytes, content_type)},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            logger.warning("Ingestion service not reachable at %s", self.base_url)
            return {"error": "Ingestion service unavailable", "status": "failed"}
        except Exception as exc:
            logger.error("IngestionClient.ingest_document error: %s", exc)
            return {"error": str(exc), "status": "failed"}

    async def list_documents(self) -> List[dict]:
        """Get all documents from ingestion service."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/documents")
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("IngestionClient.list_documents error: %s", exc)
            return []

    async def get_document(self, document_id: str) -> Optional[dict]:
        """Get a specific document by ID."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/documents/{document_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("IngestionClient.get_document error: %s", exc)
            return None
