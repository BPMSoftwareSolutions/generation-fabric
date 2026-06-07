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
