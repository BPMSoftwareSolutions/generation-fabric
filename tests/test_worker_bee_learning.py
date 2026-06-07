from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.worker_bee.learning import (
    DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES,
    run_worker_bee_learning_loop,
)


class WorkerBeeLearningTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_learning_loop_reports_full_coverage(self) -> None:
        report = run_worker_bee_learning_loop(rounds=3)

        self.assertTrue(report.passed)
        self.assertEqual(report.rounds_requested, 3)
        self.assertEqual(report.rounds_run, 1)
        self.assertEqual(report.capabilities, DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES)
        self.assertEqual(report.coverage_percent, 100.0)
        self.assertEqual(report.rounds[0].coverage_percent, 100.0)
        self.assertEqual(report.rounds[0].covered_capabilities, DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES)
        self.assertTrue(report.rounds[0].artifact_root)
        self.assertTrue(pathlib.Path(report.rounds[0].artifact_root).exists())
        self.assertIn("worker bee learned", report.summary)
        self.assertGreaterEqual(len(report.lessons), 1)
        self.assertTrue(all(case_result.passed for case_result in report.rounds[0].case_results))

    def test_worker_bee_learn_command_writes_a_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            report_path = tmp_path / "worker-bee-learning.json"

            code, stdout, stderr = self.run_cli(
                "worker-bee-learn",
                "--rounds",
                "2",
                "--output",
                str(report_path),
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("worker-bee learning report written", stdout)
            self.assertTrue(report_path.exists())

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["passed"])
            self.assertEqual(report["rounds_requested"], 2)
            self.assertEqual(report["rounds_run"], 1)
            self.assertEqual(report["coverage_percent"], 100.0)
            self.assertEqual(report["capabilities"], list(DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES))
            self.assertIn("worker-bee-generate", report["capabilities"])
            self.assertIn("worker-bee-plan", report["capabilities"])
            self.assertIn("worker-bee-taxonomy", report["capabilities"])
            self.assertTrue(report["rounds"][0]["artifact_root"])
            self.assertTrue(pathlib.Path(report["rounds"][0]["artifact_root"]).exists())


if __name__ == "__main__":
    unittest.main()
