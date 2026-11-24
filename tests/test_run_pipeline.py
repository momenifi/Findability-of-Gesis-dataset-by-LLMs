import unittest
from argparse import Namespace

from src.run_pipeline import ROOT, read_yaml, resolve_config


class ResolveConfigTests(unittest.TestCase):
    def setUp(self):
        self.catalog = read_yaml(ROOT / "experiment.yaml")
        self.args = Namespace(provider="gemini", sample="random100", template="title_download",
                              variant="V3", model=None, mode="WEB_SEARCH", input_path=None,
                              qrels_input_path=None, limit=None)

    def test_download_profile_settings(self):
        cfg = resolve_config(self.catalog, self.args)
        expected = {
            "title_query_template": "Where can you download the dataset titled {title}? Please give the direct link and which database the link belongs to.",
            "models_web": ["gemini-3.6-flash"], "modes": ["WEB_SEARCH"], "provider": "gemini",
            "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key_env": "GEMINI_API_KEY", "source_row_limit": 100,
            "include_top_k_limit_in_prompt": False, "max_returned_items_to_save": 0,
            "query_variants": ["V3_TITLE_ONLY"],
        }
        for key, value in expected.items():
            self.assertEqual(cfg[key], value, key)

    def test_provider_and_model_override(self):
        self.args.provider = "openai"
        self.args.model = "test-model"
        cfg = resolve_config(self.catalog, self.args)
        self.assertEqual(cfg["api_key_env"], "OPENAI_API_KEY")
        self.assertEqual(cfg["models_web"], ["test-model"])
        self.assertEqual(cfg["models_no_web"], [])

    def test_v6_cache_shared_across_providers(self):
        self.args.variant = "V6"
        self.args.template = "default"
        gemini = resolve_config(self.catalog, self.args)
        self.args.provider = "openai"
        openai = resolve_config(self.catalog, self.args)
        self.assertEqual(gemini["abstract_query_cache_path"], openai["abstract_query_cache_path"])

    def test_title_template_rejected_for_metadata_variant(self):
        self.args.variant = "V1"
        with self.assertRaises(ValueError):
            resolve_config(self.catalog, self.args)

    def test_custom_input_does_not_reuse_sample_cache(self):
        self.args.input_path = "custom.csv"
        self.args.limit = 3
        cfg = resolve_config(self.catalog, self.args)
        self.assertNotIn("abstract_query_cache_path", cfg)
        self.assertEqual(cfg["source_row_limit"], 3)


if __name__ == "__main__":
    unittest.main()
