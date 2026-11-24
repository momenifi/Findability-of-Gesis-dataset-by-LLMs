import unittest
from unittest.mock import patch

from scripts.diagnose_openwebui_required import classify
from src.run_llm import _build_openwebui_payload, _call_openwebui_chat


class OpenWebUIRequiredTests(unittest.TestCase):
    def test_required_is_sent_and_auto_is_left_to_server(self):
        cfg = {"openwebui_tool_choice": "required", "openwebui_web_search_mode": "features"}
        payload = _build_openwebui_payload(cfg, "test", [], True)
        self.assertEqual(payload["tool_choice"], "required")
        self.assertEqual(payload["features"], {"web_search": True})
        self.assertNotIn("tool_choice", _build_openwebui_payload({**cfg, "openwebui_tool_choice": "auto"}, "test", [], True))
        with patch("src.run_llm.get_api_key", return_value="test"), patch("src.run_llm.requests.post") as post:
            _call_openwebui_chat(cfg, "test", [], True)
            self.assertEqual(post.call_args.kwargs["json"], payload)

    def test_search_call_is_not_mistaken_for_executed_search(self):
        body = {"choices": [{"finish_reason": "tool_calls", "message": {
            "content": None, "tool_calls": [{"function": {"name": "search_web"}}]}}]}
        result = classify(body)
        self.assertEqual(result["outcome"], "unresolved_tool_calls")
        self.assertEqual(result["requested_tools"], ["search_web"])
        self.assertFalse(result["content_present"])
