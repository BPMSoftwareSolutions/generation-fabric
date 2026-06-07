from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.exceptions import SchemaError
from generation_fabric.layout.box_model import build_box_model_document, leaf_boxes

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
ZONES_PATH = EXAMPLES / "value-simulator.zones.json"
BOXES_PATH = EXAMPLES / "value-simulator.boxes.json"


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def load_zones() -> dict:
    return json.loads(read_text(ZONES_PATH))


class BoxModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.zones = load_zones()
        self.boxes_document = build_box_model_document(self.zones)

    def test_box_model_nests_page_bands_and_surfaces(self) -> None:
        boxes = {box["box_id"]: box for box in self.boxes_document["boxes"]}
        # 1 page + 5 bands + 7 surfaces.
        self.assertEqual(len(self.boxes_document["boxes"]), 13)
        self.assertEqual(boxes["page"]["layout_type"], "stack")
        self.assertEqual(boxes["page"]["contains"], ["band-0", "band-1", "band-2", "band-3", "band-4"])
        self.assertEqual(boxes["band-1"]["layout_type"], "two_column")
        self.assertEqual(boxes["band-1"]["contains"], ["segment-picker", "value-simulator"])

    def test_two_column_band_collapses_responsively(self) -> None:
        band = next(box for box in self.boxes_document["boxes"] if box["box_id"] == "band-1")
        self.assertEqual(band["responsive_behavior"], {"desktop": "two_column", "tablet": "stacked", "mobile": "single_column"})

    def test_every_zone_becomes_a_named_surface(self) -> None:
        surfaces = leaf_boxes(self.boxes_document)
        surface_ids = {box["box_id"] for box in surfaces}
        zone_ids = {zone["zone_id"] for zone in self.zones["zones"]}
        self.assertEqual(surface_ids, zone_ids)
        for box in surfaces:
            self.assertTrue(box["css_class"].startswith(f"surface surface--{box['box_id']}"))

    def test_empty_zones_are_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            build_box_model_document({"page_id": "x", "zones": []})

    def test_committed_box_model_matches_builder(self) -> None:
        committed = json.loads(read_text(BOXES_PATH))
        self.assertEqual(committed, self.boxes_document)


class BoxModelCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_layout_boxes_command_writes_box_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "page.boxes.json"
            code, stdout, stderr = self.run_cli(
                "layout-boxes",
                "--data-file",
                str(ZONES_PATH),
                "--output",
                str(output),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("derived 13 boxes", stdout)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), json.loads(read_text(BOXES_PATH)))


if __name__ == "__main__":
    unittest.main()
