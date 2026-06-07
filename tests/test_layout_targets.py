from __future__ import annotations

import contextlib
import copy
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.css.renderer import grid_column_span, render_css_document
from generation_fabric.layout.ascii_sketch import build_layout_zone_schema
from generation_fabric.layout.coherence import audit_layout_coherence, write_layout_coherence_report
from generation_fabric.svg.renderer import render_svg_document

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
ZONES_PATH = EXAMPLES / "value-simulator.zones.json"
CSS_PATH = EXAMPLES / "value-simulator.css"
SVG_PATH = EXAMPLES / "value-simulator.svg"
COHERENCE_PATH = EXAMPLES / "value-simulator.coherence.md"


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def load_zones() -> dict:
    return json.loads(read_text(ZONES_PATH))


class CssRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = build_layout_zone_schema()
        self.data = load_zones()

    def test_grid_column_span_rules(self) -> None:
        self.assertEqual(grid_column_span(0, 1, 12), "1 / -1")
        self.assertEqual(grid_column_span(0, 2, 12), "1 / 7")
        self.assertEqual(grid_column_span(1, 2, 12), "7 / -1")

    def test_every_zone_gets_an_ownership_rule(self) -> None:
        css = render_css_document(self.schema, self.data)
        for zone in self.data["zones"]:
            self.assertIn(f'[data-zone-id="{zone["zone_id"]}"]', css)
        self.assertIn("grid-template-columns: repeat(12, 1fr);", css)
        self.assertIn("@media (max-width: 720px) {", css)

    def test_css_render_is_deterministic(self) -> None:
        self.assertEqual(render_css_document(self.schema, self.data), render_css_document(self.schema, self.data))

    def test_committed_css_matches_render(self) -> None:
        self.assertEqual(read_text(CSS_PATH), render_css_document(self.schema, self.data))


class SvgRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = build_layout_zone_schema()
        self.data = load_zones()

    def test_every_zone_draws_a_rect(self) -> None:
        svg = render_svg_document(self.schema, self.data)
        self.assertTrue(svg.startswith("<svg "))
        for zone in self.data["zones"]:
            self.assertIn(f'data-zone-id="{zone["zone_id"]}"', svg)
        self.assertIn('<rect class="zone zone--full_width"', svg)
        self.assertIn('<rect class="zone zone--split_left"', svg)

    def test_committed_svg_matches_render(self) -> None:
        self.assertEqual(read_text(SVG_PATH), render_svg_document(self.schema, self.data))


class CoherenceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = build_layout_zone_schema()
        self.data = load_zones()

    def test_clean_taxonomy_scores_full_coherence(self) -> None:
        report = audit_layout_coherence(self.schema, self.data)
        self.assertTrue(report["passed"])
        self.assertEqual(report["score"], 100.0)
        self.assertEqual(len(report["checks"]), 10)
        self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))

    def test_duplicate_zone_ids_fail_the_audit(self) -> None:
        broken = copy.deepcopy(self.data)
        broken["zones"][1]["zone_id"] = broken["zones"][0]["zone_id"]
        report = audit_layout_coherence(self.schema, broken)
        self.assertFalse(report["passed"])
        unique_check = next(check for check in report["checks"] if check["check"] == "unique_zone_ids")
        self.assertEqual(unique_check["status"], "fail")

    def test_committed_coherence_report_matches_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "value-simulator.coherence.md"
            _paths, report = write_layout_coherence_report(self.schema, self.data, output=str(output))
            self.assertTrue(report["passed"])
            self.assertEqual(output.read_text(encoding="utf-8"), read_text(COHERENCE_PATH))


class LayoutTargetCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_layout_css_and_svg_commands_default_to_canonical_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            css_path = pathlib.Path(tmp) / "page.css"
            svg_path = pathlib.Path(tmp) / "page.svg"

            code, _stdout, stderr = self.run_cli("layout-css", "--data-file", str(ZONES_PATH), "--output", str(css_path))
            self.assertEqual(code, 0, stderr)
            self.assertIn('[data-zone-id="hero"]', css_path.read_text(encoding="utf-8"))

            code, _stdout, stderr = self.run_cli("layout-svg", "--data-file", str(ZONES_PATH), "--output", str(svg_path))
            self.assertEqual(code, 0, stderr)
            self.assertIn("<svg ", svg_path.read_text(encoding="utf-8"))

    def test_layout_coherence_command_writes_report_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = pathlib.Path(tmp) / "page.coherence.md"
            code, stdout, stderr = self.run_cli(
                "layout-coherence",
                "--data-file",
                str(ZONES_PATH),
                "--output",
                str(report_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("100.0% coherence", stdout)
            self.assertTrue(report_path.exists())
            self.assertTrue((pathlib.Path(tmp) / "page.coherence.schema.json").exists())
            self.assertTrue((pathlib.Path(tmp) / "page.coherence.json").exists())


if __name__ == "__main__":
    unittest.main()
