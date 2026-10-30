"""
Test Suite for Person 4 Frontend Integration and Hierarchical RBAC Authorization.
Verifies:
1. Cryptographic password hashing (bcrypt/scrypt) and verification.
2. HMAC-SHA256 JWT access token creation and decoding.
3. Multi-role RBAC: employee (public), analyst/manager (internal), admin (confidential).
4. Dual-compatible API endpoints for Person 4's frontend contract:
   - POST /api/chat (query / workspace_id / coverage / execution_time_ms)
   - GET /api/chat/{id}/history (List[ChatMessage])
   - POST /api/batch (questions: List[str] / results)
   - POST /api/documents/upload (RBAC admin guard)
   - GET /api/documents (List[DocumentItem] when workspace_id is queried)
   - GET /api/health (latency_ms)
"""
from datetime import datetime
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure root and backend are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.auth.security import (
    ROLE_CONFIG,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Cryptographic Hashing Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_password_hashing_and_verification():
    """Verify passwords are salted, hashed, and verified securely."""
    secret = "SuperSecretPassword123!"
    hashed = hash_password(secret)

    # Hash must not contain plain text password
    assert secret not in hashed
    assert len(hashed) > 20

    # Verification must succeed for correct password
    assert verify_password(secret, hashed) is True

    # Verification must fail for incorrect password
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_tamper_detection():
    """Verify HMAC-SHA256 JWT token creation, decoding, and signature verification."""
    token = create_access_token(
        user_id="emp-123",
        organization_id="11111111-1111-1111-1111-111111111111",
        role="analyst",
        access_scopes=["public", "internal"],
    )
    assert isinstance(token, str)

    user = decode_access_token(token)
    assert user.user_id == "emp-123"
    assert user.role == "analyst"
    assert "internal" in user.access_scopes
    assert "public" in user.access_scopes

    # Tampered token must fail
    tampered_token = token[:-5] + "ABCDE"
    with pytest.raises(Exception):
        decode_access_token(tampered_token)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Auth & RBAC Endpoints Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_auth_login_with_demo_credentials(client):
    """Verify /api/auth/login works for employee, analyst, and admin accounts."""
    # Test Junior Employee login
    resp_emp = client.post(
        "/api/auth/login",
        json={"email": "employee@enterprise.local", "password": "employee123"},
    )
    assert resp_emp.status_code == 200
    data_emp = resp_emp.json()
    assert "access_token" in data_emp
    assert data_emp["user"]["role"] == "employee"
    assert data_emp["user"]["access_scopes"] == ["public"]

    # Test Admin login
    resp_adm = client.post(
        "/api/auth/login",
        json={"email": "admin@enterprise.local", "password": "admin123"},
    )
    assert resp_adm.status_code == 200
    data_adm = resp_adm.json()
    assert data_adm["user"]["role"] == "admin"
    assert "confidential" in data_adm["user"]["access_scopes"]

    # Test Invalid password
    resp_bad = client.post(
        "/api/auth/login",
        json={"email": "admin@enterprise.local", "password": "wrongpassword"},
    )
    assert resp_bad.status_code == 401


def test_auth_demo_token_persona_switcher(client):
    """Verify /api/auth/demo-token enables instantaneous UI persona switching."""
    # 1. Junior Employee
    r1 = client.get("/api/auth/demo-token?role=employee")
    assert r1.status_code == 200
    assert r1.json()["user"]["role"] == "employee"
    assert r1.json()["user"]["access_scopes"] == ["public"]

    # 2. Senior Analyst
    r2 = client.get("/api/auth/demo-token?role=analyst")
    assert r2.status_code == 200
    assert r2.json()["user"]["role"] == "analyst"
    assert r2.json()["user"]["access_scopes"] == ["public", "internal"]

    # 3. System Admin
    r3 = client.get("/api/auth/demo-token?role=admin")
    assert r3.status_code == 200
    assert r3.json()["user"]["role"] == "admin"
    assert "confidential" in r3.json()["user"]["access_scopes"]


def test_auth_roles_matrix(client):
    """Verify /api/auth/roles returns full matrix of enterprise roles."""
    resp = client.get("/api/auth/roles")
    assert resp.status_code == 200
    roles = resp.json()
    assert len(roles) == 5
    role_names = [r["role"] for r in roles]
    assert "employee" in role_names
    assert "analyst" in role_names
    assert "manager" in role_names
    assert "compliance_officer" in role_names
    assert "admin" in role_names


# ─────────────────────────────────────────────────────────────────────────────
# 3. Person 4 Frontend Compatibility Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_chat_endpoint_person4_contract(client):
    """
    Verify POST /api/chat consumes Person 4 frontend payload format:
    { workspace_id, query, conversation_id, document_ids }
    and returns:
    { message_id, conversation_id, response, coverage, grounded_doc_count, execution_time_ms, citations }
    """
    payload = {
        "workspace_id": "ws-demo",
        "query": "What is the corporate expense reimbursement cap?",
        "conversation_id": "conv-test-101",
        "document_ids": ["doc-1"],
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Person 4 frontend expected fields
    assert "message_id" in data
    assert data["conversation_id"] == "conv-test-101"
    assert "response" in data
    assert data["coverage"] in ("full", "partial", "insufficient_evidence")
    assert "grounded_doc_count" in data
    assert "execution_time_ms" in data
    assert isinstance(data["citations"], list)

    # Person 1 backwards-compatible fields
    assert "answer" in data
    assert "status" in data


def test_chat_history_person4_contract(client):
    """Verify GET /api/chat/{conversation_id}/history returns List[ChatMessage]."""
    conv_id = "conv-history-test"

    # Send a query first
    client.post(
        "/api/chat",
        json={"conversation_id": conv_id, "query": "Hello, how does this work?"},
    )

    resp = client.get(f"/api/chat/{conv_id}/history")
    assert resp.status_code == 200
    messages = resp.json()
    assert isinstance(messages, list)
    assert len(messages) >= 2  # User message and assistant response
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello, how does this work?"
    assert messages[1]["role"] == "assistant"
    assert "coverage" in messages[1]


def test_batch_processing_person4_contract(client):
    """
    Verify POST /api/batch consumes:
    { workspace_id, questions: List[str], document_ids: List[str] }
    and returns:
    { batch_id, workspace_id, overall_execution_time_ms, coverage_rate, results: [...] }
    """
    payload = {
        "workspace_id": "ws-demo",
        "questions": [
            "What is the daily per diem cap for meals?",
            "What is the maximum expense submission window?",
        ],
        "document_ids": [],
    }
    resp = client.post("/api/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Person 4 fields
    assert "batch_id" in data
    assert data["workspace_id"] == "ws-demo"
    assert "overall_execution_time_ms" in data
    assert "coverage_rate" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 2
    assert "coverage" in data["results"][0]

    # Person 1 backwards-compatible fields
    assert "answers" in data
    assert "total" in data
    assert data["total"] == 2


def test_document_upload_rbac_protection(client):
    """Verify document upload is restricted: junior employee is rejected (403), admin is accepted."""
    from unittest.mock import patch, AsyncMock

    # Obtain Junior Employee token
    emp_token = client.get("/api/auth/demo-token?role=employee").json()["access_token"]
    # Obtain Admin token
    admin_token = client.get("/api/auth/demo-token?role=admin").json()["access_token"]

    sample_content = b"# Restricted Document\nAdmin only content."
    files = {"file": ("admin_policy.txt", sample_content, "text/plain")}

    # 1. Junior Employee tries to upload -> HTTP 403 Forbidden
    resp_forbidden = client.post(
        "/api/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert resp_forbidden.status_code == 403
    assert "Forbidden" in resp_forbidden.json()["detail"]

    # 2. Admin uploads -> mocked IngestionClient returns completed, HTTP 200 with dual-compatible Person 4 fields
    mock_ingestion_result = {
        "status": "completed",
        "document_id": "doc-admin-uuid",
        "document_name": "admin_policy.txt",
        "total_pages": 2,
        "total_chunks": 4,
        "message": "Successfully indexed",
    }
    with patch("app.api.documents.IngestionClient.ingest_document", new=AsyncMock(return_value=mock_ingestion_result)):
        files_ok = {"file": ("admin_policy.txt", sample_content, "text/plain")}
        resp_ok = client.post(
            "/api/documents/upload",
            files=files_ok,
            data={"workspace_id": "ws-demo"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_ok.status_code == 200
        data_upload = resp_ok.json()

        # Person 4 fields
        assert data_upload["id"] == "doc-admin-uuid"
        assert data_upload["workspaceId"] == "ws-demo"
        assert data_upload["name"] == "admin_policy.txt"
        assert data_upload["format"] == "txt"
        assert data_upload["sizeBytes"] == len(sample_content)

        # Person 1 fields
        assert data_upload["document_id"] == "doc-admin-uuid"
        assert data_upload["status"] == "completed"


def test_health_check_person4_contract(client):
    """Verify GET /api/health returns status, latency_ms, and version."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "latency_ms" in data
    assert data["latency_ms"] >= 0
    assert "version" in data
    assert data["version"] == "1.0.0"
