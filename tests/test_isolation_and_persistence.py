import unittest
import os
import sys
from datetime import datetime

# Ensure backend on sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.schemas import DocumentInfo, DocumentUploadResponse
from app.storage.vault import KnowledgeVault


class TestIsolationAndPersistence(unittest.TestCase):
    def test_document_info_serialization_for_frontend(self):
        """DocumentInfo includes uploadedAt, status, accessScope, and isEmployeeAccessible."""
        doc = DocumentInfo(
            id="doc_test_101",
            workspaceId="default",
            name="Employee Safety Manual.pdf",
            format="pdf",
            sizeBytes=2048,
            pageCount=5,
            chunkCount=12,
            summary="Safety procedures and requirements",
            access_scope="public",
            uploaded_at=datetime(2026, 10, 31, 8, 0, 0),
        )
        d_dict = doc.model_dump()
        self.assertEqual(d_dict["id"], "doc_test_101")
        self.assertEqual(d_dict["name"], "Employee Safety Manual.pdf")
        self.assertEqual(d_dict["format"], "pdf")
        self.assertEqual(d_dict["status"], "ready")
        self.assertEqual(d_dict["accessScope"], "public")
        self.assertTrue(d_dict["isEmployeeAccessible"])
        self.assertIn("uploadedAt", d_dict)
        self.assertTrue(d_dict["uploadedAt"].startswith("2026-10-31"))

    def test_document_upload_response_fields(self):
        """DocumentUploadResponse includes all frontend-required fields."""
        resp = DocumentUploadResponse(
            id="doc_up_202",
            document_id="doc_up_202",
            name="Security Standards.pdf",
            document_name="Security Standards.pdf",
            format="pdf",
            sizeBytes=4096,
            pageCount=3,
            chunkCount=8,
            access_scope="confidential",
            accessScope="confidential",
            is_employee_accessible=False,
            isEmployeeAccessible=False,
            uploadedAt="2026-10-31T08:15:00",
            version="2.0",
        )
        r_dict = resp.model_dump()
        self.assertEqual(r_dict["id"], "doc_up_202")
        self.assertEqual(r_dict["status"], "ready")
        self.assertEqual(r_dict["accessScope"], "confidential")
        self.assertFalse(r_dict["isEmployeeAccessible"])
        self.assertEqual(r_dict["uploadedAt"], "2026-10-31T08:15:00")

    def test_knowledge_vault_ingest_and_retrieve_persistence(self):
        """Uploaded document is immediately persisted in database and returned in list_documents."""
        vault = KnowledgeVault.get_instance()
        test_content = (
            "# Travel Expenses Policy\n\n"
            "Section 1: Domestic hotel rate allowance is strictly $180 per night.\n"
            "Section 2: Rental car insurance must be pre-approved.\n"
        ).encode("utf-8")

        res = vault.ingest_file(
            file_bytes=test_content,
            filename="Persistent_Test_Policy.md",
            workspace_id="default",
            document_name="Persistent Test Policy",
            access_scope="public",
        )
        doc_id = res["id"]
        self.assertTrue(doc_id.startswith("doc_"))

        # Retrieve document from database
        listed = vault.list_documents(workspace_id="default", user_scope="public")
        matched = [d for d in listed if d["id"] == doc_id or d.get("name") == "Persistent Test Policy.md" or d.get("name") == "Persistent_Test_Policy.md"]
        self.assertTrue(len(matched) >= 1, "Uploaded document must persist in list_documents")

        # Cleanup test document
        with vault._get_connection() as conn:
            conn.execute("DELETE FROM vault_documents WHERE id = ?", (doc_id,))
            conn.execute("DELETE FROM vault_chunks WHERE document_id = ?", (doc_id,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
