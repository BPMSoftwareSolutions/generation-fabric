from __future__ import annotations

import contextlib
import copy
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import json_schema_crud as jsc

from generation_fabric.css.web_renderer import render_web_css_document
from generation_fabric.html.web_renderer import render_web_html_document
from generation_fabric.layout.ascii_sketch import build_zone_document
from generation_fabric.layout.web_coherence import audit_web_coherence, write_web_coherence_report
from generation_fabric.layout.web_contract import build_web_page_contract
from generation_fabric.layout.web_repair import repair_web_contract, run_web_repair_cycle
from generation_fabric.svg.web_renderer import render_web_svg_document

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
PAGE_ID = "operations-dashboard"


def read_text(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


def build_contract() -> dict:
    sketch = read_text(f"{PAGE_ID}.ascii.md")
    zones = build_zone_document(sketch, page_id=PAGE_ID, title="Operations Dashboard")
    return build_web_page_contract(zones)


class WebContractTests(unittest.TestCase):
    def test_contract_combines_layers(self) -> None:
        contract = build_contract()
        self.assertEqual(contract["kind"], "web_page_contract")
        self.assertEqual(len(contract["components"]), 5)
        self.assertTrue(contract["zones"])
        self.assertTrue(contract["boxes"])
        self.assertEqual(contract["source_sketch"]["format"], "ascii")
        self.assertTrue(contract["source_sketch"]["hash"].startswith("sha256:"))

    def test_committed_web_contract_matches_builder(self) -> None:
        self.assertEqual(json.loads(read_text(f"{PAGE_ID}.web.json")), build_contract())


class WebHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = render_web_html_document(build_contract())

    def test_components_render_semantic_markup(self) -> None:
        self.assertIn("<form class=\"gf-form\"", self.html)
        self.assertIn('type="date"', self.html)
        self.assertIn("<table class=\"gf-table\">", self.html)
        self.assertIn("<figure class=\"gf-chart\"", self.html)
        self.assertIn('data-component-id="component-runs"', self.html)

    def test_single_main_landmark(self) -> None:
        self.assertEqual(self.html.count('role="main"'), 1)

    def test_committed_html_matches_render(self) -> None:
        self.assertEqual(read_text(f"{PAGE_ID}.html"), self.html)


class WebCssTests(unittest.TestCase):
    def setUp(self) -> None:
        self.css = render_web_css_document(build_contract())

    def test_css_has_layout_and_component_ownership(self) -> None:
        self.assertIn("grid-template-columns: repeat(12, 1fr);", self.css)
        self.assertIn('[data-zone-id="filters-form"]', self.css)
        self.assertIn(".gf-form", self.css)
        self.assertIn("--gf-color-accent", self.css)

    def test_committed_css_matches_render(self) -> None:
        self.assertEqual(read_text(f"{PAGE_ID}.css"), self.css)


class WebSvgTests(unittest.TestCase):
    def setUp(self) -> None:
        self.svg = render_web_svg_document(build_contract())

    def test_each_component_draws_a_group(self) -> None:
        self.assertTrue(self.svg.startswith("<svg "))
        for component_id in ("component-filters", "component-runs", "component-delivery-health"):
            self.assertIn(f'data-component-id="{component_id}"', self.svg)
        self.assertIn("gf-glyph-series", self.svg)  # the chart_line polyline glyph
        self.assertIn("gf-glyph-arc", self.svg)  # the gauge arc glyph

    def test_committed_svg_matches_render(self) -> None:
        self.assertEqual(read_text(f"{PAGE_ID}.svg"), self.svg)


class WebCoherenceTests(unittest.TestCase):
    def test_clean_contract_scores_full_coherence(self) -> None:
        report = audit_web_coherence(build_contract())
        self.assertTrue(report["passed"])
        self.assertEqual(report["score"], 100.0)
        self.assertEqual(len(report["checks"]), 11)

    def test_missing_form_controls_warns(self) -> None:
        contract = build_contract()
        for component in contract["components"]:
            if component["component_type"] == "form":
                component["fields"] = []
                component["actions"] = []
        report = audit_web_coherence(contract)
        check = next(c for c in report["checks"] if c["check"] == "form_controls_present")
        self.assertEqual(check["status"], "warn")
        self.assertTrue(check["remediation"])

    def test_committed_coherence_report_matches_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / f"{PAGE_ID}.web-coherence.md"
            write_web_coherence_report(build_contract(), output=str(output))
            self.assertEqual(output.read_text(encoding="utf-8"), read_text(f"{PAGE_ID}.web-coherence.md"))


class WebRepairTests(unittest.TestCase):
    def _broken_contract(self) -> dict:
        contract = copy.deepcopy(build_contract())
        for component in contract["components"]:
            if component["component_type"] == "gauge":
                component["measures"] = {"value": "delivery_health"}  # drop min/max
            if component["component_type"] == "form":
                component["accessibility"] = {}  # drop aria label
        return contract

    def test_repair_backfills_defaults_and_labels(self) -> None:
        repaired, repairs = repair_web_contract(self._broken_contract())
        self.assertTrue(repairs)
        gauge = next(c for c in repaired["components"] if c["component_type"] == "gauge")
        self.assertEqual(gauge["measures"]["min"], "0")
        self.assertEqual(gauge["measures"]["max"], "100")
        form = next(c for c in repaired["components"] if c["component_type"] == "form")
        self.assertTrue(form["accessibility"]["aria_label"])

    def test_repair_cycle_improves_coherence(self) -> None:
        cycle = run_web_repair_cycle(self._broken_contract())
        self.assertGreater(cycle["after_score"], cycle["before_score"])
        self.assertTrue(cycle["improved"])
        self.assertTrue(cycle["after_passed"])


class WebCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_ascii_web_writes_full_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = self.run_cli(
                "ascii-web",
                "--source-file",
                str(EXAMPLES / f"{PAGE_ID}.ascii.md"),
                "--page-id",
                "ops",
                "--output-dir",
                tmp,
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("100.0%", stdout)
            for suffix in (".components.json", ".web.json", ".html", ".css", ".svg", ".web-coherence.md"):
                self.assertTrue((pathlib.Path(tmp) / f"ops{suffix}").exists(), suffix)

    def test_layout_web_html_renders_from_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html_path = pathlib.Path(tmp) / "page.html"
            code, _stdout, stderr = self.run_cli(
                "layout-web-html",
                "--contract-file",
                str(EXAMPLES / f"{PAGE_ID}.web.json"),
                "--output",
                str(html_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("<form class=\"gf-form\"", html_path.read_text(encoding="utf-8"))


class WebGeneratorTests(unittest.TestCase):
    def test_generator_reproduces_committed_bundle(self) -> None:
        script_path = REPO_ROOT / "scripts" / "generate_operations_dashboard.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("100.0%", result.stdout)


if __name__ == "__main__":
    unittest.main()
