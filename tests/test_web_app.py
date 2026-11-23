import importlib.util
import unittest
from unittest.mock import patch

from src.run_pipeline import ROOT


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Install requirements-web.txt for UI tests")
class WebAppTests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()

    def test_saved_experiment_view_renders(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Experiments")

    def test_prompt_preview_is_offline(self):
        app = self.app()
        app.radio(key="page").set_value("New experiment").run()
        next(widget for widget in app.selectbox if widget.label == "Metadata preset").set_value("V3").run()
        with patch("src.generate_queries._generate_abstract_query", side_effect=AssertionError("API call")):
            next(widget for widget in app.button if widget.label == "Preview prompts").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("5 generated queries" in widget.value for widget in app.caption))

    def test_invalid_template_cannot_start(self):
        app = self.app()
        app.radio(key="page").set_value("New experiment").run()
        app.text_area[0].set_value("Find datasets about {unknown}").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertTrue(next(widget for widget in app.button if widget.label == "Generate prompts").disabled)

    def test_metadata_fields_determine_variant_and_templates(self):
        app = self.app()
        app.radio(key="page").set_value("New experiment").run()
        app.multiselect[0].set_value(["title"]).run()
        self.assertFalse(app.exception)
        self.assertTrue(any(widget.value == "Evaluation variant: V3" for widget in app.caption))
        choices = next(widget for widget in app.selectbox if widget.label == "Prompt template")
        self.assertIn("Title download", choices.options)
        self.assertNotIn("Metadata search", choices.options)

    def test_unsupported_metadata_cannot_start(self):
        app = self.app()
        app.radio(key="page").set_value("New experiment").run()
        app.multiselect[0].set_value(["topic", "country"]).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertTrue(next(widget for widget in app.button if widget.label == "Generate prompts").disabled)

    def test_dataset_profile_can_be_inspected(self):
        app = self.app()
        app.radio(key="page").set_value("New experiment").run()
        next(widget for widget in app.selectbox if widget.label == "Dataset profile").set_value("top10").run()
        next(widget for widget in app.button if widget.label == "Inspect sample").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("out of 10" in widget.value for widget in app.caption))


if __name__ == "__main__":
    unittest.main()
