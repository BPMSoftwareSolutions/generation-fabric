from __future__ import annotations

import contextlib
import io
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.layout.ascii_sketch import build_zone_document
from generation_fabric.worker_bee.layout_sketch import (
    build_segment_value_sketch,
    build_worker_bee_sketch,
    infer_sketch_profile,
)

MSP_BRIEF = "Build an MSP consultancy page focused on delivery acceleration across many clients"


class WorkerBeeSketchProfileTests(unittest.TestCase):
    def test_infer_profile_matches_segment_and_value_angle(self) -> None:
        segment, value_angle = infer_sketch_profile(MSP_BRIEF)
        self.assertEqual(segment[0], "msp-consultancy")
        self.assertEqual(value_angle[0], "delivery-acceleration")

    def test_infer_profile_defaults_when_no_keywords_match(self) -> None:
        segment, value_angle = infer_sketch_profile("a generic note with no signals")
        self.assertEqual(segment[0], "enterprise-engineering")
        self.assertEqual(value_angle[0], "cost-avoidance")

    def test_generated_sketch_round_trips_into_seven_zones(self) -> None:
        sketch, page_id, _title, _segment_label, _value_headline = build_segment_value_sketch(MSP_BRIEF)
        self.assertEqual(page_id, "msp-consultancy.delivery-acceleration")
        document = build_zone_document(sketch, page_id=page_id)
        self.assertEqual(len(document["zones"]), 7)
        # The generated box must stay perfectly aligned (every line same width).
        widths = {len(line) for line in sketch.splitlines()}
        self.assertEqual(len(widths), 1)


class WorkerBeeSketchBundleTests(unittest.TestCase):
    def test_bundle_renders_every_target_and_passes_coherence(self) -> None:
        bundle = build_worker_bee_sketch(MSP_BRIEF)
        self.assertEqual(bundle.page_id, "msp-consultancy-delivery-acceleration")
        self.assertEqual(bundle.segment_label, "MSP / consultancy")
        self.assertEqual(len(bundle.document["zones"]), 7)
        self.assertEqual(len(bundle.box_model["boxes"]), 13)
        self.assertIn('<section data-zone-id="hero"', bundle.html)
        self.assertIn('[data-zone-id="hero"]', bundle.css)
        self.assertIn("<svg ", bundle.svg)
        self.assertIn("Layout Coherence Report", bundle.coherence_markdown)
        self.assertTrue(bundle.report["passed"])
        self.assertEqual(bundle.report["score"], 100.0)

    def test_bundle_is_deterministic(self) -> None:
        first = build_worker_bee_sketch(MSP_BRIEF)
        second = build_worker_bee_sketch(MSP_BRIEF)
        self.assertEqual(first.sketch, second.sketch)
        self.assertEqual(first.document, second.document)
        self.assertEqual(first.box_model, second.box_model)
        self.assertEqual(first.css, second.css)
        self.assertEqual(first.svg, second.svg)


class WorkerBeeSketchCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_command_writes_all_six_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = self.run_cli(
                "worker-bee-sketch",
                "--brief",
                MSP_BRIEF,
                "--output-dir",
                tmp,
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("100.0% coherence", stdout)
            base = "msp-consultancy-delivery-acceleration"
            for suffix in (".ascii.md", ".zones.json", ".boxes.json", ".html", ".css", ".svg", ".coherence.md"):
                self.assertTrue((pathlib.Path(tmp) / (base + suffix)).exists(), suffix)

    def test_command_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = pathlib.Path(tmp) / "msp-consultancy-delivery-acceleration.ascii.md"
            existing.write_text("x", encoding="utf-8")
            code, _stdout, stderr = self.run_cli(
                "worker-bee-sketch",
                "--brief",
                MSP_BRIEF,
                "--output-dir",
                tmp,
            )
            self.assertEqual(code, 1)
            self.assertIn("refusing to overwrite", stderr)


if __name__ == "__main__":
    unittest.main()
