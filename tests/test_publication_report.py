import unittest
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts.build_publication_report import ROOT, interpretation, check_publication, sample_readme, source_root


class PublicationReportTests(unittest.TestCase):
    def test_sources_mirror_the_provider_sample_report_layout(self):
        for provider in ("OpenAI", "Gemini"):
            for sample in ("random100", "top10"):
                self.assertEqual(source_root(sample, provider),
                                 ROOT / "output/current_results_sources" / provider.lower() / sample)

    def test_provider_sample_page_contains_strict_and_broad_counts(self):
        row = {"variant": "V3", "requests": 100, "empty_responses": 12, "api_errors": 0}
        for label, count in (("strict_source", 63), ("source", 82), ("strict_gesis", 63), ("gesis", 82)):
            row[label + "_hits"] = count
            row[label + "_rate"] = count / 100
        text = sample_readme("OpenAI", "random100", [row])
        self.assertIn("OpenAI: 100 Random Datasets", text)
        self.assertIn("63/100 (63.0%)", text)
        self.assertIn("82/100 (82.0%)", text)
        self.assertIn("returned_items.csv", text)
        self.assertNotIn("Strict Source Hits", text)
        self.assertIn("dataset discovery rate", text)

    def test_tables_use_all_requests_not_only_responses_with_items(self):
        row = {"sample": "random100", "variant": "V3", "provider": "OpenAI", "requests": 100,
               "strict_source_hits": 56, "strict_source_rate": .56, "strict_gesis_hits": 56,
               "strict_gesis_rate": .56, "empty_responses": 12, "api_errors": 0,
               "execution_dates_utc": "2026-11-23"}
        text = interpretation([row])
        self.assertIn("56/100 (56.0%)", text)
        self.assertNotIn("56/88", text)
        self.assertTrue(text.startswith("# Dataset Discovery with OpenAI and Gemini\n\nThis study investigates"))
        self.assertIn("## Study Setup", text)
        self.assertIn("## Models and API Access", text)
        self.assertIn("`chat-latest`", text)
        self.assertIn("`gemini-3.6-flash`", text)
        self.assertIn("Execution date", text)
        self.assertIn("2026-11-23", text)
        self.assertIn("Not recorded", text)
        self.assertIn("does not explicitly transmit these sampling parameters", text)
        self.assertIn("Model Used to Construct Abstract Queries", text)
        setup = text.split("## Study Setup", 1)[1].split("## What Counts as Found?", 1)[0]
        self.assertNotIn("V2", setup)
        self.assertIn("## What Counts as Found?", text)
        self.assertIn("## Rationale for the Query Designs", text)
        self.assertIn("Known-title baseline (V3)", text)
        self.assertIn("Metadata-based discovery (V1 and V2)", text)
        self.assertIn("Natural-language research need (V6)", text)
        self.assertIn("cannot be attributed to natural wording", text)
        self.assertNotIn("rerun", text.casefold())
        self.assertIn("equivalent web-search conditions", text)
        self.assertIn("top-10 evaluation depth", text)
        self.assertNotIn("Strict Source Hits", text)
        self.assertIn("dataset discovery rate", text)
        self.assertIn("Original dataset found", text)

    def test_researcher_date_is_not_presented_as_a_logged_utc_timestamp(self):
        text = interpretation([{"provider": "Gemini", "sample": "random100", "variant": "unknown",
                                "reported_execution_date": "2026-09-23"}])
        self.assertIn("2026-09-23 (researcher-reported)", text)
        self.assertIn("timezone was not", text)

    def test_consistency_check_detects_changed_sources_and_edited_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "report"
            report.mkdir()
            (root / "source.csv").write_text("original")
            provenance = {"files": [{"path": "source.csv", "sha256": hashlib.sha256(b"original").hexdigest()}],
                          "evaluation_code_sha256": {}, "openai_run": "run"}
            encoded = json.dumps(provenance)
            (report / "provenance.json").write_text(encoded)
            (report / "summary.csv").write_text("generated")
            (report / "INTERPRETATION.md").write_text("interpretation")

            def rebuild(run, destination):
                (destination / "provenance.json").write_text(encoded)
                (destination / "summary.csv").write_text("generated")
                return []

            with patch("scripts.build_publication_report.ROOT", root), \
                    patch("scripts.build_publication_report.build", side_effect=rebuild), \
                    patch("scripts.build_publication_report.interpretation", return_value="interpretation"):
                self.assertEqual(check_publication(report), [])
                (report / "summary.csv").write_text("manual edit")
                self.assertTrue(any("Stale or edited export" in issue for issue in check_publication(report)))
                self.assertEqual((report / "summary.csv").read_text(), "manual edit")
                (root / "source.csv").write_text("changed")
                self.assertTrue(any("Changed or missing source" in issue for issue in check_publication(report)))
