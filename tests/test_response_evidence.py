import unittest

import pandas as pd

from src.match_and_eval import match_items, compute_metrics
from src.response_evidence import response_evidence


class EvidenceTests(unittest.TestCase):
    def test_mention_in_failed_search_is_not_attribution(self):
        evidence = response_evidence(
            "No verified dataset download link or database record could be found for this exact title. "
            "Searches including ICPSR and GESIS did not identify a matching dataset.", None)
        self.assertEqual(evidence["mentions_gesis"], 1)
        self.assertEqual(evidence["claims_gesis_provider"], 0)
        self.assertEqual(evidence["reports_not_found_without_link"], 1)

    def test_catalogue_is_separate_from_provider(self):
        evidence = response_evidence(
            "This dataset is listed in the CESSDA Data Catalogue and is provided by the GESIS Data Archive.",
            "https://datacatalogue.cessda.eu/detail?id=example")
        self.assertEqual(evidence["claims_gesis_provider"], 1)
        self.assertEqual(evidence["claimed_catalogues"], '["CESSDA"]')
        self.assertNotIn("CESSDA", evidence["claimed_data_providers"])
        self.assertEqual(evidence["returned_link_repository"], "CESSDA")

    def test_negative_availability_is_not_provider_claim(self):
        evidence = response_evidence("This dataset is not deposited or available in any repository such as GESIS.", "")
        self.assertEqual(evidence["claims_gesis_provider"], 0)
        self.assertEqual(evidence["reports_not_found_without_link"], 1)

    def test_alternative_with_link_survives_negative_source_statement(self):
        evidence = response_evidence(
            "No dataset with the exact title exists. This alternative is available from GESIS.",
            "https://doi.org/10.4232/1.1234")
        self.assertEqual(evidence["reports_not_found_without_link"], 0)
        self.assertEqual(evidence["claims_gesis_provider"], 1)

    def test_unknown_and_spoofed_domains_are_not_verified(self):
        self.assertEqual(response_evidence("", "https://gesis.org.example.com/x")["returned_link_repository"], "")
        self.assertEqual(response_evidence("", "https://doi.org/10.1234/x")["returned_link_repository"], "")

    def test_shared_metrics_exclude_failure_for_every_variant(self):
        corpus = pd.DataFrame([{"id": "ZA0529", "title": "Political Socialization in Pre-School Age",
                                "doi": '["10.4232/1.0529"]', "portal_url": "https://example.org/ZA0529"}])
        for variant in ("V1", "V2", "V3", "V6"):
            with self.subTest(variant=variant):
                items = pd.DataFrame([{
                    "query_id": 1, "query_variant": variant, "mode": "WEB_SEARCH", "model": "test",
                    "rank": 1, "returned_title": corpus.iloc[0]["title"], "returned_url_or_doi": float("nan"),
                    "justification": "No dataset could be found across repositories including GESIS.",
                }])
                matched, _, _ = match_items(items, corpus)
                self.assertEqual(matched.iloc[0]["title_match_score"], 1)
                per_item, summary, metrics = compute_metrics(matched, {1: ["ZA0529"]}, 10, {1: "ZA0529"})
                self.assertEqual(per_item.iloc[0]["is_title_source_dataset"], 0)
                self.assertEqual(metrics.iloc[0]["hit_at_k"], 0)
                self.assertEqual(summary.iloc[0]["title_source_hit_at_k"], 0)

    def test_matching_doi_preserves_strict_credit(self):
        corpus = pd.DataFrame([{"id": "ZA0529", "title": "Study", "doi": '["10.4232/1.0529"]', "portal_url": ""}])
        items = pd.DataFrame([{"query_id": 1, "query_variant": "V3", "mode": "WEB_SEARCH", "model": "test",
                               "rank": 1, "returned_title": "Study", "returned_url_or_doi": "https://doi.org/10.4232/1.0529",
                               "justification": "This dataset is available from GESIS."}])
        matched, _, _ = match_items(items, corpus)
        per_item, _, metrics = compute_metrics(matched, {1: ["ZA0529"]}, 10, {1: "ZA0529"})
        self.assertEqual(per_item.iloc[0]["is_strict_source_dataset"], 1)
        self.assertEqual(metrics.iloc[0]["strict_source_hit_at_k"], 1)

    def test_failure_item_does_not_suppress_successful_alternative(self):
        corpus = pd.DataFrame([
            {"id": "ZA0529", "title": "Source", "doi": '["10.4232/1.0529"]', "portal_url": ""},
            {"id": "ZA0001", "title": "Alternative", "doi": '["10.4232/1.0001"]', "portal_url": ""},
        ])
        base = {"query_id": 1, "query_variant": "V1", "mode": "WEB_SEARCH", "model": "test"}
        items = pd.DataFrame([
            {**base, "rank": 1, "returned_title": "Source", "returned_url_or_doi": "",
             "justification": "No dataset could be found."},
            {**base, "rank": 2, "returned_title": "Alternative", "returned_url_or_doi": "https://doi.org/10.4232/1.0001",
             "justification": "This alternative is available from GESIS."},
        ])
        matched, _, _ = match_items(items, corpus)
        _, _, metrics = compute_metrics(matched, {1: ["ZA0529", "ZA0001"]}, 10, {1: "ZA0529"})
        self.assertEqual(metrics.iloc[0]["source_hit_at_k"], 0)
        self.assertEqual(metrics.iloc[0]["strict_gesis_relevant_hit_at_k"], 1)
        self.assertEqual(metrics.iloc[0]["strict_mrr"], 0.5)


if __name__ == "__main__":
    unittest.main()
