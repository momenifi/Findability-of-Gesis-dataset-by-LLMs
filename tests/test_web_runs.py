from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.web_runs import prepare_config, preview_queries, store_upload, managed_run, job_status


class WebRunTests(unittest.TestCase):
    def test_edited_metadata_template_reaches_actual_generator(self):
        cfg = prepare_config("gemini", "random100", "V1", "default", "test", 5,
                             query_template="Find data on {topic}, place {country}, period {time_collection_years}.")
        preview, rows, uncached = preview_queries(cfg)
        self.assertEqual(rows, 5)
        self.assertEqual(len(preview), 4)
        self.assertEqual(uncached, 0)
        self.assertTrue(preview.iloc[0].query_text.startswith("Find data on Political"))
        self.assertIn("SYSTEM: Use web search", preview.iloc[0].full_prompt)
        self.assertNotIn("Return up to", preview.iloc[0].full_prompt)

    def test_template_rejects_attribute_access_and_missing_fields(self):
        for template in ("{title.__class__}", "Find this", "{other}"):
            with self.subTest(template=template), self.assertRaises(ValueError):
                prepare_config("gemini", "random100", "V3", "title_original", "test", 5,
                               query_template=template)

    def test_uncached_v6_preview_does_not_call_model(self):
        cfg = prepare_config("gemini", "random100", "V6", "default", "test", 5)
        cfg["abstract_query_cache_path"] = "does-not-exist.csv"
        with patch("src.generate_queries._generate_abstract_query", side_effect=AssertionError("No API calls")):
            preview, rows, uncached = preview_queries(cfg)
        self.assertEqual(rows, 5)
        self.assertTrue(preview.empty)
        self.assertGreater(uncached, 0)

    def test_upload_uses_content_hash_and_ignores_filename_paths(self):
        with tempfile.TemporaryDirectory() as directory, patch("src.web_runs.UPLOAD_ROOT", Path(directory)):
            path = store_upload("../../outside.csv", b"id,title\nZA1,Study")
            again = store_upload("another.csv", b"id,title\nZA1,Study")
            self.assertEqual(path, again)
            self.assertEqual(path.parent, Path(directory))

    def test_outside_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            managed_run(directory)

    def test_dead_worker_marked_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "web_job.json").write_text('{"state":"running","pid":123}')
            with patch("src.web_runs.process_alive", return_value=False):
                self.assertEqual(job_status(path)["state"], "interrupted")


if __name__ == "__main__":
    unittest.main()
