"""
Mock Retrieval Server — simulates Person 3's retrieval service.
Run on port 8002 while Person 3 builds the real thing.
Augmented with live lookup to Knowledge Vault and Ingestion Service (port 8003).

Usage:
    uvicorn mock_retrieval_server:app --port 8002
"""
from __future__ import annotations
import logging
import re
from typing import List, Optional
import httpx

from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger("mock_retrieval")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mock Retrieval Server", version="1.0.0")

# Clean production: No hardcoded mock documents or policies
MOCK_PASSAGES: List[dict] = []


class SearchRequest(BaseModel):
    query: str
    access_scope: str = "public"
    top_k: int = 10
    doc_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock_retrieval"}


@app.post("/search")
async def search(req: SearchRequest) -> List[dict]:
    """Return passages relevant to the query from Knowledge Vault and Ingestion Service."""
    all_candidates: List[dict] = list(MOCK_PASSAGES)

    # 1. Check local Knowledge Vault directly
    try:
        from app.storage.vault import KnowledgeVault
        vault = KnowledgeVault.get_instance()
        vault_passages = vault.search_chunks(req.query, doc_id=req.doc_id, top_k=req.top_k)
        for p in vault_passages:
            all_candidates.append(p.model_dump())
    except Exception as exc:
        logger.debug("Knowledge Vault lookup in mock retrieval: %s", exc)

    # 2. Attempt to pull real uploaded document chunks from Ingestion Service (Port 8003)
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.post(
                "http://localhost:8003/search",
                json={"query": req.query, "top_k": req.top_k, "doc_id": req.doc_id},
            )
            if resp.status_code == 200:
                ingested_passages = resp.json()
                if ingested_passages:
                    all_candidates.extend(ingested_passages)
    except Exception as exc:
        logger.debug("Could not query ingestion service: %s", exc)

    q_lower = req.query.lower()
    q_words = [w for w in re.findall(r"\w+", q_lower) if len(w) > 2]

    results = []
    seen_ids = set()
    for p in all_candidates:
        if p["chunk_id"] in seen_ids:
            continue
        if req.doc_id and p["document_id"] != req.doc_id:
            continue

        content_lower = p["content"].lower()
        if not q_words or any(w in content_lower for w in q_words) or (p.get("score", 0) > 0.5):
            results.append(p)
            seen_ids.add(p["chunk_id"])

    results.sort(key=lambda x: x.get("score", 0.5), reverse=True)
    return results[: req.top_k]


@app.get("/passage/{chunk_id}")
def get_passage(chunk_id: str):
    # Check Knowledge Vault
    try:
        from app.storage.vault import KnowledgeVault
        vault = KnowledgeVault.get_instance()
        with vault._get_connection() as conn:
            row = conn.execute("SELECT * FROM vault_chunks WHERE id = ?", (chunk_id,)).fetchone()
            if row:
                return {
                    "chunk_id": row["id"],
                    "document_id": row["document_id"],
                    "document_name": row["document_name"],
                    "version": "1.0",
                    "is_current": True,
                    "section": row["section_context"],
                    "page": row["page_number"],
                    "content": row["content"],
                    "access_scope": "public",
                    "score": 0.9,
                }
    except Exception:
        pass

    for p in MOCK_PASSAGES:
        if p["chunk_id"] == chunk_id:
            return p
    return {"error": "not found"}
