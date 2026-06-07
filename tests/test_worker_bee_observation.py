from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.worker_bee.observation import collect_python_function_observations


class WorkerBeeObservationTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_collect_python_function_observations_finds_planner_paths(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        observations = collect_python_function_observations(source_path)

        self.assertGreaterEqual(len(observations), 1)
        names = [observation.name for observation in observations]
        self.assertIn("normalize_brief", names)
        normalize_observation = next(observation for observation in observations if observation.name == "normalize_brief")
        self.assertIn("def normalize_brief", normalize_observation.signature)
        self.assertTrue(all(observation.participants[0] == "Caller" for observation in observations))

    def test_worker_bee_observe_command_writes_a_sequence_diagram_document(self) -> None:
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
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee observation written", stdout)
            self.assertTrue(markdown_path.exists())

            schema_path = tmp_path / "planner-observation.schema.json"
            data_path = tmp_path / "planner-observation.json"
            self.assertTrue(schema_path.exists())
            self.assertTrue(data_path.exists())

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            data = json.loads(data_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

            self.assertEqual(schema["title"], "Code Observation: planner")
            self.assertEqual(data["shape"], "sequence-diagram")
            self.assertIn("sequenceDiagram", markdown)
            self.assertIn("participant Caller", markdown)
            self.assertIn("Execution Paths", markdown)


if __name__ == "__main__":
    unittest.main()
