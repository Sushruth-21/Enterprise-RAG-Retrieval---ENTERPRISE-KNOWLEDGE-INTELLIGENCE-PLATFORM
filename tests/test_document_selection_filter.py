import unittest
import os
import sys

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.schemas import DocumentPassage, VerificationResult
from app.storage.vault import KnowledgeVault
from app.orchestrator.graph import build_citations, classify_status


class TestDocumentSelectionFilter(unittest.TestCase):
    def setUp(self):
        self.passages = [
            DocumentPassage(
                chunk_id="chunk_doc_a_1",
                document_id="doc_A",
                document_name="Travel Policy",
                section="Section 3.1 - Per Diem Rates",
                page=4,
                content="Daily meal per diem allowance is capped at $75 per day for domestic travel.",
                score=0.92,
                is_current=True,
            ),
            DocumentPassage(
                chunk_id="chunk_doc_b_1",
                document_id="doc_B",
                document_name="IT Security Policy",
                section="Section 1.4 - Smart Cards",
                page=2,
                content="Employees must wear RFID access badges visibly at all times within facilities.",
                score=0.88,
                is_current=True,
            ),
        ]

    def test_citations_filter_to_single_selected_document(self):
        """When doc_A is selected and doc_B is deselected, only doc_A citations are returned."""
        state = {
            "all_passages": self.passages,
            "document_ids": ["doc_A"],
            "answer": "The daily meal allowance is $75 [1].",
            "has_restricted_matches": False,
            "status": "answered",
        }
        res = build_citations(state)
        citations = res["citations"]
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].document_id, "doc_A")
        self.assertEqual(citations[0].document_name, "Travel Policy")

    def test_deselected_document_excluded_from_citations(self):
        """When doc_A is deselected and doc_B is selected, doc_A is NEVER cited."""
        state = {
            "all_passages": self.passages,
            "document_ids": ["doc_B"],
            "answer": "Smart badges must be worn [1].",
            "has_restricted_matches": False,
            "status": "answered",
        }
        res = build_citations(state)
        citations = res["citations"]
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].document_id, "doc_B")
        self.assertEqual(citations[0].document_name, "IT Security Policy")
        self.assertNotIn("doc_A", [c.document_id for c in citations])

    def test_empty_document_selection_yields_zero_citations(self):
        """When document_ids is an empty list ([]), zero citations are generated."""
        state = {
            "all_passages": self.passages,
            "document_ids": [],
            "answer": "No documents are currently selected.",
            "has_restricted_matches": False,
            "status": "not_covered",
        }
        res = build_citations(state)
        self.assertEqual(len(res["citations"]), 0)

    def test_vault_search_chunks_with_empty_doc_ids(self):
        """KnowledgeVault.search_chunks(doc_ids=[]) immediately returns empty list."""
        vault = KnowledgeVault.get_instance()
        chunks = vault.search_chunks(query="per diem travel allowance", doc_ids=[])
        self.assertEqual(chunks, [])

    def test_classify_status_for_empty_selection(self):
        """Status classifier marks unselected documents query as not_covered and 0.0 confidence."""
        state = {
            "answer": "No documents are currently selected. Please select one or more documents from the checklist.",
            "has_restricted_matches": False,
            "all_passages": [],
            "verification": VerificationResult(verified=True, unsupported_claims=[]),
        }
        res = classify_status(state)
        self.assertEqual(res["status"], "not_covered")
        self.assertEqual(res["confidence_score"], 0.0)


if __name__ == "__main__":
    unittest.main()

