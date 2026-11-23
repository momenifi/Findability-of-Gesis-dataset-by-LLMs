import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import run_openai_required
from src import web_worker


class ReviewRegressionTests(unittest.TestCase):
    def test_required_run_hint_accepts_directory_outside_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "manifest.json").write_text(json.dumps({"planned_requests": 3, "runs": []}))
            output = io.StringIO()
            with patch("sys.argv", ["required", "--run-dir", str(path)]), contextlib.redirect_stdout(output):
                run_openai_required.main()
            self.assertIn(str(path.resolve()), output.getvalue())
            self.assertIn("--execute", output.getvalue())

    def test_worker_stop_is_not_marked_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            process = Mock()
            process.poll.side_effect = [None, 1]
            process.wait.return_value = 1

            def start(*args, **kwargs):
                (path / "stop.request").touch()
                return process

            with patch("sys.argv", ["worker", "--run-dir", str(path), "--stages", "generate_queries", "run_llm"]), \
                    patch("src.web_worker.managed_run", return_value=path), \
                    patch("src.web_worker.subprocess.Popen", side_effect=start) as popen, \
                    patch("src.web_worker.terminate") as terminate:
                web_worker.main()
            state = json.loads((path / "web_job.json").read_text())
            self.assertEqual(state["state"], "stopped")
            terminate.assert_called_once_with(process)
            self.assertEqual(popen.call_count, 1)
            self.assertEqual(json.loads((path / "stages.jsonl").read_text())["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
