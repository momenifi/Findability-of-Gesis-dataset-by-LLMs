import contextlib
import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from scripts.diagnose_gemini_search import diagnose
from src.run_llm import _build_gemini_payload, _call_gemini


class GeminiDiagnosticTests(unittest.TestCase):
    def test_production_call_sends_shared_search_payload(self):
        messages = [{"role": "system", "content": "Search"}, {"role": "user", "content": "Find data"}]
        cfg = {"api_key_env": "GEMINI_API_KEY"}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "secret"}), patch("src.run_llm.requests.post") as post:
            post.return_value.ok = True
            _call_gemini(cfg, "test", messages, True)
        self.assertEqual(post.call_args.kwargs["json"], _build_gemini_payload(messages, True))
        self.assertEqual(post.call_args.kwargs["json"]["tools"], [{"google_search": {}}])
        self.assertNotIn("tools", _build_gemini_payload(messages, False))

    def test_preview_is_offline_and_execution_saves_actual_payload_without_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            pd.DataFrame([{"query_id": 1, "query_text": "Find study"}]).to_csv(path / "queries.csv", sep=";", index=False)
            cfg = {"models_web": ["test"], "api_key_env": "GEMINI_API_KEY"}
            output = io.StringIO()
            response = Mock(ok=True, status_code=200)
            response.json.return_value = {"candidates": [{"groundingMetadata": {"webSearchQueries": ["study"]}}]}
            with patch("scripts.diagnose_gemini_search.load_config", return_value=cfg), \
                    patch.dict("os.environ", {"GEMINI_API_KEY": "secret-test-value"}), \
                    patch("scripts.diagnose_gemini_search.requests.post", return_value=response) as post, \
                    contextlib.redirect_stdout(output):
                self.assertIsNone(diagnose(path / "config", path, [1]))
                post.assert_not_called()
                saved = diagnose(path / "config", path, [1], True, path / "diagnostics")
                self.assertEqual(post.call_count, 1)
                record = json.loads((saved / "query_1.json").read_text())
                self.assertEqual(record["request_payload"], post.call_args.kwargs["json"])
            self.assertNotIn("secret-test-value", output.getvalue())
            for file in saved.iterdir():
                self.assertNotIn("secret-test-value", file.read_text())
