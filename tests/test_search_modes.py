import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import yaml

from src.compare_search_modes import prepare, summarize
from src.prompts import build_messages, format_messages
from src.run_llm import _call_openai


class SearchModeTests(unittest.TestCase):
    def test_required_setting_reaches_api_and_no_web_is_unchanged(self):
        with patch("src.run_llm.OpenAI") as client, patch("src.run_llm.get_api_key", return_value="test"):
            _call_openai({"openai_web_search_tool_choice": "required"}, "test-model", [], True)
            kwargs = client.return_value.responses.create.call_args.kwargs
            self.assertEqual(kwargs["tool_choice"], "required")
            self.assertEqual(kwargs["tools"], [{"type": "web_search"}])
            _call_openai({}, "test-model", [], True)
            self.assertEqual(client.return_value.responses.create.call_args.kwargs["tool_choice"], "auto")
            client.return_value.responses.create.reset_mock()
            _call_openai({}, "test-model", [], False)
            client.return_value.responses.create.assert_not_called()
            client.return_value.chat.completions.create.assert_called_once()

    def test_invalid_setting_fails_before_client_creation(self):
        with patch("src.run_llm.OpenAI") as client, self.assertRaises(ValueError):
            _call_openai({"openai_web_search_tool_choice": "invalid"}, "test", [], True)
        client.assert_not_called()

    def setup_source(self, path):
        source = path / "source"
        source.mkdir()
        rows = []
        for query_id in (18, 22):
            query = f"Can you find the dataset titled Study {query_id}?"
            rows.append({"query_id": query_id, "query_variant": "V3_TITLE_ONLY", "query_text": query,
                         "full_prompt_web_search": format_messages(build_messages(query, 10, "WEB_SEARCH", False))})
        pd.DataFrame(rows).to_csv(source / "queries.csv", sep=";", index=False)
        cfg = {"input_path": str(source / "queries.csv"), "qrels_input_path": str(source / "queries.csv"),
               "top_k_return": 10, "models_web": ["test-model"], "query_variants": ["V3_TITLE_ONLY"]}
        return source, cfg

    def test_preparation_preserves_pairs_and_alternates_order_without_api(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            source, cfg = self.setup_source(path)
            with patch("src.compare_search_modes.resolve_config", return_value=cfg), patch("src.run_llm.OpenAI", side_effect=AssertionError("API call")):
                manifest = prepare(source, [18, 22], 2, "test-model", path / "comparison")
            self.assertEqual([row["condition"] for row in manifest["runs"]], ["auto", "required", "required", "auto"])
            first = path / "comparison/repeat_01_auto"
            second = path / "comparison/repeat_01_required"
            self.assertEqual((first / "queries.csv").read_bytes(), (second / "queries.csv").read_bytes())
            settings = [yaml.safe_load((d / "resolved_config.yaml").read_text()) for d in (first, second)]
            for value in settings:
                value.pop("output_dir")
                value.pop("openai_web_search_tool_choice")
            self.assertEqual(settings[0], settings[1])

    def test_required_only_prepares_no_auto_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            source, cfg = self.setup_source(path)
            with patch("src.compare_search_modes.resolve_config", return_value=cfg):
                manifest = prepare(source, [18, 22], 1, "test-model", path / "comparison", ["required"])
            self.assertEqual([run["condition"] for run in manifest["runs"]], ["required"])
            self.assertFalse((path / "comparison/repeat_01_auto").exists())

    def test_summary_distinguishes_search_empty_and_api_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            source, cfg = self.setup_source(path)
            destination = path / "comparison"
            with patch("src.compare_search_modes.resolve_config", return_value=cfg):
                manifest = prepare(source, [18, 22], 1, "test-model", destination)
            search = {"type": "web_search_call", "status": "completed", "action": {"type": "search"}}
            for run in manifest["runs"]:
                directory = destination / run["directory"]
                (directory / "logs").mkdir()
                metrics = []
                for query_id in (18, 22):
                    succeeds = (run["condition"] == "auto" and query_id == 22) or (run["condition"] == "required" and query_id == 18)
                    response = {"object": "response", "model": "test-snapshot", "output": [search] if succeeds else []}
                    content = {"items": [{"title": "Study", "url_or_doi": "https://example.org"}]} if succeeds else {"items": []}
                    response["output"].append({"type": "message", "content": [{"type": "output_text", "text": json.dumps(content)}]})
                    if run["condition"] == "required" and query_id == 22:
                        response = {"error": "API error"}
                    else:
                        metrics.append({"query_id": query_id, "strict_source_hit_at_k": int(succeeds)})
                    record = {"attempts": [{"response": response}]}
                    (directory / "logs" / f"query_{query_id}_WEB_SEARCH_test-model.json").write_text(json.dumps(record))
                pd.DataFrame(metrics).to_csv(directory / "metrics_per_query.csv", sep=";", index=False)
            summary = summarize(destination).set_index("condition")
            self.assertEqual(summary.loc["auto", "requests"], 2)
            self.assertEqual(summary.loc["auto", "empty_answers"], 1)
            self.assertEqual(summary.loc["required", "api_errors"], 1)
            self.assertEqual(summary.loc["required", "requests_with_search"], 1)
            self.assertEqual(summary.loc["required", "strict_source_hits"], 1)


if __name__ == "__main__":
    unittest.main()
