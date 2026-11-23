import tempfile
from pathlib import Path
import unittest

import pandas as pd
import yaml

from src.generate_queries import generate_queries
from src.load_metadata import load_metadata
from src.match_and_eval import build_metadata_filter_qrels
from src.run_pipeline import ROOT, read_yaml
from src.web_runs import VARIANT_METADATA, compatible_templates, prepare_config, variant_for_metadata


class ExperimentChoiceTests(unittest.TestCase):
    def test_supported_metadata_routes_to_existing_variants(self):
        for variant, fields in VARIANT_METADATA.items():
            with self.subTest(variant=variant):
                mode = "Single topic" if variant == "V2" else "All topics"
                self.assertEqual(variant_for_metadata(fields, mode), variant)

    def test_arbitrary_subset_cannot_silently_use_extra_relevance_filters(self):
        for fields in ([], ["topic"], ["topic", "country"], ["title", "country"]):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                variant_for_metadata(fields)

    def test_named_templates_match_their_metadata(self):
        catalog = read_yaml(ROOT / "experiment.yaml")
        for variant in VARIANT_METADATA:
            for name in compatible_templates(catalog, variant):
                with self.subTest(variant=variant, name=name):
                    cfg = prepare_config("gemini", "random100", variant, name, "test", 5)
                    self.assertEqual(cfg["selected_metadata"], list(VARIANT_METADATA[variant]))

    def test_population_template_and_relevance_use_same_fields(self):
        common = {"topic_en": '["Education"]', "countries_collection_en": '["Germany"]',
                  "time_collection_years": '["1971", "1972"]', "analysis_unit_en": '["Individuals"]'}
        rows = [
            {**common, "id": "ZA0001", "title_en": "Source", "universe_en": '["Adults"]'},
            {**common, "id": "ZA0002", "title_en": "Other adults", "universe_en": '["Adults"]'},
            {**common, "id": "ZA0003", "title_en": "Children", "universe_en": '["Children"]'},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / "source.csv"
            pd.DataFrame(rows).to_csv(source, index=False)
            cfg = prepare_config("gemini", "random100", "V5", "population_search", "test", 1,
                                 input_path=str(source),
                                 query_template="Find {topic} data in {country}, {time_collection_years}, population {universe}.")
            cfg["output_dir"] = str(path / "results")
            config_path = path / "config.yaml"
            config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
            queries = generate_queries(str(config_path))
            self.assertEqual(len(queries), 1)
            self.assertIn("population Adults", queries.iloc[0].query_text)
            qrels = build_metadata_filter_qrels(load_metadata(str(source), "csv"), queries)
            self.assertEqual(set(qrels[1]), {"ZA0001", "ZA0002"})


if __name__ == "__main__":
    unittest.main()
