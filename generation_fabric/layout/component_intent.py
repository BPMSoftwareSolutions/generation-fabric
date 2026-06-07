"""Component intent extraction for the ASCII-to-web pipeline.

A layout zone says *where* a region sits; a component intent says *what it is* —
a form, a data grid, a chart, a gauge, a metric tile. This module reads the
component dialect embedded in zone labels and detail lines and produces a
deterministic, validated component-intent contract that the web HTML/CSS/SVG
renderers and the coherence audit consume.

Dialect (all optional; a plain label still parses):

    LABEL [component_type]      # declares the component family for a zone
    fields: name,email,status   # form controls
    columns: id,name,status     # table / data-grid columns
    data: runs[]                # collection binding
    value: delivery_health      # metric / gauge binding
    x: day y: success_rate      # chart axes (multiple key:value per line)
    min: 0 max: 100             # gauge range
    action: apply_filters       # a user action
    variant: compact            # styling intent
    role: region                # explicit landmark role

Unknown or absent component hints never hallucinate UI: the zone becomes a
``container`` and a warning is recorded with source-line evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

# Component families supported by the renderers. Unknown hints degrade to
# ``container`` with a warning rather than inventing markup.
COMPONENT_FAMILIES: dict[str, tuple[str, ...]] = {
    "layout": (
        "page", "region", "container", "stack", "grid", "card", "toolbar",
        "sidebar", "header", "footer", "modal", "drawer", "tabs",
    ),
    "forms": (
        "form", "fieldset", "text_input", "select", "checkbox", "radio",
        "date_picker", "button", "search",
    ),
    "data": ("table", "data_grid", "list", "detail_panel", "metric_tile", "metrics_strip"),
    "visualization": ("chart_bar", "chart_line", "chart_pie", "sparkline", "gauge", "progress", "kpi"),
    "widgets": (
        "filter_panel", "upload", "pagination", "notification", "timeline",
        "map", "media", "code_block",
    ),
}
SUPPORTED_COMPONENT_TYPES: frozenset[str] = frozenset(
    component for family in COMPONENT_FAMILIES.values() for component in family
)
DEFAULT_COMPONENT_TYPE = "container"

# Landmark role defaults per component type (only where a stable role applies).
ROLE_BY_TYPE: dict[str, str] = {
    "page": "main",
    "header": "banner",
    "footer": "contentinfo",
    "sidebar": "complementary",
    "toolbar": "toolbar",
    "tabs": "tablist",
    "modal": "dialog",
    "drawer": "dialog",
    "search": "search",
    "filter_panel": "search",
}

_COMPONENT_HINT_RE = re.compile(r"\[([a-z0-9_]+)\]\s*$", re.IGNORECASE)
_KEY_VALUE_RE = re.compile(r"(?P<key>[A-Za-z_][\w-]*)\s*:\s*(?P<value>.*?)(?=\s+[A-Za-z_][\w-]*\s*:|$)")


@dataclass(frozen=True)
class ComponentField:
    """A form control derived from a ``fields:`` line."""

    name: str
    label: str
    type: str = "text"

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "label": self.label, "type": self.type}


@dataclass(frozen=True)
class ComponentColumn:
    """A data-grid / table column derived from a ``columns:`` line."""

    name: str
    label: str
    type: str = "text"

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "label": self.label, "type": self.type}


@dataclass(frozen=True)
class ComponentAction:
    """A user action derived from an ``action:`` line."""

    name: str
    label: str
    target: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "label": self.label, "target": self.target}


@dataclass(frozen=True)
class ComponentDataBinding:
    """A collection or record binding derived from a ``data:`` line."""

    source: str
    item_name: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "item_name": self.item_name}


@dataclass(frozen=True)
class ComponentIntent:
    """A single component intent extracted from a layout zone."""

    component_id: str
    zone_id: str
    component_type: str
    label: str
    role: str
    variant: str
    data: ComponentDataBinding | None
    fields: tuple[ComponentField, ...]
    columns: tuple[ComponentColumn, ...]
    actions: tuple[ComponentAction, ...]
    measures: dict[str, str]
    accessibility: dict[str, str]
    warnings: tuple[str, ...]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "zone_id": self.zone_id,
            "component_type": self.component_type,
            "label": self.label,
            "role": self.role,
            "variant": self.variant,
            "data": self.data.to_dict() if self.data else None,
            "fields": [item.to_dict() for item in self.fields],
            "columns": [item.to_dict() for item in self.columns],
            "actions": [item.to_dict() for item in self.actions],
            "measures": dict(self.measures),
            "accessibility": dict(self.accessibility),
            "warnings": list(self.warnings),
            "evidence": dict(self.evidence),
        }


def _slugify(text: str) -> str:
    """Turn arbitrary text into a stable identifier fragment."""

    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "component"


def _humanize(identifier: str) -> str:
    """Turn a snake/slug identifier into a readable label."""

    words = [word for word in re.split(r"[\s_-]+", identifier.strip()) if word]
    return " ".join(word.capitalize() for word in words) if words else identifier.strip()


def _parse_key_values(line: str) -> list[tuple[str, str]]:
    """Parse one or more ``key: value`` pairs from a single detail line."""

    pairs: list[tuple[str, str]] = []
    for match in _KEY_VALUE_RE.finditer(line):
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if key:
            pairs.append((key, value))
    return pairs


def _split_list(value: str) -> list[str]:
    """Split a comma-separated metadata value into clean tokens."""

    return [token.strip() for token in value.split(",") if token.strip()]


def _binding_from_value(value: str) -> ComponentDataBinding:
    """Build a data binding from a ``data:`` value such as ``runs[]``."""

    source = value.strip()
    collection = source[:-2] if source.endswith("[]") else source
    collection = collection.strip()
    item_name = collection[:-1] if len(collection) > 1 and collection.endswith("s") else collection
    return ComponentDataBinding(source=source or "items[]", item_name=item_name or "item")


def _component_type_from_label(label: str) -> tuple[str, str]:
    """Return (clean_label, component_type) parsed from a zone label."""

    match = _COMPONENT_HINT_RE.search(label)
    if not match:
        return label.strip(), ""
    component_type = match.group(1).strip().lower()
    clean_label = label[: match.start()].strip()
    return clean_label or label.strip(), component_type


def _resolve_role(component_type: str, explicit_role: str) -> str:
    """Resolve the landmark role for a component."""

    if explicit_role:
        return explicit_role
    return ROLE_BY_TYPE.get(component_type, "region")


def build_component_intent(zone: dict[str, Any]) -> ComponentIntent:
    """Build one component intent from a single zone dictionary."""

    zone_id = str(zone.get("zone_id", "")) or "zone"
    raw_label = str(zone.get("label", "")).strip()
    clean_label, component_type = _component_type_from_label(raw_label)

    warnings: list[str] = []
    if not component_type:
        component_type = DEFAULT_COMPONENT_TYPE
        warnings.append(f"zone '{zone_id}' has no component hint; defaulted to container")
    elif component_type not in SUPPORTED_COMPONENT_TYPES:
        warnings.append(
            f"zone '{zone_id}' uses unsupported component type '{component_type}'; rendered as container"
        )
        component_type = DEFAULT_COMPONENT_TYPE

    variant = ""
    explicit_role = ""
    data: ComponentDataBinding | None = None
    fields: list[ComponentField] = []
    columns: list[ComponentColumn] = []
    actions: list[ComponentAction] = []
    measures: dict[str, str] = {}

    details = zone.get("details", [])
    detail_lines = list(details) if isinstance(details, list) else []
    for line in detail_lines:
        for key, value in _parse_key_values(str(line)):
            if not value:
                continue
            if key == "fields":
                fields.extend(ComponentField(name=name, label=_humanize(name)) for name in _split_list(value))
            elif key == "columns":
                columns.extend(ComponentColumn(name=name, label=_humanize(name)) for name in _split_list(value))
            elif key == "data":
                data = _binding_from_value(value)
            elif key == "action":
                actions.append(ComponentAction(name=value, label=_humanize(value)))
            elif key == "variant":
                variant = value
            elif key == "role":
                explicit_role = value
            elif key in {"value", "min", "max", "x", "y", "measure", "unit"}:
                measures[key] = value
            # h1/title and other keys are descriptive only; ignored deterministically.

    role = _resolve_role(component_type, explicit_role)
    accessibility = {"aria_label": clean_label or _humanize(zone_id)}

    bounds = zone.get("bounds", {}) if isinstance(zone.get("bounds"), dict) else {}
    evidence = {
        "source": "ascii",
        "zone_id": zone_id,
        "band": int(bounds.get("band", 0)),
    }

    return ComponentIntent(
        component_id=f"component-{_slugify(clean_label or zone_id)}",
        zone_id=zone_id,
        component_type=component_type,
        label=clean_label or _humanize(zone_id),
        role=role,
        variant=variant,
        data=data,
        fields=tuple(fields),
        columns=tuple(columns),
        actions=tuple(actions),
        measures=measures,
        accessibility=accessibility,
        warnings=tuple(warnings),
        evidence=evidence,
    )


def build_component_intent_schema() -> dict[str, Any]:
    """Build the canonical component-intent contract."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Component Intent",
        "description": "Component intent extracted from a layout zone taxonomy for the ASCII-to-web pipeline.",
        "type": "object",
        "properties": {
            "page_id": {"type": "string"},
            "title": {"type": "string"},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "component_id": {"type": "string"},
                        "zone_id": {"type": "string"},
                        "component_type": {"type": "string"},
                        "label": {"type": "string"},
                        "role": {"type": "string"},
                        "variant": {"type": "string"},
                        "data": {
                            "type": ["object", "null"],
                            "properties": {
                                "source": {"type": "string"},
                                "item_name": {"type": "string"},
                            },
                            "required": ["source", "item_name"],
                            "additionalProperties": False,
                        },
                        "fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "label": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                                "required": ["name", "label", "type"],
                                "additionalProperties": False,
                            },
                        },
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "label": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                                "required": ["name", "label", "type"],
                                "additionalProperties": False,
                            },
                        },
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "label": {"type": "string"},
                                    "target": {"type": "string"},
                                },
                                "required": ["name", "label", "target"],
                                "additionalProperties": False,
                            },
                        },
                        "measures": {"type": "object"},
                        "accessibility": {"type": "object"},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "object"},
                    },
                    "required": [
                        "component_id",
                        "zone_id",
                        "component_type",
                        "label",
                        "role",
                        "fields",
                        "columns",
                        "actions",
                    ],
                    "additionalProperties": True,
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["page_id", "components"],
        "additionalProperties": True,
    }
    validate_schema_node(schema)
    return schema


def build_component_intent_document(zones_document: dict[str, Any]) -> dict[str, Any]:
    """Build and validate a component-intent document from a zone taxonomy document."""

    if not isinstance(zones_document, dict):
        raise SchemaError("component intent needs a zone taxonomy document")

    zones = zones_document.get("zones", [])
    if not isinstance(zones, list) or not zones:
        raise SchemaError("zone taxonomy document has no zones")

    components = [build_component_intent(zone) for zone in zones if isinstance(zone, dict)]
    warnings = [warning for component in components for warning in component.warnings]

    document = {
        "page_id": str(zones_document.get("page_id", "layout-sketch")),
        "title": str(zones_document.get("title", "")),
        "components": [component.to_dict() for component in components],
        "warnings": warnings,
    }

    schema = build_component_intent_schema()
    validate_instance_against_schema(schema, document)
    return document
