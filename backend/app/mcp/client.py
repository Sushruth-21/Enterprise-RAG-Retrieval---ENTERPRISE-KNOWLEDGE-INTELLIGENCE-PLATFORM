from __future__ import annotations
import logging
from typing import Dict, List, Optional

import httpx

from app.config import get_settings
from app.schemas import DocumentPassage

logger = logging.getLogger(__name__)


class MCPClient:
    """HTTP client for Person 4's MCP server (port 8001).
    Calls tools via POST /tools/{tool_name} with JSON body.
    """

    def __init__(self) -> None:
        self.base_url = get_settings().MCP_SERVER_URL.rstrip("/")

    async def _call_tool(self, tool_name: str, payload: dict) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/tools/{tool_name}", json=payload
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            logger.warning("MCP server not reachable at %s", self.base_url)
            return None
        except Exception as exc:
            logger.error("MCPClient._call_tool(%s) error: %s", tool_name, exc)
            return None

    async def search_documents(
        self,
        query: str,
        department: Optional[str] = None,
        doc_type: Optional[str] = None,
        version: Optional[str] = None,
    ) -> List[DocumentPassage]:
        result = await self._call_tool(
            "search_documents",
            {"query": query, "department": department, "doc_type": doc_type, "version": version},
        )
        if not result:
            return []
        try:
            items = result if isinstance(result, list) else result.get("passages", [])
            return [DocumentPassage(**item) for item in items]
        except Exception as exc:
            logger.error("MCPClient.search_documents parse error: %s", exc)
            return []

    async def get_document_details(self, document_id: str) -> dict:
        result = await self._call_tool("get_document_details", {"document_id": document_id})
        return result or {}

    async def get_document_version(self, document_id: str) -> dict:
        result = await self._call_tool("get_document_version", {"document_id": document_id})
        return result or {}

    async def get_policy_section(self, document_id: str, section: str) -> dict:
        result = await self._call_tool(
            "get_policy_section", {"document_id": document_id, "section": section}
        )
        return result or {}

    async def get_source_passage(self, chunk_id: str) -> Optional[DocumentPassage]:
        result = await self._call_tool("get_source_passage", {"chunk_id": chunk_id})
        if not result:
            return None
        try:
            return DocumentPassage(**result)
        except Exception:
            return None

    async def compare_document_versions(self, doc_id_v1: str, doc_id_v2: str) -> dict:
        result = await self._call_tool(
            "compare_document_versions",
            {"doc_id_v1": doc_id_v1, "doc_id_v2": doc_id_v2},
        )
        return result or {}

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
