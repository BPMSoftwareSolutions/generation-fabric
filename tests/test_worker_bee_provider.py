from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.worker_bee.provider import (
    DeterministicWorkerBeePlanningProvider,
    build_provider_backed_generation_packet,
    propose_worker_bee_plan,
)


class WorkerBeeProviderTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_provider_proposal_is_deterministic_and_prompted(self) -> None:
        brief = "Create a markdown operations note for the generation fabric."
        provider = DeterministicWorkerBeePlanningProvider()

        proposal = propose_worker_bee_plan(brief, provider=provider)
        packet = build_provider_backed_generation_packet(brief, provider=provider)

        self.assertEqual(proposal.provider_name, "local-deterministic")
        self.assertTrue(proposal.prompt.startswith("You are the worker-bee planner"))
        self.assertIn("contract-backed", proposal.prompt)
        self.assertEqual(packet.metadata["planner_mode"], "provider-backed")
        self.assertEqual(packet.metadata["provider"]["provider_name"], "local-deterministic")
        self.assertEqual(packet.focus, "markdown")
        self.assertEqual(packet.packet_type, "generation-fabric.worker-bee.packet")

    def test_worker_bee_propose_command_writes_a_proposal_file(self) -> None:
        brief = "Create a markdown operations note for the generation fabric."

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            output_path = tmp_path / "proposal.json"

            code, stdout, stderr = self.run_cli(
                "worker-bee-propose",
                "--brief",
                brief,
                "--output",
                str(output_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee proposal written", stdout)
            self.assertTrue(output_path.exists())

            proposal = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(proposal["provider_name"], "local-deterministic")
            self.assertEqual(proposal["focus"], "markdown")
            self.assertIn("Return a concise planning proposal", proposal["prompt"])
            self.assertIn("reuse the existing fabric primitives", proposal["recommendations"])


if __name__ == "__main__":
    unittest.main()
