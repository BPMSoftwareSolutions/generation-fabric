from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import json_schema_crud as jsc
from generation_fabric.layout.inventory import build_layout_inventory, write_layout_inventory_report
from generation_fabric.markdown.renderer import render_markdown_document

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
INVENTORY_PATH = EXAMPLES / "segment-inventory.md"
SEGMENT_ZONES = (
    EXAMPLES / "enterprise-engineering-cost-avoidance.zones.json",
    EXAMPLES / "msp-consultancy-delivery-acceleration.zones.json",
    EXAMPLES / "ai-platform-compute-discipline.zones.json",
)


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def load_segment_documents() -> list[tuple[str, dict]]:
    documents = []
    for path in SEGMENT_ZONES:
        document = json.loads(read_text(path))
        documents.append((document["page_id"], document))
    return documents


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = load_segment_documents()
        self.inventory = build_layout_inventory(self.documents)

    def test_shared_skeleton_is_detected(self) -> None:
        self.assertEqual(self.inventory["metrics"]["total_pages"], 3)
        self.assertEqual(self.inventory["metrics"]["total_zones"], 7)
        self.assertEqual(self.inventory["metrics"]["shared"], 7)
        self.assertEqual(self.inventory["metrics"]["structural_reuse_percent"], 100.0)
        self.assertEqual(self.inventory["page_specific"], [])

    def test_content_variation_is_reported(self) -> None:
        variants = {zone["zone_id"]: zone["content_variants"] for zone in self.inventory["zones"]}
        self.assertEqual(variants["hero"], 3)
        self.assertEqual(variants["segment"], 3)
        self.assertEqual(variants["loc-evidence-chain"], 1)

    def test_unique_and_common_classes(self) -> None:
        page_a = ("page-a", {"page_id": "page-a", "zones": [{"zone_id": "shared", "label": "A", "layout_role": "full_width"}, {"zone_id": "only_a", "label": "A2", "layout_role": "full_width"}]})
        page_b = ("page-b", {"page_id": "page-b", "zones": [{"zone_id": "shared", "label": "B", "layout_role": "full_width"}]})
        inventory = build_layout_inventory([page_a, page_b])
        classes = {zone["zone_id"]: zone["reuse_class"] for zone in inventory["zones"]}
        self.assertEqual(classes["shared"], "shared")
        self.assertEqual(classes["only_a"], "unique")
        self.assertEqual(inventory["page_specific"], ["only_a"])

    def test_committed_inventory_report_matches_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "segment-inventory.md"
            write_layout_inventory_report(self.documents, output=str(output))
            self.assertEqual(output.read_text(encoding="utf-8"), read_text(INVENTORY_PATH))


class InventoryScriptTests(unittest.TestCase):
    def test_generator_script_reproduces_committed_examples(self) -> None:
        script_path = REPO_ROOT / "scripts" / "generate_segment_examples.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("generated:", result.stdout)

        # The committed report is reproducible from its committed sidecars.
        schema = json.loads(read_text(EXAMPLES / "segment-inventory.schema.json"))
        data = json.loads(read_text(EXAMPLES / "segment-inventory.json"))
        self.assertEqual(render_markdown_document(schema, data), read_text(INVENTORY_PATH))

        visual_schema = json.loads(read_text(EXAMPLES / "visual-intent-inventory.schema.json"))
        visual_data = json.loads(read_text(EXAMPLES / "visual-intent-inventory.json"))
        visual_markdown = read_text(EXAMPLES / "visual-intent-inventory.md")
        self.assertEqual(render_markdown_document(visual_schema, visual_data), visual_markdown)
        self.assertTrue((EXAMPLES / "msp-consultancy-delivery-acceleration.boxes.json").exists())


class InventoryCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_layout_inventory_command_compares_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "inventory.md"
            args = ["layout-inventory"]
            for path in SEGMENT_ZONES:
                args.extend(["--data-file", str(path)])
            args.extend(["--output", str(output)])
            code, stdout, stderr = self.run_cli(*args)
            self.assertEqual(code, 0, stderr)
            self.assertIn("3 pages compared", stdout)
            self.assertEqual(output.read_text(encoding="utf-8"), read_text(INVENTORY_PATH))


if __name__ == "__main__":
    unittest.main()
