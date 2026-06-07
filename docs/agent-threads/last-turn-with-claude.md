What's now live: one contract → four artifacts + audit

                         ASCII sketch
                              │ parse
                              ▼
                    zone taxonomy contract
        (x-html · x-css · x-svg annotations, one JSON Schema)
            │           │           │              │
         x-html      x-css        x-svg      (audit renders)
            ▼           ▼           ▼              ▼
          HTML        CSS         SVG       coherence report
                                              (Markdown, via
                                            the existing renderer)
Phase 2 — CSS + SVG targets
css/renderer.py: projects each zone into a box-model ownership rule — [data-zone-id="hero"] { grid-column: 1 / -1 }, split bands → 1 / 7 and 7 / -1, spacing tokens in :root, and a responsive media query that collapses to single-column. Grid placement comes straight from the parsed bounds.
svg/renderer.py: draws a <rect> + label per zone from the character bounds (scaled to pixels), color-coded by layout_role.
The canonical contract now carries all three namespaces; a shared find_zone_list() keeps zone discovery in one place. Commands: layout-css, layout-svg. Goldens: value-simulator.css, value-simulator.svg.
Phase 3 — Coherence audit
layout/coherence.py: 10 deterministic checks (unique ids, labels, bounds, reading order, and that HTML/CSS/SVG each preserve every zone), scored, then rendered as a Markdown report through the existing Markdown renderer — the fabric audits itself with its own pipeline. Command: layout-coherence (exit 1 on any failure). Golden: value-simulator.coherence.md (100%).
Phase 4 — worker-bee-sketch
worker_bee/layout_sketch.py: brief → segment (5 GTM segments) + value angle (5 value levers) by keyword → draws an aligned ASCII box (render_box with ┬/┴/┼ junctions + fit/truncate) → renders all four targets + coherence. Verified end-to-end: "MSP consultancy … delivery acceleration" → msp-consultancy.delivery-acceleration, 6 artifacts, 100% coherence. Command: worker-bee-sketch.
Notes
One layering fix worth flagging: coherence depends on the css/svg renderers, which depend on layout — so importing coherence from layout/__init__.py created a circular import. I kept the correct layering: coherence lives in layout/coherence.py but is imported from the submodule, not re-exported from the package init. (Saved to memory.)
README stayed a rendered artifact — I edited the contract source (readme.json/readme.schema.json) and re-rendered, never the derived file. module-map.md updated too.
The committed coherence report ships with its schema/json sidecars, matching the repo's "real, committed artifacts" convention.
The only remaining item from the original vision is the nested box-model contract (*.boxes.json) for richer responsive ownership, plus the doc's segment-comparison/reuse inventory — flagged as TODO in memory. Want me to take the box-model phase next, or is this a good place to pause and commit?

I've committed and pushed the changes. Let's proceed with the remaining work.
The user pushed and wants to continue. The remaining work from the plan is the box-model contract (*.boxes.json) and the segment reuse inventory. Let me set up the todos and build both, keeping the same tested-and-documented discipline.

Update Todos

Build layout/box_model.py (nested box hierarchy from zones) + canonical schema

Wire layout-boxes CLI command + golden boxes.json example

Integrate box-model checks into coherence audit + regenerate coherence golden

Build layout/inventory.py (zone reuse across pages) + report via markdown renderer

Wire layout-inventory CLI + scripts/generate_segment_examples.py + golden segment examples

Write tests for box-model and inventory

Update README contract source + module-map, re-render, run full suite
Write c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\layout\box_model.py
176 lines
"""Derive a governed box model from a layout zone taxonomy.

The flat zone taxonomy answers "what are the value-carrying regions?". The box
model answers "how do those regions nest, own CSS, and behave responsively?".
It is the bridge between zones and measurable CSS: each box names a surface
class, declares responsive behavior, and lists the alignment checks it must
satisfy. The page becomes a tree of boxes (page -> band rows -> zone surfaces)
expressed as a flat, validated list with parent/contains references.
"""

from __future__ import annotations

from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

ROOT_BOX_ID = "page"

LEAF_ALIGNMENT_CHECKS = (
    "has_named_surface_class",
    "uses_spacing_tokens",
    "does_not_use_inline_style",
    "preserves_reading_order",
)
BAND_ALIGNMENT_CHECKS = ("uses_spacing_tokens", "preserves_reading_order")
ROOT_ALIGNMENT_CHECKS = ("preserves_reading_order",)


def _band_layout_type(zone_count: int) -> str:
    """Name a band's layout type from how many zones it holds."""

    if zone_count <= 1:
        return "single_column"
    if zone_count == 2:
        return "two_column"
    return "multi_column"


def _band_responsive_behavior(zone_count: int) -> dict[str, str]:
    """Describe how a band collapses across breakpoints."""

    if zone_count <= 1:
        return {"desktop": "single_column", "tablet": "single_column", "mobile": "single_column"}
    return {"desktop": _band_layout_type(zone_count), "tablet": "stacked", "mobile": "single_column"}


def build_box_model_schema() -> dict[str, Any]:
    """Build the canonical box-model contract."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Layout Box Model",
        "description": "Nested box model derived from a layout zone taxonomy. Each box owns a CSS surface class and responsive behavior.",
        "type": "object",
        "properties": {
            "page_id": {"type": "string"},
            "title": {"type": "string"},
            "boxes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "box_id": {"type": "string"},
                        "parent_box": {"type": "string"},
                        "layout_type": {"type": "string"},
                        "contains": {"type": "array", "items": {"type": "string"}},
                        "css_class": {"type": "string"},
                        "responsive_behavior": {
                            "type": "object",
                            "properties": {
                                "desktop": {"type": "string"},
                                "tablet": {"type": "string"},
                                "mobile": {"type": "string"},
                            },
                            "required": ["desktop", "tablet", "mobile"],
                            "additionalProperties": False,
                        },
                        "alignment_checks": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "box_id",
                        "parent_box",
                        "layout_type",
                        "contains",
                        "css_class",
                        "responsive_behavior",
                        "alignment_checks",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["page_id", "boxes"],
        "additionalProperties": False,
    }
    validate_schema_node(schema)
    return schema


def build_box_model_document(zones_document: dict[str, Any]) -> dict[str, Any]:
    """Derive and validate a box-model document from a zone taxonomy document."""

    if not isinstance(zones_document, dict):
        raise SchemaError("zone taxonomy document must be a JSON object")

    zones = zones_document.get("zones", [])
    if not isinstance(zones, list) or not zones:
        raise SchemaError("zone taxonomy document has no zones")

    page_id = str(zones_document.get("page_id", "layout-sketch"))
    title = str(zones_document.get("title", ""))

    bands: dict[int, list[dict[str, Any]]] = {}
    band_order: list[int] = []
    for zone in zones:
        band = int(zone.get("bounds", {}).get("band", 0))
        if band not in bands:
            bands[band] = []
            band_order.append(band)
        bands[band].append(zone)

    boxes: list[dict[str, Any]] = [
        {
            "box_id": ROOT_BOX_ID,
            "parent_box": "",
            "layout_type": "stack",
            "contains": [f"band-{band}" for band in band_order],
            "css_class": "layout",
            "responsive_behavior": {"desktop": "stack", "tablet": "stack", "mobile": "stack"},
            "alignment_checks": list(ROOT_ALIGNMENT_CHECKS),
        }
    ]

    for band in band_order:
        band_zones = bands[band]
        zone_count = len(band_zones)
        band_box_id = f"band-{band}"
        boxes.append(
            {
                "box_id": band_box_id,
                "parent_box": ROOT_BOX_ID,
                "layout_type": _band_layout_type(zone_count),
                "contains": [str(zone.get("zone_id", "")) for zone in band_zones],
                "css_class": f"band band--row-{band}",
                "responsive_behavior": _band_responsive_behavior(zone_count),
                "alignment_checks": list(BAND_ALIGNMENT_CHECKS),
            }
        )
        for zone in band_zones:
            zone_id = str(zone.get("zone_id", ""))
            boxes.append(
                {
                    "box_id": zone_id,
                    "parent_box": band_box_id,
                    "layout_type": "surface",
                    "contains": [],
                    "css_class": f"surface surface--{zone_id}",
                    "responsive_behavior": {"desktop": "full", "tablet": "full", "mobile": "full"},
                    "alignment_checks": list(LEAF_ALIGNMENT_CHECKS),
                }
            )

    document = {"page_id": page_id, "title": title, "boxes": boxes}
    schema = build_box_model_schema()
    validate_instance_against_schema(schema, document)
    return document


def leaf_boxes(box_model_document: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the surface (leaf) boxes from a box-model document."""

    boxes = box_model_document.get("boxes", []) if isinstance(box_model_document, dict) else []
    return [box for box in boxes if box.get("layout_type") == "surface"]
Now export from the layout package (box_model has no css/svg deps, so it's safe in __init__):

Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\layout\__init__.py
Added 5 lines
Now wire the layout-boxes CLI command. Add the import, handler, and subparser:

Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\cli.py
Added 1 line
Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\cli.py
Added 16 lines
Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\cli.py
Added 13 lines
Now integrate box-model checks into the coherence audit:

Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\layout\coherence.py
Added 1 line
Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\layout\coherence.py
Added 9 lines
Box-model wired and integrated into coherence. Let me smoke-test imports, then generate the box-model golden and regenerate the coherence golden (now 12 checks):

PowerShell
IN
{
  "command": "$env:PYTHONUTF8 = \"1\"\n$py = \"C:\\Users\\Sidney Jones\\AppData\\Local\\Microsoft\\WindowsApps\\python3.12.exe\"\nSet-Location \"c:\\Users\\Sidney Jones\\OneDrive - bpmsoftwaresolutions.com\\Documents\\Generation Fabric\"\n& $py -c \"import generation_fabric.cli as c; c.build_parser(); print('imports OK')\"\n& $py json_schema_crud.py layout-boxes --data-file examples/value-simulator.zones.json --output examples/value-simulator.boxes.json --overwrite\n& $py json_schema_crud.py layout-coherence --data-file examples/value-simulator.zones.json --output examples/value-simulator.coherence.md --overwrite",
  "description": "Generate box-model golden and regenerate coherence golden"
}
OUT
imports OK
box model written: examples\value-simulator.boxes.json
derived 13 boxes
layout coherence report written: examples\value-simulator.coherence.md
generated: examples\value-simulator.coherence.schema.json, examples\value-simulator.coherence.json, examples\value-simulator.coherence.md
12/12 coherence checks passed across 7 zones. (100.0% coherence)
13 boxes (1 page + 5 bands + 7 surfaces), coherence now 12/12. Let me verify the box-model structure:

Read c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\value-simulator.boxes.json
Box model is correct. Now Phase 6 — the reuse inventory. Let me first check how the existing generator-script + test pattern works so I mirror it for the segment examples:

Read c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\scripts\generate_table_showcase.py
Grep "table_showcase_is_generated|raw_sections_showcase_is_generated" (in c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\tests\test_json_schema_crud.py)
47 lines of output
I have the generator-script pattern. Now let me build the inventory module:

Write c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\layout\inventory.py
238 lines
"""Layout reuse inventory across multiple zone taxonomies.

This is the "design reuse before code reuse" layer from the ASCII-first vision.
Given several zone taxonomies (for example one per market segment), it reports
which zones repeat across pages, which carry page-specific content, and which
are unique. The result is rendered as a Markdown report through the existing
Markdown renderer, so the inventory itself is a derived, contract-backed
artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node


@dataclass(frozen=True)
class InventoryReportPaths:
    """Describe the files produced by the reuse inventory."""

    schema_path: Path
    data_path: Path
    markdown_path: Path


def _reuse_class(page_count: int, total_pages: int) -> str:
    """Classify a zone's reuse based on how many pages it appears in."""

    if total_pages > 1 and page_count >= total_pages:
        return "shared"
    if page_count > 1:
        return "common"
    return "unique"


def build_layout_inventory(documents: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Build a reuse inventory from named zone taxonomy documents."""

    if not documents:
        raise SchemaError("layout inventory needs at least one zone taxonomy document")

    pages: list[str] = []
    for name, _document in documents:
        candidate = name
        suffix = 2
        while candidate in pages:
            candidate = f"{name}-{suffix}"
            suffix += 1
        pages.append(candidate)

    order: list[str] = []
    zone_pages: dict[str, list[str]] = {}
    zone_labels: dict[str, list[str]] = {}
    zone_roles: dict[str, list[str]] = {}

    for page_name, (_name, document) in zip(pages, documents):
        zones = document.get("zones", []) if isinstance(document, dict) else []
        for zone in zones:
            zone_id = str(zone.get("zone_id", ""))
            if not zone_id:
                continue
            if zone_id not in zone_pages:
                order.append(zone_id)
                zone_pages[zone_id] = []
                zone_labels[zone_id] = []
                zone_roles[zone_id] = []
            if page_name not in zone_pages[zone_id]:
                zone_pages[zone_id].append(page_name)
            label = str(zone.get("label", ""))
            if label and label not in zone_labels[zone_id]:
                zone_labels[zone_id].append(label)
            role = str(zone.get("layout_role", ""))
            if role and role not in zone_roles[zone_id]:
                zone_roles[zone_id].append(role)

    total_pages = len(pages)
    zones_inventory: list[dict[str, Any]] = []
    for zone_id in order:
        page_count = len(zone_pages[zone_id])
        zones_inventory.append(
            {
                "zone_id": zone_id,
                "reuse_class": _reuse_class(page_count, total_pages),
                "page_count": page_count,
                "content_variants": len(zone_labels[zone_id]),
                "layout_role": "/".join(zone_roles[zone_id]) or "",
                "pages": list(zone_pages[zone_id]),
                "labels": list(zone_labels[zone_id]),
            }
        )

    shared = [zone["zone_id"] for zone in zones_inventory if zone["reuse_class"] == "shared"]
    common = [zone["zone_id"] for zone in zones_inventory if zone["reuse_class"] == "common"]
    unique = [zone["zone_id"] for zone in zones_inventory if zone["reuse_class"] == "unique"]
    content_varying = [zone["zone_id"] for zone in zones_inventory if zone["content_variants"] > 1]

    total_zones = len(order)
    structural_reuse = round((len(shared) + len(common)) / total_zones * 100, 1) if total_zones else 0.0

    summary = (
        f"{total_pages} pages compared. "
        f"{len(shared)} of {total_zones} zones are shared across all pages, "
        f"{len(common)} common, {len(unique)} page-specific. "
        f"{len(content_varying)} zones carry page-specific content."
    )

    return {
        "pages": pages,
        "summary": summary,
        "metrics": {
            "total_pages": total_pages,
            "total_zones": total_zones,
            "shared": len(shared),
            "common": len(common),
            "unique": len(unique),
            "content_varying": len(content_varying),
            "structural_reuse_percent": structural_reuse,
        },
        "zones": zones_inventory,
        "reuse_candidates": shared + common,
        "page_specific": unique,
    }


def build_inventory_report_document(inventory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a Markdown report contract and data from a reuse inventory."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Layout Reuse Inventory",
        "description": "Zone reuse across multiple layout taxonomies, for design reuse before code reuse.",
        "type": "object",
        "properties": {
            "summary": {"type": "string", "x-markdown": {"kind": "paragraph"}},
            "structural_reuse": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
            "pages_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "pages": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
            "zones_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "zones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "zone_id": {"type": "string"},
                        "reuse_class": {"type": "string"},
                        "page_count": {"type": "string"},
                        "content_variants": {"type": "string"},
                        "layout_role": {"type": "string"},
                    },
                    "required": ["zone_id", "reuse_class", "page_count", "content_variants", "layout_role"],
                    "additionalProperties": False,
                },
                "x-markdown": {"kind": "table"},
            },
            "reuse_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "reuse_candidates": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
            "specific_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "page_specific": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
        },
        "required": [
            "summary",
            "structural_reuse",
            "pages_heading",
            "pages",
            "zones_heading",
            "zones",
            "reuse_heading",
            "reuse_candidates",
            "specific_heading",
            "page_specific",
        ],
        "additionalProperties": False,
    }
    validate_schema_node(schema)

    metrics = inventory.get("metrics", {})
    data = {
        "summary": inventory.get("summary", ""),
        "structural_reuse": f"{float(metrics.get('structural_reuse_percent', 0.0)):.1f}%",
        "pages_heading": "Compared Pages",
        "pages": list(inventory.get("pages", [])),
        "zones_heading": "Zone Inventory",
        "zones": [
            {
                "zone_id": zone["zone_id"],
                "reuse_class": zone["reuse_class"],
                "page_count": str(zone["page_count"]),
                "content_variants": str(zone["content_variants"]),
                "layout_role": zone["layout_role"],
            }
            for zone in inventory.get("zones", [])
        ],
        "reuse_heading": "Reuse Candidates",
        "reuse_candidates": list(inventory.get("reuse_candidates", [])) or ["(none)"],
        "specific_heading": "Page-Specific Zones",
        "page_specific": list(inventory.get("page_specific", [])) or ["(none)"],
    }
    validate_instance_against_schema(schema, data)
    return schema, data


def write_layout_inventory_report(
    documents: list[tuple[str, dict[str, Any]]],
    *,
    output: str = "",
    overwrite: bool = False,
) -> tuple[InventoryReportPaths, dict[str, Any]]:
    """Build a reuse inventory and write the report plus its sidecars."""

    inventory = build_layout_inventory(documents)
    report_schema, report_data = build_inventory_report_document(inventory)
    markdown = render_markdown_document(report_schema, report_data)

    markdown_path = Path(output) if output else Path("generated") / "layout-inventory.md"
    if not markdown_path.suffix:
        markdown_path = markdown_path.with_suffix(".md")
    stem = markdown_path.stem
    schema_path = markdown_path.with_name(f"{stem}.schema.json")
    data_path = markdown_path.with_name(f"{stem}.json")

    for target in (schema_path, data_path, markdown_path):
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_json_file_atomic(schema_path, report_schema)
    write_json_file_atomic(data_path, report_data)
    write_text_file_atomic(markdown_path, markdown)

    paths = InventoryReportPaths(schema_path=schema_path, data_path=data_path, markdown_path=markdown_path)
    return paths, inventory
Now wire the layout-inventory CLI command:

Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\cli.py
Added 1 line
Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\cli.py
Added 18 lines
Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\generation_fabric\cli.py
Added 19 lines
Now the generator script for the segment examples (mirroring the existing generate_* scripts):

Write c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\scripts\generate_segment_examples.py
64 lines
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

from generation_fabric.core.io import write_json_file_atomic
from generation_fabric.layout.ascii_sketch import build_zone_document
from generation_fabric.layout.inventory import write_layout_inventory_report
from generation_fabric.worker_bee.layout_sketch import build_segment_value_sketch

OUTPUT_DIR = REPO_ROOT / "examples"
INVENTORY_PATH = OUTPUT_DIR / "segment-inventory.md"

SEGMENT_BRIEFS = (
    "Enterprise engineering organization focused on cost avoidance",
    "MSP consultancy scaling delivery acceleration across many clients",
    "AI platform team focused on compute discipline and reducing model retry waste",
)


def build_segment_documents() -> list[tuple[str, dict]]:
    """Build the segment zone taxonomies in a deterministic order."""

    documents: list[tuple[str, dict]] = []
    for brief in SEGMENT_BRIEFS:
        sketch, page_id, title, _segment_label, _value_headline = build_segment_value_sketch(brief)
        document = build_zone_document(sketch, page_id=page_id, title=title)
        documents.append((document["page_id"], document))
    return documents


def main() -> int:
    """Write the segment zone taxonomies and the reuse inventory report."""

    documents = build_segment_documents()
    written: list[str] = []
    for page_id, document in documents:
        zones_path = OUTPUT_DIR / f"{page_id}.zones.json"
        write_json_file_atomic(zones_path, document)
        written.append(str(zones_path))

    paths, inventory = write_layout_inventory_report(documents, output=str(INVENTORY_PATH), overwrite=True)
    written.extend([str(paths.schema_path), str(paths.data_path), str(paths.markdown_path)])

    print("generated: " + ", ".join(written))
    print(inventory["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
Now run the generator and a smoke test of layout-inventory:

PowerShell
IN
{
  "command": "$env:PYTHONUTF8 = \"1\"\n$py = \"C:\\Users\\Sidney Jones\\AppData\\Local\\Microsoft\\WindowsApps\\python3.12.exe\"\nSet-Location \"c:\\Users\\Sidney Jones\\OneDrive - bpmsoftwaresolutions.com\\Documents\\Generation Fabric\"\n& $py -c \"import generation_fabric.cli as c; c.build_parser(); print('imports OK')\"\n& $py scripts/generate_segment_examples.py",
  "description": "Run segment-examples generator and confirm imports"
}
OUT
imports OK
generated: C:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\enterprise-engineering-cost-avoidance.zones.json, C:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\msp-consultancy-delivery-acceleration.zones.json, C:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\ai-platform-compute-discipline.zones.json, C:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\segment-inventory.schema.json, C:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\segment-inventory.json, C:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\segment-inventory.md
3 pages compared. 7 of 7 zones are shared across all pages, 0 common, 0 page-specific. 3 zones carry page-specific content.
Let me view the inventory report to confirm it renders well:

Read c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\segment-inventory.md
The inventory report tells a true, useful story — 7-zone shared skeleton at 100% structural reuse, with hero/segment/formula carrying 3 content variants each. Now the tests for box-model and inventory:

Update Todos

Build layout/box_model.py (nested box hierarchy from zones) + canonical schema

Wire layout-boxes CLI command + golden boxes.json example

Integrate box-model checks into coherence audit + regenerate coherence golden

Build layout/inventory.py (zone reuse across pages) + report via markdown renderer

Wire layout-inventory CLI + scripts/generate_segment_examples.py + golden segment examples

Write tests for box-model and inventory

Update README contract source + module-map, re-render, run full suite
Write c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\tests\test_layout_box_model.py
88 lines
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
Write c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\tests\test_layout_inventory.py
115 lines
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
        from generation_fabric.markdown.renderer import render_markdown_document

        self.assertEqual(render_markdown_document(schema, data), read_text(INVENTORY_PATH))


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
I need to update the coherence test in test_layout_targets.py (10 → 12 checks now). Let me fix that:

Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\tests\test_layout_targets.py
Added 3 lines
Now run the full suite to validate the new modules and tests:

PowerShell
IN
{
  "command": "$env:PYTHONUTF8 = \"1\"\n$py = \"C:\\Users\\Sidney Jones\\AppData\\Local\\Microsoft\\WindowsApps\\python3.12.exe\"\nSet-Location \"c:\\Users\\Sidney Jones\\OneDrive - bpmsoftwaresolutions.com\\Documents\\Generation Fabric\"\n& $py -m unittest discover -s tests 2>&1 | Select-Object -Last 6",
  "description": "Run full test suite"
}
OUT
python3.12.exe : ............................................................................
At line:4 char:1
+ & $py -m unittest discover -s tests 2>&1 | Select-Object -Last 6
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (.................................:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
----------------------------------------------------------------------
Ran 76 tests in 4.584s
OK
All 76 tests pass (64 + 12 new). Now update the docs. The README is rendered from its contract, so I edit the source. First the schema — new quick-start blocks for layout-boxes and layout-inventory:

Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\readme.schema.json
Added 13 lines
Edit c:\Users\Sidney Jones\OneDrive - bpmsoftwaresolutions.com\Documents\Generation Fabric\examples\readme.schema.json
Added 13 lines
