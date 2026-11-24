import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.validate_title_only_links import PageEvidence, classify, load_title_aliases


class LinkValidationTests(unittest.TestCase):
    def test_cached_aliases_need_only_the_current_source_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "output/current_results_sources/_support/title_aliases.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"ZA1": ["German title", "English title"]}))
            with patch("scripts.validate_title_only_links.ROOT", root), \
                    patch("scripts.validate_title_only_links.pd.read_csv", side_effect=AssertionError("No external data inputs")):
                self.assertEqual(load_title_aliases()["ZA1"], {"German title", "English title"})

    def page(self, **values):
        return {"http_status": 200, "error": "", "content_type": "text/html", "metadata": {},
                "final_url": "https://example.org/record/123", "page_title": "Other", "page_h1": "", **values}

    def test_status_and_generic_pages_do_not_confirm_identity(self):
        for page, expected in (
            (self.page(http_status=403), "inconclusive_blocked"),
            (self.page(http_status=404), "not_found_at_check_time"),
            (self.page(final_url="https://search.gesis.org/"), "generic_page_not_dataset_record"),
            (self.page(content_type="application/pdf"), "document_or_non_html_identity_unverified")):
            self.assertEqual(classify(page, "ZA1", {"Source"}, ""), expected)

    def test_title_only_and_body_mentions_are_not_verified_identifiers(self):
        self.assertEqual(classify(self.page(page_title="Source"), "ZA1", {"Source"}, ""),
                         "source_title_supported_identity_or_version_unverified")
        self.assertEqual(classify(self.page(body_identity_terms=["ZA1"]), "ZA1", {"Source"}, ""),
                         "source_mentioned_record_identity_unverified")

    def test_primary_metadata_identifier_can_support_source(self):
        self.assertEqual(classify(self.page(metadata={"citation_doi": ["10.1234/data"]}),
                                  "ZA1", {"Source"}, '["10.1234/data"]'),
                         "source_identifier_supported_by_destination")

    def test_parser_ignores_script_mentions_and_reads_metadata(self):
        parser = PageEvidence()
        parser.feed('<title>Source</title><script>ZA9999</script><meta name="citation_doi" content="10.1234/data">')
        self.assertEqual(parser.meta["citation_doi"], ["10.1234/data"])
        self.assertNotIn("ZA9999", " ".join(parser.parts))
