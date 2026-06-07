from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.worker_bee.object_model import scan_python_object_model


class WorkerBeeObjectModelTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_scan_python_object_model_finds_provider_inventory(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "provider.py"

        document = scan_python_object_model([source_path], scope="module")

        self.assertEqual(document.shape, "object-model")
        self.assertEqual(document.scope, "module")
        self.assertTrue(document.source_hash.startswith("sha256:"))

        class_names = [model_class.name for model_class in document.classes]
        self.assertEqual(
            class_names,
            [
                "WorkerBeePlanProposal",
                "WorkerBeePlanningProvider",
                "DeterministicWorkerBeePlanningProvider",
            ],
        )
        self.assertEqual(len(document.relationships), 3)
        self.assertGreaterEqual(len(document.patterns), 3)
        self.assertGreaterEqual(len(document.checks), 1)

    def test_object_model_report_renders_coherent_class_tables(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "provider.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            markdown_path = tmp_path / "provider.object-model.md"

            code, stdout, stderr = self.run_cli(
                "worker-bee-object-model",
                "--source-file",
                str(source_path),
                "--output",
                str(markdown_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee object model written", stdout)

            schema_path = tmp_path / "provider.object-model.schema.json"
            data_path = tmp_path / "provider.object-model.json"
            self.assertTrue(schema_path.exists())
            self.assertTrue(data_path.exists())
            self.assertTrue(markdown_path.exists())

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            data = json.loads(data_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

            self.assertEqual(schema["title"], "Object Model: module")
            self.assertIn("Class Inventory", markdown)
            self.assertIn("Relationship Inventory", markdown)
            self.assertIn("Pattern Signals", markdown)
            self.assertIn("Coherence Checks", markdown)
            self.assertIn("classDiagram", markdown)
            self.assertIn("WorkerBeePlanProposal", markdown)
            self.assertIn("DeterministicWorkerBeePlanningProvider", markdown)
            self.assertIn("provider_name | str | missing | 19 | 19", markdown)
            self.assertIn("to_dict | def WorkerBeePlanProposal.to_dict", markdown)

            proposal_segment = markdown.split("### WorkerBeePlanProposal", 1)[1].split("### WorkerBeePlanningProvider", 1)[0]
            self.assertEqual(proposal_segment.count("| name | annotation | default_kind | line_start | line_end |"), 1)
            self.assertEqual(proposal_segment.count("| name | signature | decorators | calls | mutations | returns | line_start | line_end |"), 1)
            self.assertIn("| provider_name | str | missing | 19 | 19 |", proposal_segment)
            self.assertIn("| metadata | dict[str, Any] | factory | 27 | 27 |", proposal_segment)
            self.assertIn("| to_dict | def WorkerBeePlanProposal.to_dict(self) -> dict[str, Any] |  | to_jsonable_dataclass |  | to_jsonable_dataclass(self) | 29 | 32 |", proposal_segment)

            self.assertEqual(data["overview"]["shape"], "object-model")
            self.assertEqual(len(data["class_inventory"]["rows"]), 3)


if __name__ == "__main__":
    unittest.main()
