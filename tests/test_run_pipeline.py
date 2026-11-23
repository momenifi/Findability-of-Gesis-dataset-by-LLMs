import unittest
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

import yaml

from src.run_pipeline import ROOT, read_yaml, resolve_config
from src.run_pipeline import main


class ResolveConfigTests(unittest.TestCase):
    def setUp(self):
        self.catalog = read_yaml(ROOT / "experiment.yaml")
        self.args = Namespace(provider="gemini", sample="random100", template="title_download",
                              variant="V3", model=None, mode="WEB_SEARCH", input_path=None,
                              qrels_input_path=None, limit=None)

    def test_download_matches_existing_experiment(self):
        cfg = resolve_config(self.catalog, self.args)
        old = read_yaml(ROOT / "config_random100_v3_download_gemini.yaml")
        for key in ("title_query_template", "models_web", "modes", "provider", "api_base_url",
                    "api_key_env", "source_row_limit", "include_top_k_limit_in_prompt",
                    "max_returned_items_to_save", "query_variants"):
            self.assertEqual(cfg[key], old[key], key)

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

    def test_missing_input_settings_have_clear_errors(self):
        for key in ("input_path", "qrels_input_path"):
            with self.subTest(key=key):
                catalog = deepcopy(self.catalog)
                catalog["defaults"].pop(key, None)
                catalog["datasets"]["random100"].pop(key, None)
                with self.assertRaisesRegex(ValueError, f"Missing required setting: {key}"):
                    resolve_config(catalog, self.args)

    def test_unreadable_input_fails_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            catalog = deepcopy(self.catalog)
            catalog["datasets"]["random100"]["input_path"] = str(directory / "absent.csv")
            config = directory / "catalog.yaml"
            config.write_text(yaml.safe_dump(catalog), encoding="utf-8")
            output = directory / "results"
            argv = ["pipeline", "--config", str(config), "--provider", "openai", "-V", "V3",
                    "--output-root", str(output)]
            with patch("sys.argv", argv), patch("src.run_pipeline.subprocess.run") as run:
                with self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(output.exists())
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
