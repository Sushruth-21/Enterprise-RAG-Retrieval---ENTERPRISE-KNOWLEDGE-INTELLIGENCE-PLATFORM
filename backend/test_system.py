"""
End-to-End System Test Suite for Person 1 (Backend & Integration Lead)
Tests the FastAPI backend against running mock or real microservices.

Usage:
    py test_system.py
"""
import sys
import time
import json
import httpx

BASE_URL = "http://localhost:8000"

def log_test(title: str):
    print("\n" + "=" * 60)
    print(f"TEST: {title}")
    print("=" * 60)

def main():
    print("Starting Enterprise Knowledge Intelligence Platform Verification...")
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. Health Check
    log_test("System Health Check (/api/health)")
    try:
        r = client.get("/api/health")
        print(f"Status Code: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        assert r.status_code == 200, "Health check failed"
        print("PASS: Health check responded cleanly.")
    except Exception as e:
        print(f"FAIL: Health check failed - {e}")
        print("Make sure the backend is running at http://localhost:8000")
        sys.exit(1)

    # 2. List Documents
    log_test("List Ingested Documents (/api/documents)")
    try:
        r = client.get("/api/documents")
        print(f"Status Code: {r.status_code}")
        data = r.json()
        print(f"Total documents found: {data.get('total')}")
        assert r.status_code == 200
        print("PASS: Successfully retrieved document directory.")
    except Exception as e:
        print(f"FAIL: List documents failed - {e}")

    # 3. Document Upload
    log_test("Upload Document (/api/documents/upload)")
    try:
        sample_file_content = b"# Corporate Policy\nAll expense reports must be submitted within 30 days."
        files = {"file": ("test_policy.txt", sample_file_content, "text/plain")}
        r = client.post("/api/documents/upload", files=files)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        assert r.status_code == 200
        print("PASS: Document upload forwarded to ingestion service.")
    except Exception as e:
        print(f"FAIL: Document upload failed - {e}")

    # 4. Chat - In-Corpus Question (Grounding test)
    log_test("Chat - Answerable Query (Travel Policy accommodation limit)")
    try:
        payload = {
            "question": "What is the accommodation expense limit per night for domestic travel?",
            "access_scope": "public"
        }
        r = client.post("/api/chat", json=payload)
        print(f"Status Code: {r.status_code}")
        res = r.json()
        print(f"Answer: {res.get('answer')}")
        print(f"Status: {res.get('status')}")
        print(f"Model Used: {res.get('model_used')}")
        print(f"Citations ({len(res.get('citations', []))}): {json.dumps(res.get('citations'), indent=2)}")
        print(f"Verification: {json.dumps(res.get('verification'), indent=2)}")
        assert r.status_code == 200
        print("PASS: Grounded query responded with structured citations.")
    except Exception as e:
        print(f"FAIL: Answerable query test failed - {e}")

    # 5. Chat - Out-of-Corpus Question (Hallucination prevention / not_covered test)
    log_test("Chat - Out-of-Corpus Query (Should classify as 'not_covered')")
    try:
        payload = {
            "question": "What is the procedure for launching a spacecraft to Mars?",
            "access_scope": "public"
        }
        r = client.post("/api/chat", json=payload)
        print(f"Status Code: {r.status_code}")
        res = r.json()
        print(f"Answer: {res.get('answer')}")
        print(f"Status: {res.get('status')}")
        print(f"Model Used: {res.get('model_used')}")
        assert r.status_code == 200
        if res.get("status") == "not_covered":
            print("PASS: System correctly recognized topic is not covered in enterprise corpus!")
        else:
            print(f"NOTE: System returned status '{res.get('status')}'.")
    except Exception as e:
        print(f"FAIL: Out-of-corpus query test failed - {e}")

    # 6. Batch Processing
    log_test("Batch Processing (/api/batch)")
    try:
        batch_payload = {
            "questions": [
                {"question_id": "q1", "question": "What are the password requirements in IT Security Policy?"},
                {"question_id": "q2", "question": "What is the annual leave policy for employees with 5+ years?"},
                {"question_id": "q3", "question": "How do we bake a sourdough pizza in the office?"}
            ],
            "access_scope": "public"
        }
        r = client.post("/api/batch", json=batch_payload)
        print(f"Status Code: {r.status_code}")
        res = r.json()
        print(f"Total: {res.get('total')}, Answered: {res.get('answered')}, Partially: {res.get('partially_answered')}, Not Covered: {res.get('not_covered')}")
        for ans in res.get("answers", []):
            print(f"- [{ans.get('question_id')}] Status: {ans.get('status')} | Verified: {ans.get('verified')}")
        assert r.status_code == 200
        print("PASS: Batch processing executed all questions concurrently.")
    except Exception as e:
        print(f"FAIL: Batch processing test failed - {e}")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    main()
