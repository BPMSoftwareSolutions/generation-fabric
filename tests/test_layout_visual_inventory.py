from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from generation_fabric.layout.visual_inventory import build_visual_intent_inventory, write_visual_intent_inventory_report
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.worker_bee.layout_sketch import write_worker_bee_sketch

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
VISUAL_INVENTORY_PATH = EXAMPLES / "visual-intent-inventory.md"

BRIEFS = (
    "Enterprise engineering organization focused on cost avoidance",
    "MSP consultancy scaling delivery acceleration across many clients",
    "AI platform team focused on compute discipline and reducing model retry waste",
)


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


class VisualInventoryTests(unittest.TestCase):
    def build_items(self, output_dir: pathlib.Path) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for brief in BRIEFS:
            paths, bundle = write_worker_bee_sketch(brief, output_dir=str(output_dir), overwrite=True)
            items.append(
                {
                    "page_id": bundle.page_id,
                    "title": bundle.document["title"],
                    "segment_label": bundle.segment_label,
                    "value_angle_label": bundle.value_angle_label,
                    "visualization": {
                        "ascii_sketch_required": True,
                        "ascii_sketch_path": paths.sketch_path.relative_to(output_dir).as_posix(),
                        "sketch_type": "layout_flow",
                        "sketch_status": "approved" if bundle.report["passed"] else "needs_attention",
                        "zone_taxonomy_path": paths.zones_path.relative_to(output_dir).as_posix(),
                        "box_model_path": paths.boxes_path.relative_to(output_dir).as_posix(),
                        "visual_coherence_status": "aligned" if bundle.report["passed"] else "drifted",
                    },
                    "notes": [f"Coherence score: {bundle.report['score']:.1f}%"],
                }
            )
        return items

    def test_visual_inventory_reports_sketch_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            items = self.build_items(tmp_path)
            paths, inventory = write_visual_intent_inventory_report(items, output=str(tmp_path / "visual-intent-inventory.md"), overwrite=True)

            self.assertTrue(paths.schema_path.exists())
            self.assertTrue(paths.data_path.exists())
            self.assertTrue(paths.markdown_path.exists())
            self.assertEqual(inventory["coverage"]["total_items"], 3)
            self.assertEqual(inventory["coverage"]["approved"], 3)
            self.assertEqual(inventory["coverage"]["sketch_coverage"], 100.0)

            schema = json.loads(paths.schema_path.read_text(encoding="utf-8"))
            data = json.loads(paths.data_path.read_text(encoding="utf-8"))
            markdown = read_text(paths.markdown_path)
            self.assertEqual(render_markdown_document(schema, data), markdown)
            self.assertIn("Coverage Metrics", markdown)
            self.assertIn("Inventory Items", markdown)
            self.assertIn("Visualization", markdown)
            self.assertIn("ascii_sketch_path", markdown)
            self.assertIn("box_model_path", markdown)

    def test_committed_inventory_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            items = self.build_items(tmp_path)
            inventory = build_visual_intent_inventory(items)
            self.assertEqual(inventory["coverage"]["total_items"], 3)
            self.assertEqual(inventory["coverage"]["sketch_required"], 3)
            self.assertEqual(inventory["drifted_items"], [])


if __name__ == "__main__":
    unittest.main()
