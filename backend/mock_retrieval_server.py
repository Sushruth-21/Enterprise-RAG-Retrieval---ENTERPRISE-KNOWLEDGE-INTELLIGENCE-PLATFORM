"""
Mock Retrieval Server — simulates Person 3's retrieval service.
Run on port 8002 while Person 3 builds the real thing.

Usage:
    uvicorn mock_retrieval_server:app --port 8002
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Retrieval Server", version="1.0.0")

# ── Mock passage data ──────────────────────────────────────────
MOCK_PASSAGES = [
    {
        "chunk_id": "chunk_001",
        "document_id": "policy_travel_v2",
        "document_name": "Travel Policy",
        "version": "2.0",
        "is_current": True,
        "section": "5.2",
        "page": 12,
        "content": (
            "Employees are entitled to claim accommodation expenses up to ₹5,000 per night "
            "for domestic travel and USD 150 per night for international travel. "
            "All claims must be submitted within 30 days of travel with original receipts."
        ),
        "access_scope": "public",
        "score": 0.95,
    },
    {
        "chunk_id": "chunk_002",
        "document_id": "policy_travel_v2",
        "document_name": "Travel Policy",
        "version": "2.0",
        "is_current": True,
        "section": "3.1",
        "page": 7,
        "content": (
            "Business class travel is permitted only for flights exceeding 6 hours. "
            "Economy class is mandatory for all flights under 6 hours. "
            "Approval from department head is required for any upgrade."
        ),
        "access_scope": "public",
        "score": 0.88,
    },
    {
        "chunk_id": "chunk_003",
        "document_id": "policy_it_security_v1",
        "document_name": "IT Security Policy",
        "version": "1.1",
        "is_current": True,
        "section": "3.1",
        "page": 5,
        "content": (
            "All employee passwords must be a minimum of 12 characters and include at least "
            "one uppercase letter, one lowercase letter, one number, and one special character. "
            "Passwords must be changed every 90 days. Password reuse for the last 10 passwords is prohibited."
        ),
        "access_scope": "public",
        "score": 0.82,
    },
    {
        "chunk_id": "chunk_004",
        "document_id": "policy_hr_handbook_v3",
        "document_name": "HR Employee Handbook",
        "version": "3.0",
        "is_current": True,
        "section": "7.4",
        "page": 24,
        "content": (
            "Annual leave entitlement is 21 days per year for employees with less than 5 years of service, "
            "and 28 days per year for employees with 5 or more years of service. "
            "Leave must be approved by the direct manager at least 2 weeks in advance."
        ),
        "access_scope": "public",
        "score": 0.78,
    },
    {
        "chunk_id": "chunk_005",
        "document_id": "policy_travel_v1",
        "document_name": "Travel Policy",
        "version": "1.0",
        "is_current": False,
        "section": "5.2",
        "page": 10,
        "content": (
            "[SUPERSEDED] Employees were previously entitled to claim accommodation expenses up to "
            "₹3,500 per night for domestic travel. This policy was superseded by Travel Policy v2.0 "
            "effective January 2024."
        ),
        "access_scope": "public",
        "score": 0.60,
    },
]


class SearchRequest(BaseModel):
    query: str
    access_scope: str = "public"
    top_k: int = 10
    doc_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock_retrieval"}


@app.post("/search")
def search(req: SearchRequest) -> List[dict]:
    """Return mock passages relevant to the query."""
    results = [p for p in MOCK_PASSAGES if p["access_scope"] == req.access_scope or req.access_scope == "public"]
    if req.doc_id:
        results = [p for p in results if p["document_id"] == req.doc_id]
    return results[: req.top_k]


@app.get("/passage/{chunk_id}")
def get_passage(chunk_id: str):
    """Return a single passage by chunk_id."""
    for p in MOCK_PASSAGES:
        if p["chunk_id"] == chunk_id:
            return p
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
