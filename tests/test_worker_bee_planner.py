from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.worker_bee.planner import build_generation_packet


class WorkerBeePlannerTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_generation_packet_is_deterministic_and_contract_backed(self) -> None:
        packet = build_generation_packet("Create a README for the generation fabric")
        packet_again = build_generation_packet("Create a README for the generation fabric")

        self.assertEqual(packet.packet_type, "generation-fabric.worker-bee.packet")
        self.assertEqual(packet.packet_version, "1")
        self.assertEqual(packet.focus, "markdown")
        self.assertTrue(packet.base_name.startswith("create-a-readme-for-the-generation-fabric"))
        self.assertEqual(packet.packet_id, packet_again.packet_id)
        self.assertEqual(packet.to_dict()["strategy"]["north_star"], "planner -> packet -> worker -> fabric -> verifier")
        self.assertEqual(packet.artifact_pipeline, ("schema", "json", "markdown"))
        self.assertIn("planner_proposes_only", packet.guardrails)
        self.assertIn("verification closes the loop before publish", packet.routing_notes)
        self.assertEqual(packet.metadata["base_name_source"], "inferred")
        self.assertIn("markdown", packet.metadata["focus_reason"])

    def test_worker_bee_plan_command_prints_packet_json(self) -> None:
        code, stdout, stderr = self.run_cli(
            "worker-bee-plan",
            "--brief",
            "Create a schema-backed markdown status page",
        )

        self.assertEqual(code, 0, stderr)
        packet = json.loads(stdout)
        self.assertEqual(packet["packet_type"], "generation-fabric.worker-bee.packet")
        self.assertEqual(packet["focus"], "markdown")
        self.assertEqual(packet["plan_steps"][0]["name"], "capture_brief")
        self.assertEqual(packet["artifact_pipeline"], ["schema", "json", "markdown"])
        self.assertIn("planner_does_not_write_files", packet["guardrails"])
        self.assertEqual(packet["metadata"]["base_name_source"], "inferred")

    def test_worker_bee_plan_command_writes_a_packet_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            brief_path = tmp_path / "brief.txt"
            output_path = tmp_path / "packet.json"
            brief = "Generate release notes from a brief."
            brief_path.write_text(brief, encoding="utf-8")

            code, stdout, stderr = self.run_cli(
                "worker-bee-plan",
                "--brief-file",
                str(brief_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee packet written", stdout)
            self.assertTrue(output_path.exists())

            packet = json.loads(output_path.read_text(encoding="utf-8"))
            expected = build_generation_packet(brief).to_dict()
            self.assertEqual(packet, expected)
            self.assertEqual(packet["routing_notes"][0], "planner emits packet JSON only")
            self.assertIn("validate the generated schema", packet["verification"])

