"""Web page contract builder for the ASCII-to-web pipeline.

The web page contract is the single, normalized source of truth for a page: it
folds the zone taxonomy, the box model, and the component intent into one
validated document. HTML, CSS, and SVG are deterministic projections of this
contract, and the coherence audit checks them against it.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.layout.box_model import build_box_model_document
from generation_fabric.layout.component_intent import build_component_intent_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

WEB_CONTRACT_KIND = "web_page_contract"
WEB_CONTRACT_VERSION = "0.1.0"

REQUIRED_CHECKS = (
    "zone_component_coverage",
    "component_ids_unique",
    "component_type_supported",
    "form_controls_present",
    "data_grid_columns_present",
    "chart_axes_present",
    "gauge_range_present",
    "html_component_traceability",
    "css_component_ownership",
    "svg_component_representation",
    "a11y_labels",
)


def _sketch_hash(source_sketch: str) -> str:
    """Return a stable hash for the source sketch text."""

    return "sha256:" + sha256(source_sketch.encode("utf-8")).hexdigest()


def build_web_page_contract_schema() -> dict[str, Any]:
    """Build the schema that validates a web page contract envelope."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Web Page Contract",
        "description": "Normalized web page contract combining zones, boxes, and component intent.",
        "type": "object",
        "properties": {
            "kind": {"type": "string", "const": WEB_CONTRACT_KIND},
            "version": {"type": "string"},
            "page_id": {"type": "string"},
            "title": {"type": "string"},
            "source_sketch": {
                "type": "object",
                "properties": {"format": {"type": "string"}, "hash": {"type": "string"}},
                "required": ["format", "hash"],
                "additionalProperties": True,
            },
            "zones": {"type": "array", "items": {"type": "object"}},
            "boxes": {"type": "array", "items": {"type": "object"}},
            "components": {"type": "array", "items": {"type": "object"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "render_targets": {"type": "object"},
            "coherence": {
                "type": "object",
                "properties": {"required_checks": {"type": "array", "items": {"type": "string"}}},
                "required": ["required_checks"],
                "additionalProperties": True,
            },
        },
        "required": [
            "kind",
            "version",
            "page_id",
            "source_sketch",
            "zones",
            "boxes",
            "components",
            "render_targets",
            "coherence",
        ],
        "additionalProperties": True,
    }
    validate_schema_node(schema)
    return schema


def build_web_page_contract(
    zones_document: dict[str, Any],
    components_document: dict[str, Any] | None = None,
    boxes_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a web page contract from a zone taxonomy document."""

    if not isinstance(zones_document, dict):
        raise SchemaError("web page contract needs a zone taxonomy document")

    components_document = components_document or build_component_intent_document(zones_document)
    boxes_document = boxes_document or build_box_model_document(zones_document)
    source_sketch = str(zones_document.get("source_sketch", ""))

    contract = {
        "kind": WEB_CONTRACT_KIND,
        "version": WEB_CONTRACT_VERSION,
        "page_id": str(zones_document.get("page_id", "layout-sketch")),
        "title": str(zones_document.get("title", "")),
        "source_sketch": {"format": "ascii", "hash": _sketch_hash(source_sketch)},
        "zones": list(zones_document.get("zones", [])),
        "boxes": list(boxes_document.get("boxes", [])),
        "components": list(components_document.get("components", [])),
        "warnings": list(components_document.get("warnings", [])),
        "render_targets": {
            "html": {"enabled": True, "annotation": "x-html"},
            "css": {"enabled": True, "annotation": "x-css"},
            "svg": {"enabled": True, "annotation": "x-svg"},
        },
        "coherence": {"required_checks": list(REQUIRED_CHECKS)},
    }
    validate_instance_against_schema(build_web_page_contract_schema(), contract)
    return contract


def zone_bounds_index(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map zone_id -> zone (including bounds) for renderer placement."""

    index: dict[str, dict[str, Any]] = {}
    for zone in contract.get("zones", []):
        if isinstance(zone, dict) and zone.get("zone_id"):
            index[str(zone["zone_id"])] = zone
    return index
