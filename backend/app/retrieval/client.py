from __future__ import annotations
import logging
import os
from typing import List, Optional

import httpx

from app.config import get_settings
from app.schemas import DocumentPassage
from app.storage.vault import KnowledgeVault

logger = logging.getLogger(__name__)


class RetrievalClient:
    """HTTP client for retrieval across local Knowledge Vault,
    Person 3's service (port 8002) and Ingestion service (port 8003)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.RETRIEVAL_API_URL.rstrip("/")
        self.ingestion_url = settings.INGESTION_API_URL.rstrip("/")

    async def hybrid_search(
        self,
        query: str,
        access_scope: str = "public",
        top_k: int = 10,
        doc_id: Optional[str] = None,
        doc_ids: Optional[List[str]] = None,
        workspace_id: Optional[str] = None,
    ) -> List[DocumentPassage]:
        if doc_ids is not None and len(doc_ids) == 0:
            return []

        all_passages: List[DocumentPassage] = []

        # ── 1. Query Knowledge Vault (Local Persistent DB) ──
        try:
            vault = KnowledgeVault.get_instance()
            vault_passages = vault.search_chunks(
                query=query,
                workspace_id=workspace_id,
                doc_id=doc_id,
                doc_ids=doc_ids,
                access_scope=access_scope,
                top_k=top_k,
            )
            if vault_passages:
                logger.info("Found %d passages in local Knowledge Vault", len(vault_passages))
                all_passages.extend(vault_passages)
        except Exception as exc:
            logger.error("Knowledge Vault search error: %s", exc)

        # ── 2. Query primary retrieval service (port 8002) if running and local vault has no matches ──
        enable_ext = os.getenv("ENABLE_EXTERNAL_RETRIEVAL", "false").lower() in ("true", "1")
        if not all_passages and enable_ext:
            payload: dict = {
                "query": query,
                "access_scope": access_scope,
                "top_k": top_k,
                "workspace_id": workspace_id,
            }
            if doc_ids:
                payload["doc_ids"] = doc_ids
            elif doc_id:
                payload["doc_id"] = doc_id

            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(0.5, connect=0.5)) as client:
                    resp = await client.post(f"{self.base_url}/search", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        all_passages.extend([DocumentPassage(**item) for item in data])
            except (httpx.ConnectError, httpx.TimeoutException, OSError):
                logger.debug("Retrieval service not reachable at %s", self.base_url)
            except Exception as exc:
                logger.error("RetrievalClient.hybrid_search error: %s", exc)

            # ── 3. Query Ingestion service (port 8003) if running ──
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(0.5, connect=0.5)) as client:
                    resp = await client.post(f"{self.ingestion_url}/search", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        all_passages.extend([DocumentPassage(**item) for item in data])
            except (httpx.ConnectError, httpx.TimeoutException, OSError):
                logger.debug("Ingestion search fallback not reachable at %s", self.ingestion_url)
            except Exception as exc:
                logger.error("Ingestion search error: %s", exc)

        # Filter strictly by doc_ids if specified (prevents returning previous sources)
        if doc_ids is not None:
            doc_id_set = set(doc_ids)
            all_passages = [p for p in all_passages if p.document_id in doc_id_set]

        # Deduplicate by chunk_id and sort by relevance score descending
        seen_ids = set()
        deduped: List[DocumentPassage] = []
        for p in all_passages:
            if p.chunk_id not in seen_ids:
                seen_ids.add(p.chunk_id)
                deduped.append(p)

        deduped.sort(key=lambda x: x.score, reverse=True)
        return deduped[:top_k]

    async def get_passage_by_chunk_id(self, chunk_id: str) -> Optional[DocumentPassage]:
        """Fetch a single passage by chunk ID."""
        try:
            vault = KnowledgeVault.get_instance()
            with vault._get_connection() as conn:
                row = conn.execute("SELECT * FROM vault_chunks WHERE id = ?", (chunk_id,)).fetchone()
                if row:
                    return DocumentPassage(
                        chunk_id=row["id"],
                        document_id=row["document_id"],
                        document_name=row["document_name"],
                        version="1.0",
                        is_current=True,
                        section=row["section_context"] or f"Page {row['page_number']}",
                        page=row["page_number"],
                        content=row["content"],
                        access_scope=row["access_scope"],
                        score=0.9,
                    )
        except Exception as exc:
            logger.debug("Vault get_passage error: %s", exc)

        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self.base_url}/passage/{chunk_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return DocumentPassage(**resp.json())
        except Exception as exc:
            logger.error("RetrievalClient.get_passage error: %s", exc)
            return None
