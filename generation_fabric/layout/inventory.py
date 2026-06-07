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
