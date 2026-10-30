from __future__ import annotations
import logging
from datetime import date
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class IngestionClient:
    """HTTP client for Person 2's document ingestion service (port 8003)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.INGESTION_API_URL.rstrip("/")
        self.upload_path = settings.INGESTION_UPLOAD_PATH
        self.status_path = settings.INGESTION_STATUS_PATH

    async def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        organization_id: str = "public",
        document_name: Optional[str] = None,
        version_label: str = "1.0",
        supersedes_id: Optional[str] = None,
        effective_date: Optional[date] = None,
    ) -> dict:
        """Forward a document to Person 2's ingestion service."""
        data = {
            "organization_id": organization_id,
            "document_name": document_name or filename,
            "version_label": version_label,
        }
        if supersedes_id:
            data["supersedes_id"] = supersedes_id
        if effective_date:
            data["effective_date"] = effective_date.isoformat()

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.base_url}/{self.upload_path.lstrip('/')}",
                    files={"file": (filename, file_bytes, content_type)},
                    data=data,
                )
                if resp.is_error:
                    return {
                        "status": "failed",
                        "error": self._format_error(resp),
                        "http_status": resp.status_code,
                    }
                return self._normalize_upload_response(resp.json())
        except httpx.ConnectError:
            logger.warning("Ingestion service not reachable at %s", self.base_url)
            return {"error": "Ingestion service unavailable", "status": "failed"}
        except httpx.TimeoutException:
            logger.warning("Ingestion service timed out at %s", self.base_url)
            return {"error": "Ingestion service timed out", "status": "failed"}
        except Exception as exc:
            logger.error("IngestionClient.ingest_document error: %s", exc)
            return {"error": str(exc), "status": "failed"}

    @staticmethod
    def _format_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Ingestion service returned HTTP {response.status_code}"
        error = payload.get("error")
        if isinstance(error, dict):
            return error.get("message", str(error))
        return payload.get("detail") or str(error or payload)

    @staticmethod
    def _normalize_upload_response(payload: dict) -> dict:
        if payload.get("success") is False:
            error = payload.get("error", "Ingestion request failed")
            return {
                "status": "failed",
                "error": error.get("message", str(error))
                if isinstance(error, dict)
                else str(error),
            }
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            return {"status": "failed", "error": "Invalid ingestion response"}
        return {
            **data,
            "status": data.get("status", "processing"),
            "document_id": data.get("document_id", "unknown"),
            "document_name": data.get("document_name", ""),
            "version_id": data.get("version_id"),
            "status_url": data.get("status_url"),
        }

    async def get_processing_status(self, version_id: str) -> Optional[dict]:
        """Get asynchronous processing status for an uploaded document version."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/{self.status_path.lstrip('/')}/{version_id}"
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("IngestionClient.get_processing_status error: %s", exc)
            return None

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
