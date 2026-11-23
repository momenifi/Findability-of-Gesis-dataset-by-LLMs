import unittest

from scripts.audit_openai_search_usage import search_evidence


class SearchUsageAuditTests(unittest.TestCase):
    def test_page_open_is_not_a_search(self):
        result = search_evidence({"output": [{"type": "web_search_call", "action": {"type": "open_page"}}]})
        self.assertEqual(result["search_used"], 0)
        self.assertEqual(result["open_page_actions"], 1)

    def test_final_and_earlier_attempts_are_distinguished(self):
        response = {"output": [{"type": "web_search_call", "status": "completed", "action": {"type": "search"}}]}
        result = search_evidence({"attempts": [{"response": response}, {"response": {"output": []}}]})
        self.assertEqual(result["search_used"], 0)
        self.assertEqual(result["search_used_any_attempt"], 1)
        completed = search_evidence(response)
        self.assertEqual(completed["completed_search_actions"], 1)


if __name__ == "__main__":
    unittest.main()
