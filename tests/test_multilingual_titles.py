import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.load_metadata import load_metadata
from src.match_and_eval import match_items, compute_metrics


class MultilingualTitleTests(unittest.TestCase):
    def load_fixture(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            return load_metadata(str(path), "csv")

    def test_original_title_preserved_without_study_title(self):
        corpus = self.load_fixture([{
            "id": "ZA0529", "title": "Politische Sozialisation im Vorschulalter",
            "title_en": "Political Socialization in Pre-School Age",
            "doi": '["10.4232/1.0529"]',
        }])
        self.assertEqual(corpus.iloc[0]["title"], "Political Socialization in Pre-School Age")
        self.assertEqual(corpus.iloc[0]["title_original"], "Politische Sozialisation im Vorschulalter")
        for title, link in (
            ("Politische Sozialisation im Vorschulalter", ""),
            ("Political Socialization in Pre-School Age", ""),
            ("Politische Sozialisation im Vorschulalter (GESIS ZA0529)", "https://doi.org/10.4232/1.0529"),
        ):
            with self.subTest(title=title):
                items = pd.DataFrame([{
                    "query_id": 1, "query_variant": "V6", "mode": "WEB_SEARCH", "model": "test",
                    "rank": 1, "returned_title": title, "returned_url_or_doi": link,
                    "justification": "Available from GESIS.",
                }])
                matched, _, _ = match_items(items, corpus)
                self.assertEqual(matched.iloc[0]["title_matched_dataset_id"], "ZA0529")
                _, _, metrics = compute_metrics(matched, {1: ["ZA0529"]}, 10, {1: "ZA0529"})
                self.assertEqual(metrics.iloc[0]["title_source_hit_at_k"], 1)
                self.assertEqual(metrics.iloc[0]["strict_source_hit_at_k"], int(bool(link)))

    def test_study_and_alternative_title_fields_survive_loading(self):
        row = {
            "id": "ZA0590", "title": "English primary title", "title_en": "English primary title",
            "study_title": "Politische Situation in West-Berlin (Jugendliche aus der DDR)",
            "study_title_en": "English study title", "other_titles": '["Anderer Titel"]',
            "other_titles_en": '["Alternative title"]',
        }
        corpus = self.load_fixture([row])
        for column in ("study_title", "study_title_en", "other_titles", "other_titles_en"):
            self.assertEqual(corpus.iloc[0][column], row[column])
        items = pd.DataFrame([{"returned_title": row["study_title"], "returned_url_or_doi": ""}])
        matched, _, _ = match_items(items, corpus)
        self.assertEqual(matched.iloc[0]["title_match_method"], "title_exact")
        self.assertEqual(matched.iloc[0]["title_match_column"], "study_title")


if __name__ == "__main__":
    unittest.main()
