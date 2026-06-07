from __future__ import annotations

import contextlib
import io
import pathlib
import tempfile
import unittest

import json

import json_schema_crud as jsc
from generation_fabric.worker_bee.executor import build_worker_bee_document


class WorkerBeeExecutorTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_worker_bee_document_builds_ascii_billboard_concepts(self) -> None:
        brief = (
            "Generate me a markdown file that has two ASCII sketches, "
            "one for an ASCII sketch of a billboard for a car salesman, "
            "another one is an ASCII sketch for a restaurant advertisement on a billboard"
        )

        packet, schema, data, markdown = build_worker_bee_document(brief)

        self.assertEqual(packet.focus, "markdown")
        self.assertEqual(schema["title"], "ASCII Billboard Concepts")
        self.assertEqual(data["packet_id"], packet.packet_id)
        self.assertEqual(len(data["sketches"]), 2)
        self.assertEqual(data["sketches"][0]["title"], "Car Salesman Billboard")
        self.assertEqual(data["sketches"][1]["title"], "Restaurant Advertisement Billboard")
        self.assertIn("ASCII Sketches", markdown)
        self.assertIn("CAR SALESMAN", markdown)
        self.assertIn("RESTAURANT", markdown)
        self.assertIn("```text", markdown)

    def test_worker_bee_generate_command_writes_contract_backed_markdown(self) -> None:
        brief = (
            "Generate me a markdown file that has two ASCII sketches, "
            "one for an ASCII sketch of a billboard for a car salesman, "
            "another one is an ASCII sketch for a restaurant advertisement on a billboard"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            markdown_path = tmp_path / "billboards.md"
            schema_path = tmp_path / "billboards.schema.json"
            data_path = tmp_path / "billboards.json"

            code, stdout, stderr = self.run_cli(
                "worker-bee-generate",
                "--brief",
                brief,
                "--output",
                str(markdown_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee document written", stdout)
            self.assertTrue(markdown_path.exists())
            self.assertTrue(schema_path.exists())
            self.assertTrue(data_path.exists())

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            data = json.loads(data_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

            self.assertEqual(schema["title"], "ASCII Billboard Concepts")
            self.assertEqual(data["sketches"][0]["title"], "Car Salesman Billboard")
            self.assertEqual(data["sketches"][1]["title"], "Restaurant Advertisement Billboard")
            self.assertIn("CAR SALESMAN", markdown)
            self.assertIn("RESTAURANT", markdown)
            self.assertIn("```text", markdown)
            self.assertIn("ASCII Sketches", markdown)

