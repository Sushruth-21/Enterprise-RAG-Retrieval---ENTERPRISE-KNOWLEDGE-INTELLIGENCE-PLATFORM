from __future__ import annotations
import logging
from typing import List, Optional

import httpx

from app.config import get_settings
from app.schemas import DocumentPassage

logger = logging.getLogger(__name__)


class RetrievalClient:
    """HTTP client for Person 3's retrieval service (port 8002)."""

    def __init__(self) -> None:
        self.base_url = get_settings().RETRIEVAL_API_URL.rstrip("/")

    async def hybrid_search(
        self,
        query: str,
        access_scope: str = "public",
        top_k: int = 10,
        doc_id: Optional[str] = None,
    ) -> List[DocumentPassage]:
        """Call Person 3's /search endpoint. Returns empty list on failure."""
        payload: dict = {"query": query, "access_scope": access_scope, "top_k": top_k}
        if doc_id:
            payload["doc_id"] = doc_id
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self.base_url}/search", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return [DocumentPassage(**item) for item in data]
        except httpx.ConnectError:
            logger.warning("Retrieval service not reachable at %s", self.base_url)
            return []
        except Exception as exc:
            logger.error("RetrievalClient.hybrid_search error: %s", exc)
            return []

    async def get_passage_by_chunk_id(self, chunk_id: str) -> Optional[DocumentPassage]:
        """Fetch a single passage by chunk ID."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/passage/{chunk_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return DocumentPassage(**resp.json())
        except Exception as exc:
            logger.error("RetrievalClient.get_passage error: %s", exc)
            return None
