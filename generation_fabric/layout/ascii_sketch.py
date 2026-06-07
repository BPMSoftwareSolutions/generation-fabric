"""Parse ASCII layout sketches into a zone taxonomy contract.

An ASCII sketch is the cheapest authority-bearing design artifact: a box-drawing
diagram that names the value-carrying zones of a page before any HTML/CSS exists.
This module turns that sketch into a structured zone taxonomy that the fabric can
validate and render, mirroring the Markdown importer's "artifact -> contract"
direction.

The supported sketch dialect is a vertical stack of horizontal bands. Horizontal
border lines (``------`` / ``------``) split the sketch into bands, and aligned
vertical bars (``|`` / ``|``) split a band into side-by-side zones. The interior
column separators must line up across the rows of a band, which keeps parsing
deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

HORIZONTAL_CHARS = set("-─━═┄┅╌╍")
VERTICAL_CHARS = set("|│┃║┆┇╎╏")
JUNCTION_CHARS = set(
    "+"
    "┌┐└┘├┤┬┴┼"
    "╔╗╚╝╠╣╦╩╬"
    "╭╮╯╰"
)
BORDER_CHARS = HORIZONTAL_CHARS | VERTICAL_CHARS | JUNCTION_CHARS


@dataclass(frozen=True)
class LayoutZoneBounds:
    """Describe where a zone sits in the source sketch, in character units."""

    band: int
    column: int
    column_count: int
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        """Serialize the bounds into a JSON-friendly mapping."""

        return {
            "band": self.band,
            "column": self.column,
            "column_count": self.column_count,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class LayoutZone:
    """Describe one value-carrying zone parsed from an ASCII sketch."""

    zone_id: str
    label: str
    purpose: str
    layout_role: str
    bounds: LayoutZoneBounds
    details: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the zone into a JSON-friendly mapping."""

        return {
            "zone_id": self.zone_id,
            "label": self.label,
            "purpose": self.purpose,
            "details": list(self.details),
            "layout_role": self.layout_role,
            "bounds": self.bounds.to_dict(),
        }


def _slugify(text: str) -> str:
    """Turn arbitrary label text into a stable zone identifier."""

    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "zone"


def _humanize(slug: str) -> str:
    """Turn a slug back into a readable title."""

    words = [word for word in slug.replace("_", "-").split("-") if word]
    return " ".join(word.capitalize() for word in words) if words else "Layout Sketch"


def _dedent_block(text: str) -> list[str]:
    """Normalize tabs, strip blank edges, and remove common left indentation."""

    raw = [line.replace("\t", "    ") for line in text.replace("\r\n", "\n").split("\n")]
    content_indexes = [index for index, line in enumerate(raw) if line.strip()]
    if not content_indexes:
        return []

    start = content_indexes[0]
    end = content_indexes[-1] + 1
    block = raw[start:end]

    indent = min(len(line) - len(line.lstrip(" ")) for line in block if line.strip())
    return [line[indent:] if len(line) >= indent else line for line in block]


def _is_border_line(line: str) -> bool:
    """Return True when a line is a horizontal divider rather than content."""

    stripped = line.strip()
    if not stripped:
        return False
    if not any(char in HORIZONTAL_CHARS for char in stripped):
        return False
    return all(char == " " or char in BORDER_CHARS for char in stripped)


def _collect_bands(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Group content lines into bands delimited by borders or blank lines."""

    bands: list[tuple[int, list[str]]] = []
    current: list[str] = []
    current_start = -1

    def flush() -> None:
        nonlocal current, current_start
        if current:
            bands.append((current_start, current))
        current = []
        current_start = -1

    for index, line in enumerate(lines):
        if _is_border_line(line) or not line.strip():
            flush()
            continue
        if current_start < 0:
            current_start = index
        current.append(line)

    flush()
    return bands


def _separator_columns(band_lines: list[str], width: int) -> list[int]:
    """Return the columns where every band row carries a vertical bar."""

    return [
        column
        for column in range(width)
        if all(column < len(line) and line[column] in VERTICAL_CHARS for line in band_lines)
    ]


def _cell_spans(band_lines: list[str], width: int) -> list[tuple[int, int]]:
    """Split a band into [start, end) column spans using aligned separators."""

    separators = _separator_columns(band_lines, width)
    if len(separators) < 2:
        return [(0, width)]
    return [(separators[index] + 1, separators[index + 1]) for index in range(len(separators) - 1)]


def _layout_role(column: int, column_count: int) -> str:
    """Name a zone's layout role from its position in the band."""

    if column_count <= 1:
        return "full_width"
    if column_count == 2:
        return "split_left" if column == 0 else "split_right"
    return "grid_cell"


def parse_ascii_sketch(text: str) -> list[LayoutZone]:
    """Parse an ASCII layout sketch into an ordered list of zones."""

    lines = _dedent_block(text)
    if not lines:
        raise SchemaError("ASCII sketch is empty")

    width = max(len(line) for line in lines)
    lines = [line.ljust(width) for line in lines]

    zones: list[LayoutZone] = []
    seen_ids: dict[str, int] = {}

    def unique_id(seed: str) -> str:
        base = _slugify(seed)
        if base not in seen_ids:
            seen_ids[base] = 1
            return base
        seen_ids[base] += 1
        return f"{base}-{seen_ids[base]}"

    for band_index, (band_start, band_lines) in enumerate(_collect_bands(lines)):
        spans = _cell_spans(band_lines, width)
        column_count = len(spans)
        for column, (left, right) in enumerate(spans):
            fragments = [line[left:right].strip() for line in band_lines]
            text_lines = [fragment for fragment in fragments if fragment]
            if not text_lines:
                continue

            label = text_lines[0]
            if ":" in label:
                head, _, tail = label.partition(":")
                seed = head.strip() or label
                purpose = tail.strip()
            else:
                seed = label
                purpose = ""
            details = tuple(text_lines[1:])

            bounds = LayoutZoneBounds(
                band=band_index,
                column=column,
                column_count=column_count,
                x=left,
                y=band_start,
                width=right - left,
                height=len(band_lines),
            )
            zones.append(
                LayoutZone(
                    zone_id=unique_id(seed),
                    label=label,
                    purpose=purpose,
                    layout_role=_layout_role(column, column_count),
                    bounds=bounds,
                    details=details,
                )
            )

    if not zones:
        raise SchemaError("no layout zones detected in ASCII sketch")
    return zones


def build_layout_zone_schema() -> dict[str, Any]:
    """Build the canonical zone taxonomy contract with HTML render annotations."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Layout Zone Taxonomy",
        "description": (
            "Zone taxonomy parsed from an ASCII layout sketch. Each zone is a "
            "value-carrying region that renders to a semantic HTML section."
        ),
        "type": "object",
        "x-html": {"kind": "document", "tag": "main", "class": "layout"},
        "x-css": {
            "container_class": "layout",
            "grid_columns": 12,
            "breakpoint": "720px",
            "spacing_tokens": {
                "--space-xs": "4px",
                "--space-sm": "8px",
                "--space-md": "16px",
                "--space-lg": "24px",
            },
        },
        "x-svg": {
            "cell_width": 9,
            "cell_height": 20,
            "padding": 12,
            "font_size": 12,
        },
        "properties": {
            "page_id": {
                "type": "string",
                "x-html": {"kind": "attribute", "attribute": "data-page-id"},
            },
            "title": {
                "type": "string",
                "x-html": {"kind": "heading", "level": 1},
            },
            "source_sketch": {
                "type": "string",
                "x-html": {"kind": "ignore"},
            },
            "zones": {
                "type": "array",
                "x-html": {"kind": "zone-list"},
                "items": {
                    "type": "object",
                    "x-html": {"kind": "zone", "tag": "section"},
                    "properties": {
                        "zone_id": {
                            "type": "string",
                            "x-html": {"kind": "attribute", "attribute": "data-zone-id"},
                        },
                        "label": {
                            "type": "string",
                            "x-html": {"kind": "heading", "level": 2},
                        },
                        "purpose": {
                            "type": "string",
                            "x-html": {"kind": "text"},
                        },
                        "details": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-html": {"kind": "list"},
                        },
                        "layout_role": {
                            "type": "string",
                            "x-html": {"kind": "attribute", "attribute": "data-layout-role"},
                        },
                        "value_role": {
                            "type": "string",
                            "x-html": {"kind": "attribute", "attribute": "data-value-role"},
                        },
                        "data_surface": {
                            "type": "string",
                            "x-html": {"kind": "attribute", "attribute": "data-surface"},
                        },
                        "claim_posture": {
                            "type": "string",
                            "x-html": {"kind": "attribute", "attribute": "data-claim-posture"},
                        },
                        "bounds": {
                            "type": "object",
                            "x-html": {"kind": "ignore"},
                            "properties": {
                                "band": {"type": "integer"},
                                "column": {"type": "integer"},
                                "column_count": {"type": "integer"},
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "width": {"type": "integer"},
                                "height": {"type": "integer"},
                            },
                            "additionalProperties": True,
                        },
                    },
                    "required": ["zone_id", "label"],
                    "additionalProperties": True,
                },
            },
        },
        "required": ["page_id", "zones"],
        "additionalProperties": True,
    }
    validate_schema_node(schema)
    return schema


def find_zone_list(schema: dict[str, Any], data: Any) -> tuple[dict[str, Any], list[Any]]:
    """Locate the zone array in a layout contract and return its item schema and data.

    Every layout render target (HTML, CSS, SVG) walks the same zone list, so this
    helper keeps zone discovery in one place: the first top-level array-of-objects
    property is the zone list.
    """

    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if isinstance(properties, dict):
        for name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                continue
            if property_schema.get("type") != "array":
                continue
            item_schema = property_schema.get("items")
            if isinstance(item_schema, dict) and item_schema.get("type") == "object":
                values = data.get(name, []) if isinstance(data, dict) else []
                return item_schema, list(values) if isinstance(values, list) else []
    raise SchemaError("layout contract has no zone list")


def build_zone_document(text: str, page_id: str = "", title: str = "") -> dict[str, Any]:
    """Build and validate a zone taxonomy document from an ASCII sketch."""

    lines = _dedent_block(text)
    zones = parse_ascii_sketch(text)

    resolved_page_id = _slugify(page_id) if page_id else (_slugify(title) if title else "layout-sketch")
    resolved_title = title.strip() if title.strip() else (zones[0].purpose or _humanize(resolved_page_id))

    document = {
        "page_id": resolved_page_id,
        "title": resolved_title,
        "source_sketch": "\n".join(lines),
        "zones": [zone.to_dict() for zone in zones],
    }

    schema = build_layout_zone_schema()
    validate_instance_against_schema(schema, document)
    return document
