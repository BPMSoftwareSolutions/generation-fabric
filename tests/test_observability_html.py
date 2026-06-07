from __future__ import annotations

import contextlib
import io
import json
import pathlib
import re
import tempfile
import unittest

import json_schema_crud as jsc


class ObservabilityHtmlTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def _extract_playback_json(self, html: str) -> dict[str, object]:
        match = re.search(
            r'<script type="application/json" id="observability-playback-data">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "playback JSON script tag missing")
        assert match is not None
        return json.loads(match.group(1))

    def test_worker_bee_observe_with_html_writes_html_sidecar(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            markdown_path = tmp_path / "planner-observation.md"

            code, stdout, stderr = self.run_cli(
                "worker-bee-observe",
                "--source-file",
                str(source_path),
                "--output",
                str(markdown_path),
                "--with-html",
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee observability html written", stdout)

            html_path = markdown_path.with_suffix(".html")
            self.assertTrue(html_path.exists())

            html = html_path.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn('class="observability-page"', html)
            self.assertIn('class="execution-panel"', html)
            self.assertIn('class="markdown-body"', html)
            self.assertIn('id="observability-playback-data"', html)
            self.assertIn('class="diagram-shell"', html)
            self.assertIn('type="module"', html)
            self.assertIn("Execution Playback", html)

            playback = self._extract_playback_json(html)
            self.assertIn("tracks", playback)
            self.assertGreaterEqual(len(playback["tracks"]), 1)

    def test_worker_bee_observe_html_command_renders_existing_sidecars(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            markdown_path = tmp_path / "planner-observation.md"

            observe_code, observe_stdout, observe_stderr = self.run_cli(
                "worker-bee-observe",
                "--source-file",
                str(source_path),
                "--output",
                str(markdown_path),
            )
            self.assertEqual(observe_code, 0, observe_stderr)
            self.assertIn("worker-bee observation written", observe_stdout)

            html_path = tmp_path / "planner-observation.html"
            code, stdout, stderr = self.run_cli(
                "worker-bee-observe-html",
                "--markdown-file",
                str(markdown_path),
                "--data-file",
                str(tmp_path / "planner-observation.json"),
                "--schema",
                str(tmp_path / "planner-observation.schema.json"),
                "--output",
                str(html_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee observability html written", stdout)
            self.assertTrue(html_path.exists())

            html = html_path.read_text(encoding="utf-8")
            self.assertIn('class="observability-page"', html)
            self.assertIn('class="execution-panel"', html)
            self.assertIn('class="diagram-shell"', html)
            self.assertIn('id="observability-playback-data"', html)
            self.assertIn("Execution Playback", html)
            self.assertIn("sequenceDiagram", html)

            playback = self._extract_playback_json(html)
            self.assertIn("tracks", playback)
            self.assertGreaterEqual(len(playback["tracks"]), 1)


if __name__ == "__main__":
    unittest.main()
