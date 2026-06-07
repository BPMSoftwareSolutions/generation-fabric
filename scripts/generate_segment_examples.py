"""Generate segment layout examples and a reuse inventory using the fabric.

This produces three segment- and value-angle-specific zone taxonomies plus the
reuse inventory that compares them, demonstrating "design reuse before code
reuse": the segment pages share a canonical zone skeleton while carrying
page-specific content.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from generation_fabric.layout.inventory import write_layout_inventory_report
from generation_fabric.layout.visual_inventory import write_visual_intent_inventory_report
from generation_fabric.worker_bee.layout_sketch import write_worker_bee_sketch

OUTPUT_DIR = REPO_ROOT / "examples"
INVENTORY_PATH = OUTPUT_DIR / "segment-inventory.md"
VISUAL_INVENTORY_PATH = OUTPUT_DIR / "visual-intent-inventory.md"

SEGMENT_BRIEFS = (
    "Enterprise engineering organization focused on cost avoidance",
    "MSP consultancy scaling delivery acceleration across many clients",
    "AI platform team focused on compute discipline and reducing model retry waste",
)


def _display_path(path: Path) -> str:
    """Render a repository-relative path when possible."""

    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_segment_documents() -> tuple[list[tuple[str, dict]], list[dict[str, object]], list[str]]:
    """Build the segment artifacts and the visual-intent inventory inputs."""

    documents: list[tuple[str, dict]] = []
    visual_items: list[dict[str, object]] = []
    written: list[str] = []

    for brief in SEGMENT_BRIEFS:
        paths, bundle = write_worker_bee_sketch(
            brief,
            output_dir=str(OUTPUT_DIR),
            overwrite=True,
        )
        documents.append((bundle.page_id, bundle.document))
        visual_items.append(
            {
                "page_id": bundle.page_id,
                "title": bundle.document.get("title", bundle.page_id),
                "segment_label": bundle.segment_label,
                "value_angle_label": bundle.value_angle_label,
                "visualization": {
                    "ascii_sketch_required": True,
                    "ascii_sketch_path": _display_path(paths.sketch_path),
                    "sketch_type": "layout_flow",
                    "sketch_status": "approved" if bundle.report.get("passed") else "needs_attention",
                    "zone_taxonomy_path": _display_path(paths.zones_path),
                    "box_model_path": _display_path(paths.boxes_path),
                    "visual_coherence_status": "aligned" if bundle.report.get("passed") else "drifted",
                },
                "notes": [
                    f"Coherence score: {bundle.report.get('score', 0.0):.1f}%",
                    "The sketch, zone taxonomy, box model, and coherence report are derived from one brief.",
                ],
            }
        )
        written.extend(
            [
                _display_path(paths.sketch_path),
                _display_path(paths.zones_path),
                _display_path(paths.boxes_path),
                _display_path(paths.html_path),
                _display_path(paths.css_path),
                _display_path(paths.svg_path),
                _display_path(paths.coherence_path),
            ]
        )
    return documents, visual_items, written


def main() -> int:
    """Write the segment zone taxonomies and the reuse inventory report."""

    documents, visual_items, written = build_segment_documents()

    paths, inventory = write_layout_inventory_report(documents, output=str(INVENTORY_PATH), overwrite=True)
    written.extend([str(paths.schema_path), str(paths.data_path), str(paths.markdown_path)])

    visual_paths, visual_inventory = write_visual_intent_inventory_report(
        visual_items,
        output=str(VISUAL_INVENTORY_PATH),
        overwrite=True,
    )
    written.extend([str(visual_paths.schema_path), str(visual_paths.data_path), str(visual_paths.markdown_path)])

    print("generated: " + ", ".join(written))
    print(inventory["summary"])
    print(visual_inventory["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
