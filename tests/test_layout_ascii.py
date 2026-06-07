from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.exceptions import SchemaError
from generation_fabric.html.renderer import render_html_document
from generation_fabric.layout.ascii_sketch import (
    build_layout_zone_schema,
    build_zone_document,
    parse_ascii_sketch,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
SKETCH_PATH = EXAMPLES / "value-simulator.ascii.md"
ZONES_PATH = EXAMPLES / "value-simulator.zones.json"
HTML_PATH = EXAMPLES / "value-simulator.html"
SCHEMA_PATH = EXAMPLES / "layout-zone.schema.json"


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


class LayoutAsciiParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sketch = read_text(SKETCH_PATH)

    def test_parse_detects_all_zones_in_reading_order(self) -> None:
        zones = parse_ascii_sketch(self.sketch)
        self.assertEqual(
            [zone.zone_id for zone in zones],
            [
                "hero",
                "segment-picker",
                "value-simulator",
                "formula-assumptions",
                "market-citations",
                "loc-evidence-chain",
                "limitations-transformation-review-cta",
            ],
        )

    def test_colon_label_splits_into_purpose(self) -> None:
        hero = parse_ascii_sketch(self.sketch)[0]
        self.assertEqual(hero.label, "HERO: Estimate the value of governed AI engineering")
        self.assertEqual(hero.purpose, "Estimate the value of governed AI engineering")
        self.assertEqual(hero.layout_role, "full_width")

    def test_two_column_band_gets_split_layout_roles(self) -> None:
        zones = {zone.zone_id: zone for zone in parse_ascii_sketch(self.sketch)}
        left = zones["segment-picker"]
        right = zones["value-simulator"]
        self.assertEqual(left.layout_role, "split_left")
        self.assertEqual(right.layout_role, "split_right")
        self.assertEqual(left.bounds.column_count, 2)
        self.assertEqual(left.details, ("Enterprise / MSP / AI",))
        self.assertEqual(right.details, ("Inputs + annual value opportunity",))

    def test_parse_is_deterministic(self) -> None:
        first = [zone.to_dict() for zone in parse_ascii_sketch(self.sketch)]
        second = [zone.to_dict() for zone in parse_ascii_sketch(self.sketch)]
        self.assertEqual(first, second)

    def test_empty_sketch_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            parse_ascii_sketch("   \n  \n")


class LayoutZoneContractTests(unittest.TestCase):
    def test_document_validates_against_canonical_schema(self) -> None:
        document = build_zone_document(read_text(SKETCH_PATH), page_id="value-simulator")
        self.assertEqual(document["page_id"], "value-simulator")
        self.assertEqual(document["title"], "Estimate the value of governed AI engineering")
        self.assertEqual(len(document["zones"]), 7)

    def test_committed_schema_matches_builder(self) -> None:
        committed = json.loads(read_text(SCHEMA_PATH))
        self.assertEqual(committed, build_layout_zone_schema())

    def test_committed_zones_match_parser(self) -> None:
        document = build_zone_document(read_text(SKETCH_PATH), page_id="value-simulator")
        committed = json.loads(read_text(ZONES_PATH))
        self.assertEqual(committed, document)


class LayoutHtmlRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = build_layout_zone_schema()
        self.data = json.loads(read_text(ZONES_PATH))

    def test_html_has_semantic_zone_sections(self) -> None:
        html = render_html_document(self.schema, self.data)
        self.assertIn('<main class="layout" data-page-id="value-simulator">', html)
        self.assertIn('<section data-zone-id="hero" data-layout-role="full_width">', html)
        self.assertIn('<section data-zone-id="segment-picker" data-layout-role="split_left">', html)
        self.assertIn("<h1>Estimate the value of governed AI engineering</h1>", html)
        self.assertIn("<li>Enterprise / MSP / AI</li>", html)

    def test_html_render_is_deterministic(self) -> None:
        self.assertEqual(
            render_html_document(self.schema, self.data),
            render_html_document(self.schema, self.data),
        )

    def test_committed_html_matches_render(self) -> None:
        rendered = render_html_document(self.schema, self.data)
        self.assertEqual(read_text(HTML_PATH), rendered)


class LayoutCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_ascii_zones_then_layout_html_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            zones_path = tmp_path / "page.zones.json"
            html_path = tmp_path / "page.html"

            code, stdout, stderr = self.run_cli(
                "ascii-zones",
                "--source-file",
                str(SKETCH_PATH),
                "--page-id",
                "value-simulator",
                "--output",
                str(zones_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("detected 7 zones", stdout)
            self.assertTrue(zones_path.exists())

            # layout-html defaults to the canonical schema when none is supplied.
            code, stdout, stderr = self.run_cli(
                "layout-html",
                "--data-file",
                str(zones_path),
                "--output",
                str(html_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertTrue(html_path.exists())

            html = html_path.read_text(encoding="utf-8")
            self.assertIn('<section data-zone-id="loc-evidence-chain" data-layout-role="split_right">', html)
            self.assertEqual(json.loads(zones_path.read_text(encoding="utf-8")), json.loads(read_text(ZONES_PATH)))

    def test_ascii_zones_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zones_path = pathlib.Path(tmp) / "page.zones.json"
            zones_path.write_text("{}", encoding="utf-8")
            code, _stdout, stderr = self.run_cli(
                "ascii-zones",
                "--source-file",
                str(SKETCH_PATH),
                "--output",
                str(zones_path),
            )
            self.assertEqual(code, 1)
            self.assertIn("refusing to overwrite", stderr)


if __name__ == "__main__":
    unittest.main()
