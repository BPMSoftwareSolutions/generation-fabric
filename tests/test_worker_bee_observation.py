from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.worker_bee.observation import collect_python_function_observations
from generation_fabric.worker_bee.taxonomy import scan_python_source_taxonomy


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

    def test_scan_python_source_taxonomy_finds_planner_inventory(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        taxonomy = scan_python_source_taxonomy(source_path)

        self.assertEqual(taxonomy.shape, "code-taxonomy")
        self.assertEqual(taxonomy.module_path, "generation_fabric.worker_bee.planner")
        self.assertTrue(taxonomy.source_hash.startswith("sha256:"))
        symbol_names = [symbol.name for symbol in taxonomy.symbols]
        self.assertIn("normalize_brief", symbol_names)
        self.assertIn("build_generation_packet", symbol_names)
        self.assertGreaterEqual(len(taxonomy.execution_paths), 1)
        self.assertTrue(any(path.conditions for path in taxonomy.execution_paths))
        self.assertTrue(any(path.mutations for path in taxonomy.execution_paths))

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
            self.assertIn("overview", data)
            self.assertIn("inventory", data)
            self.assertIn("executions", data)
            self.assertIn("sequenceDiagram", markdown)
            self.assertIn("Overview", markdown)
            self.assertIn("Code Inventory", markdown)
            self.assertIn("Executions", markdown)
            self.assertIn("State Changes", markdown)
            self.assertIn("Returns", markdown)
            self.assertIn("Dataclass_Serializer-->>Worker_Bee_Generation_Packet_Serializer: return", markdown)

    def test_worker_bee_taxonomy_command_writes_a_taxonomy_document(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            taxonomy_path = tmp_path / "planner-taxonomy.json"

            code, stdout, stderr = self.run_cli(
                "worker-bee-taxonomy",
                "--source-file",
                str(source_path),
                "--output",
                str(taxonomy_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee taxonomy written", stdout)
            self.assertTrue(taxonomy_path.exists())

            schema_path = tmp_path / "planner-taxonomy.schema.json"
            self.assertTrue(schema_path.exists())

            taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
            self.assertEqual(taxonomy["shape"], "code-taxonomy")
            self.assertEqual(taxonomy["module_path"], "generation_fabric.worker_bee.planner")
            self.assertIn("build_generation_packet", [symbol["name"] for symbol in taxonomy["symbols"]])

    def test_worker_bee_observe_command_can_reuse_a_saved_taxonomy(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            taxonomy_path = tmp_path / "planner-taxonomy.json"
            markdown_path = tmp_path / "planner-observation.md"

            taxonomy_code, _, taxonomy_stderr = self.run_cli(
                "worker-bee-taxonomy",
                "--source-file",
                str(source_path),
                "--output",
                str(taxonomy_path),
            )
            self.assertEqual(taxonomy_code, 0, taxonomy_stderr)

            code, stdout, stderr = self.run_cli(
                "worker-bee-observe",
                "--taxonomy-file",
                str(taxonomy_path),
                "--output",
                str(markdown_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee observation written", stdout)
            self.assertTrue(markdown_path.exists())
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("sequenceDiagram", markdown)
            self.assertIn("Code Inventory", markdown)
            self.assertIn("Executions", markdown)
            self.assertIn("State Changes", markdown)
            self.assertIn("Returns", markdown)
            self.assertIn("Dataclass_Serializer-->>Worker_Bee_Generation_Packet_Serializer: return", markdown)


if __name__ == "__main__":
    unittest.main()
