import unittest

from scripts.audit_gemini_search_usage import grounding_evidence


class GeminiSearchAuditTests(unittest.TestCase):
    def test_answer_links_are_not_search_evidence(self):
        response = {"candidates": [{"content": {"parts": [{"text": "https://gesis.org"}]}}]}
        self.assertEqual(grounding_evidence(response)["grounding_metadata_present"], 0)

    def test_queries_and_grounding_are_separate(self):
        response = {"candidates": [{"groundingMetadata": {
            "webSearchQueries": ["GESIS title"], "groundingChunks": [{"web": {"uri": "https://gesis.org"}}],
            "searchEntryPoint": {"renderedContent": "suggestions"}, "groundingSupports": [{}]}}]}
        result = grounding_evidence(response)
        self.assertEqual(result["search_queries_recorded"], 1)
        self.assertEqual(result["web_grounding_chunks"], 1)
        self.assertEqual(result["search_entry_point_present"], 1)
        self.assertEqual(grounding_evidence({"candidates": [{"groundingMetadata": {
            "groundingChunks": [{"web": {"uri": "https://gesis.org"}}]}}]})["search_queries_recorded"], 0)
