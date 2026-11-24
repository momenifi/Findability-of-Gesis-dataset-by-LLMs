import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from src.match_and_eval import (_extract_dataset_id, _sdn_doi_from_id, _query_source_identifier_aliases,
                                match_items, compute_metrics, match_and_eval)


class SdnIdentifierTests(unittest.TestCase):
    def test_extracts_canonical_id_with_url_parameters(self):
        self.assertEqual(_extract_dataset_id("https://search.gesis.org/research_data/sdn-10.7802-2388?lang=de"),
                         "SDN-10.7802-2388")
        self.assertEqual(_extract_dataset_id("https://example.org/ZA0840"), "ZA0840")
        self.assertEqual(_extract_dataset_id("SDN-10.7802-2388-invalid"), "")
        self.assertEqual(_sdn_doi_from_id("SDN-10.7802-2388"), "10.7802/2388")
        self.assertEqual(_sdn_doi_from_id("ZA2388"), "")

    def test_known_sdn_doi_and_url_are_strict_matches_without_title(self):
        source = "SDN-10.7802-2388"
        corpus = pd.DataFrame([{"id": source, "title": "Study", "doi": "", "portal_url": ""}])
        for link in ("https://doi.org/10.7802/2388", "https://search.gesis.org/research_data/SDN-10.7802-2388?lang=de"):
            with self.subTest(link=link):
                raw = pd.DataFrame([{"query_id": 1, "query_variant": "V3", "mode": "WEB_SEARCH", "model": "test",
                                     "rank": 1, "returned_title": "", "returned_url_or_doi": link}])
                matched, _, _ = match_items(raw, corpus)
                self.assertEqual(matched.iloc[0].matched_dataset_id, source)
                self.assertEqual(matched.iloc[0].is_identifier_match, 1)
                _, _, metrics = compute_metrics(matched, {1: [source]}, 10, {1: source})
                self.assertEqual(metrics.iloc[0].strict_source_hit_at_k, 1)

    def test_wrong_sdn_identifier_does_not_promote_matching_title(self):
        corpus = pd.DataFrame([{"id": "SDN-10.7802-2388", "title": "Study", "doi": "", "portal_url": ""}])
        matched, _, _ = match_items(pd.DataFrame([{"returned_title": "Study",
                                                 "returned_url_or_doi": "https://doi.org/10.7802/9999"}]), corpus)
        self.assertEqual(matched.iloc[0].is_identifier_match, 0)
        self.assertFalse(matched.iloc[0].link_valid)

    def test_query_aliases_include_canonical_sdn_doi(self):
        queries = pd.DataFrame([{"source_dataset_id": "SDN-10.7802-2388", "source_doi": ""}])
        dois, _, ids = _query_source_identifier_aliases(queries)
        self.assertEqual(dois["10.7802/2388"], "SDN-10.7802-2388")
        self.assertEqual(ids["SDN-10.7802-2388"], "SDN-10.7802-2388")

    def test_identifier_for_another_record_overrides_matching_source_title(self):
        source = "SDN-10.7802-2388"
        other = "SDN-10.7802-9999"
        corpus = pd.DataFrame([{"id": source, "title": "Source study", "doi": "", "portal_url": ""},
                               {"id": other, "title": "Different study", "doi": "", "portal_url": ""}])
        raw = pd.DataFrame([{"query_id": 1, "query_variant": "V3", "mode": "WEB_SEARCH", "model": "test",
                             "rank": 1, "returned_title": "Source study", "returned_url_or_doi": "https://doi.org/10.7802/9999"}])
        matched, _, _ = match_items(raw, corpus)
        self.assertEqual(matched.iloc[0].matched_dataset_id, other)
        self.assertEqual(matched.iloc[0].title_identifier_conflict, 1)
        _, _, metrics = compute_metrics(matched, {1: [source]}, 10, {1: source})
        self.assertEqual(metrics.iloc[0].strict_source_hit_at_k, 0)
        self.assertEqual(metrics.iloc[0].source_hit_at_k, 0)

    def test_matching_only_refresh_preserves_qrels_and_input_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = "SDN-10.7802-2388"
            metadata = pd.DataFrame([{"id": source, "title": "Study", "doi": "", "portal_url": ""}])
            pd.DataFrame([{"query_id": 1, "source_dataset_id": source}]).to_csv(directory / "queries.csv", sep=";", index=False)
            pd.DataFrame([{"query_id": 1, "query_variant": "V3_TITLE_ONLY", "mode": "WEB_SEARCH", "model": "test",
                           "rank": 1, "returned_title": "Study", "returned_url_or_doi": "https://doi.org/10.7802/2388"}]
                         ).to_csv(directory / "llm_results.csv", sep=";", index=False)
            pd.DataFrame([{"query_id": 1, "relevant_dataset_id": source}]).to_csv(directory / "qrels.csv", sep=";", index=False)
            config = directory / "config.yaml"
            config.write_text(yaml.safe_dump({"output_dir": str(directory), "input_path": "unused",
                                              "qrels_strategy": "metadata_filter"}))
            before = {name: (directory / name).read_bytes() for name in ("qrels.csv", "queries.csv", "llm_results.csv")}
            with patch("src.match_and_eval.load_metadata", side_effect=AssertionError("Already loaded")):
                match_and_eval(str(config), metadata=metadata, reuse_qrels=True)
            metrics = pd.read_csv(directory / "metrics_per_query.csv", sep=";")
            self.assertEqual(metrics.iloc[0].strict_source_hit_at_k, 1)
            for name, content in before.items():
                self.assertEqual((directory / name).read_bytes(), content)
