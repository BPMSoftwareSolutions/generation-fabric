"""SVG rendering from a schema-driven zone taxonomy.

This renderer is the SVG target counterpart to the HTML renderer: it walks the
same zone taxonomy contract and draws each zone as a positioned rectangle, using
the character bounds the ASCII parser already recorded. Dispatching happens on
the ``x-svg`` annotation namespace, which carries the character-to-pixel scale.
The sketch becomes a faithful, diffable picture without leaving the contract.
"""

from __future__ import annotations

from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.layout.ascii_sketch import find_zone_list
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

SVG_META_KEY = "x-svg"


def svg_meta(schema_node: Any) -> dict[str, Any]:
    """Return svg-specific metadata from a schema node."""

    if not isinstance(schema_node, dict):
        return {}
    meta = schema_node.get(SVG_META_KEY, {})
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise SchemaError(f"{SVG_META_KEY} must be an object")
    return meta


def escape_xml_text(value: Any) -> str:
    """Escape a value for use as SVG text content."""

    text = value if isinstance(value, str) else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_xml_attr(value: Any) -> str:
    """Escape a value for use inside a double-quoted SVG attribute."""

    text = value if isinstance(value, str) else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _canvas_size(data: Any, zones: list[Any], cell_width: int, cell_height: int, padding: int) -> tuple[int, int]:
    """Compute the SVG canvas size from the source sketch or the zone bounds."""

    source = data.get("source_sketch", "") if isinstance(data, dict) else ""
    if isinstance(source, str) and source.strip():
        rows = source.split("\n")
        columns = max((len(row) for row in rows), default=1)
        line_count = len(rows)
    else:
        columns = max((int(z["bounds"]["x"]) + int(z["bounds"]["width"]) for z in zones if "bounds" in z), default=1) + 1
        line_count = max((int(z["bounds"]["y"]) + int(z["bounds"]["height"]) for z in zones if "bounds" in z), default=1) + 1
    width = padding * 2 + columns * cell_width
    height = padding * 2 + line_count * cell_height
    return width, height


def render_svg_document(schema_node: dict[str, Any], data: Any) -> str:
    """Render an SVG drawing from a zone taxonomy contract and matching data."""

    validate_schema_node(schema_node)
    validate_instance_against_schema(schema_node, data)

    meta = svg_meta(schema_node)
    cell_width = int(meta.get("cell_width", 9))
    cell_height = int(meta.get("cell_height", 20))
    padding = int(meta.get("padding", 12))
    font_size = int(meta.get("font_size", 12))

    _item_schema, zones = find_zone_list(schema_node, data)
    width, height = _canvas_size(data, zones, cell_width, cell_height, padding)

    title = ""
    if isinstance(data, dict):
        title = data.get("title") or data.get("page_id") or ""
    title = title or schema_node.get("title") or "Layout"

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{escape_xml_attr(title)} layout sketch">',
        "  <style>",
        "    .canvas { fill: #ffffff; stroke: #cbd5e1; stroke-width: 1; }",
        "    .zone { fill: #f8fafc; stroke: #334155; stroke-width: 1; }",
        "    .zone--full_width { fill: #eef2ff; }",
        "    .zone--split_left { fill: #ecfeff; }",
        "    .zone--split_right { fill: #f0fdf4; }",
        "    .zone--grid_cell { fill: #fef9c3; }",
        f"    .zone-label {{ font-family: monospace; font-size: {font_size}px; fill: #0f172a; }}",
        "  </style>",
        f'  <rect class="canvas" x="0" y="0" width="{width}" height="{height}"/>',
    ]

    for zone in zones:
        bounds = zone.get("bounds", {}) if isinstance(zone, dict) else {}
        x = padding + int(bounds.get("x", 0)) * cell_width
        y = padding + int(bounds.get("y", 0)) * cell_height
        box_width = int(bounds.get("width", 0)) * cell_width
        box_height = int(bounds.get("height", 0)) * cell_height
        role = str(zone.get("layout_role", "full_width"))
        zone_id = str(zone.get("zone_id", ""))
        label = str(zone.get("label", ""))
        text_x = x + 6
        text_y = y + font_size + 4
        lines.append(f'  <g data-zone-id="{escape_xml_attr(zone_id)}">')
        lines.append(
            f'    <rect class="zone zone--{role}" x="{x}" y="{y}" width="{box_width}" height="{box_height}"/>'
        )
        lines.append(f'    <text class="zone-label" x="{text_x}" y="{text_y}">{escape_xml_text(label)}</text>')
        lines.append("  </g>")

    lines.append("</svg>")
    return "\n".join(lines) + "\n"
