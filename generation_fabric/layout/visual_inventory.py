"""Visual-intent inventory for ASCII-first layout governance.

This module turns page-level sketch lineage into a contract-backed inventory.
It answers the questions raised in the ASCII-first governance doc: does the
inventory item have a sketch, is the sketch current, does the implementation
match the sketch, and is the visual path still aligned? The report is rendered
through the existing Markdown pipeline so the inventory itself remains a
derived artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from generation_fabric.core.artifacts import ContractArtifact, SidecarPaths, resolve_sidecar_paths, write_contract_artifact
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node


VisualIntentInventoryPaths = SidecarPaths


def _normalize_text(value: Any) -> str:
    """Render a stable inventory string."""

    return " ".join(str(value).split()).strip()


def _normalize_visualization(item: dict[str, Any]) -> dict[str, Any]:
    """Return a stable visualization record for one inventory item."""

    raw = item.get("visualization", {}) if isinstance(item, dict) else {}
    visualization = raw if isinstance(raw, dict) else {}
    return {
        "ascii_sketch_required": bool(visualization.get("ascii_sketch_required", False)),
        "ascii_sketch_path": _normalize_text(visualization.get("ascii_sketch_path", "")),
        "sketch_type": _normalize_text(visualization.get("sketch_type", "")),
        "sketch_status": _normalize_text(visualization.get("sketch_status", "missing")) or "missing",
        "zone_taxonomy_path": _normalize_text(visualization.get("zone_taxonomy_path", "")),
        "box_model_path": _normalize_text(visualization.get("box_model_path", "")),
        "visual_coherence_status": _normalize_text(visualization.get("visual_coherence_status", "missing")) or "missing",
    }


def build_visual_intent_inventory(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a visual-intent inventory from page-level artifact records."""

    if not items:
        raise SchemaError("visual intent inventory needs at least one inventory item")

    normalized_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        visualization = _normalize_visualization(item)
        normalized_items.append(
            {
                "page_id": _normalize_text(item.get("page_id", "")),
                "title": _normalize_text(item.get("title", "")),
                "segment_label": _normalize_text(item.get("segment_label", "")),
                "value_angle_label": _normalize_text(item.get("value_angle_label", "")),
                "visualization": visualization,
                "notes": [str(note) for note in item.get("notes", []) if str(note).strip()],
            }
        )

    if not normalized_items:
        raise SchemaError("visual intent inventory needs at least one valid item")

    total_items = len(normalized_items)
    sketch_required = sum(1 for item in normalized_items if item["visualization"]["ascii_sketch_required"])
    approved = sum(
        1
        for item in normalized_items
        if item["visualization"]["sketch_status"] == "approved"
        and item["visualization"]["visual_coherence_status"] == "aligned"
    )
    drifted = total_items - approved
    sketch_coverage = round((sketch_required / total_items) * 100, 1) if total_items else 0.0
    sketch_statuses = [item["visualization"]["sketch_status"] for item in normalized_items]
    coherence_statuses = [item["visualization"]["visual_coherence_status"] for item in normalized_items]

    summary = (
        f"{total_items} inventory item(s) reviewed. "
        f"{approved} approved sketches, {drifted} needing attention, "
        f"{sketch_coverage:.1f}% sketch coverage."
    )

    return {
        "summary": summary,
        "coverage": {
            "total_items": total_items,
            "sketch_required": sketch_required,
            "approved": approved,
            "drifted": drifted,
            "sketch_coverage": sketch_coverage,
        },
        "items": normalized_items,
        "missing_sketches": [
            item["page_id"]
            for item in normalized_items
            if not item["visualization"]["ascii_sketch_required"] or not item["visualization"]["ascii_sketch_path"]
        ],
        "drifted_items": [
            item["page_id"]
            for item in normalized_items
            if item["visualization"]["sketch_status"] != "approved"
            or item["visualization"]["visual_coherence_status"] != "aligned"
        ],
        "status_histogram": {
            "sketch_statuses": sketch_statuses,
            "coherence_statuses": coherence_statuses,
        },
    }


def build_visual_intent_inventory_document(inventory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the Markdown report contract and data for a visual-intent inventory."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Visual Intent Inventory",
        "description": "Inventory of sketch lineage and visual coherence for ASCII-first governance.",
        "type": "object",
        "properties": {
            "summary": {"type": "string", "x-markdown": {"kind": "paragraph"}},
            "coverage": {
                "type": "object",
                "properties": {
                    "total_items": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "sketch_required": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "approved": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "drifted": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "sketch_coverage": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                },
                "required": ["total_items", "sketch_required", "approved", "drifted", "sketch_coverage"],
                "x-markdown": {"kind": "section", "heading": "Coverage Metrics"},
            },
            "items_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "title": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "segment_label": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "value_angle_label": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "visualization": {
                            "type": "object",
                            "properties": {
                                "ascii_sketch_required": {
                                    "type": "boolean",
                                    "x-markdown": {"kind": "paragraph", "label": True},
                                },
                                "ascii_sketch_path": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph", "label": True},
                                },
                                "sketch_type": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph", "label": True},
                                },
                                "sketch_status": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph", "label": True},
                                },
                                "zone_taxonomy_path": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph", "label": True},
                                },
                                "box_model_path": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph", "label": True},
                                },
                        "visual_coherence_status": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph", "label": True},
                        },
                    },
                            "required": [
                                "ascii_sketch_required",
                                "ascii_sketch_path",
                                "sketch_type",
                                "sketch_status",
                                "zone_taxonomy_path",
                            "box_model_path",
                            "visual_coherence_status",
                        ],
                        "x-markdown": {"kind": "section", "heading": "Visualization"},
                    },
                        "notes": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                    },
                    "required": [
                        "page_id",
                        "title",
                        "segment_label",
                        "value_angle_label",
                        "visualization",
                            "notes",
                    ],
                    "x-markdown": {"kind": "section"},
                },
                "x-markdown": {"kind": "section", "heading": "Inventory Items", "item_heading": "Inventory Item"},
            },
        },
        "required": ["summary", "coverage", "items"],
        "additionalProperties": False,
    }
    validate_schema_node(schema)

    coverage = inventory.get("coverage", {})
    data = {
        "summary": inventory.get("summary", ""),
        "coverage": {
            "total_items": str(coverage.get("total_items", 0)),
            "sketch_required": str(coverage.get("sketch_required", 0)),
            "approved": str(coverage.get("approved", 0)),
            "drifted": str(coverage.get("drifted", 0)),
            "sketch_coverage": f"{float(coverage.get('sketch_coverage', 0.0)):.1f}%",
        },
        "items": [
            {
                "page_id": item["page_id"],
                "title": item["title"],
                "segment_label": item["segment_label"],
                "value_angle_label": item["value_angle_label"],
                "visualization": {
                    "ascii_sketch_required": item["visualization"]["ascii_sketch_required"],
                    "ascii_sketch_path": item["visualization"]["ascii_sketch_path"],
                    "sketch_type": item["visualization"]["sketch_type"],
                    "sketch_status": item["visualization"]["sketch_status"],
                    "zone_taxonomy_path": item["visualization"]["zone_taxonomy_path"],
                    "box_model_path": item["visualization"]["box_model_path"],
                    "visual_coherence_status": item["visualization"]["visual_coherence_status"],
                },
                "notes": list(item["notes"]) or ["(no notes)"],
            }
            for item in inventory.get("items", [])
        ],
    }
    validate_instance_against_schema(schema, data)
    return schema, data


def _resolve_inventory_path(output: str) -> Path:
    """Resolve the Markdown report output path."""

    if output:
        path = Path(output)
        if not path.suffix:
            path = path.with_suffix(".md")
        return path
    return Path("generated") / "visual-intent-inventory.md"


def write_visual_intent_inventory_report(
    items: list[dict[str, Any]],
    *,
    output: str = "",
    overwrite: bool = False,
) -> tuple[VisualIntentInventoryPaths, dict[str, Any]]:
    """Build a visual-intent inventory and write the report plus sidecars."""

    inventory = build_visual_intent_inventory(items)
    report_schema, report_data = build_visual_intent_inventory_document(inventory)
    markdown = render_markdown_document(report_schema, report_data)

    markdown_path = _resolve_inventory_path(output)
    paths = resolve_sidecar_paths("", markdown_path)
    artifact = ContractArtifact(schema=report_schema, data=report_data, primary_text=markdown)
    write_contract_artifact(paths, artifact, overwrite=overwrite)
    paths = VisualIntentInventoryPaths(schema_path=paths.schema_path, data_path=paths.data_path, primary_path=paths.primary_path)
    return paths, inventory
