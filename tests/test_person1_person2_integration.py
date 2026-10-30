"""
End-to-End Integration Test Suite for Person 1 (Backend/Orchestration) + Person 2 (Document Intelligence & OCR)
Verifies that Person 1's backend and ingestion client seamlessly interface with Person 2's real ingestion engine.
"""
import io
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure root and backend are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from real_ingestion_server import app as ingestion_app
from app.main import app as person1_main_app


@pytest.fixture
def ingestion_client():
    return TestClient(ingestion_app)


@pytest.fixture
def person1_client():
    return TestClient(person1_main_app)


def test_real_ingestion_server_health(ingestion_client):
    """Verify Person 2's real ingestion microservice health check."""
    resp = ingestion_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["engine"] == "person2_production"
    assert "pdf" in data["supported_formats"]
    assert "png" in data["supported_formats"]


def test_real_ingestion_server_document_processing(ingestion_client):
    """
    Verify Person 2's real ingestion microservice parses, chunks, and indexes a real document.
    """
    doc_content = (
        b"# ACME Corp Security Guidelines\n\n"
        b"## Password Complexity Policy\n"
        b"All employees must use 16-character passwords with alphanumeric and special characters.\n\n"
        b"| Role | Minimum Length | Expiry Days |\n"
        b"| --- | --- | --- |\n"
        b"| Standard User | 16 | 90 |\n"
        b"| Administrator | 24 | 30 |\n\n"
        b"## MFA Requirements\n"
        b"Hardware security keys (FIDO2) are required for all privileged accounts."
    )

    files = {"file": ("security_policy.md", doc_content, "text/markdown")}
    data = {
        "organization_id": "corp_acme",
        "document_name": "ACME Security Policy 2026",
        "version_label": "2.1",
    }

    # Test POST /ingest
    resp = ingestion_client.post("/ingest", files=files, data=data)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "completed"
    assert result["document_name"] == "ACME Security Policy 2026"
    assert result["total_chunks"] >= 1
    assert result["table_count"] == 1
    assert "Successfully parsed and chunked" in result["message"]

    doc_id = result["document_id"]

    # Test GET /documents
    list_resp = ingestion_client.get("/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["document_id"] == doc_id for d in docs)

    # Test GET /documents/{doc_id}
    detail_resp = ingestion_client.get(f"/documents/{doc_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["title"] == "ACME Corp Security Guidelines"
    assert "chunk_id" in detail["chunks"][0]
    assert "section_context" in detail["chunks"][0]


def test_person1_backend_health(person1_client):
    """Verify Person 1's main FastAPI backend launches and responds to health probe."""
    resp = person1_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "ollama_available" in data
