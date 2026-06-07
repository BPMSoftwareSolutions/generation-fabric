"""Component-aware SVG blueprint rendering from a web page contract.

The SVG is a deterministic, lightweight wireframe: every component draws its
zone box plus a schematic glyph for its family (form controls, grid rows and
columns, chart axes, gauge arc). It is an architecture artifact, not a chart
engine, and every component keeps traceability attributes back to the contract.
"""

from __future__ import annotations

from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.layout.web_contract import zone_bounds_index

CELL_WIDTH = 9
CELL_HEIGHT = 20
PADDING = 12
LABEL_OFFSET = 22


def _escape_text(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", " ")
    )


def _canvas_size(zones: list[dict[str, Any]]) -> tuple[int, int]:
    columns = max((int(z.get("bounds", {}).get("x", 0)) + int(z.get("bounds", {}).get("width", 0)) for z in zones), default=1) + 1
    rows = max((int(z.get("bounds", {}).get("y", 0)) + int(z.get("bounds", {}).get("height", 0)) for z in zones), default=1) + 1
    return PADDING * 2 + columns * CELL_WIDTH, PADDING * 2 + rows * CELL_HEIGHT


def _rect(bounds: dict[str, Any]) -> tuple[int, int, int, int]:
    x = PADDING + int(bounds.get("x", 0)) * CELL_WIDTH
    y = PADDING + int(bounds.get("y", 0)) * CELL_HEIGHT
    width = int(bounds.get("width", 0)) * CELL_WIDTH
    height = int(bounds.get("height", 0)) * CELL_HEIGHT
    return x, y, width, height


def _form_glyph(gx: int, gy: int, gw: int, gh: int, field_count: int) -> list[str]:
    lines: list[str] = []
    rows = min(max(field_count, 1), 3)
    for index in range(rows):
        iy = gy + index * 22
        if iy + 14 > gy + gh:
            break
        lines.append(f'<rect class="gf-glyph-input" x="{gx}" y="{iy}" width="{max(20, gw - 60)}" height="12" rx="3"/>')
    by = gy + rows * 22
    if by + 16 <= gy + gh:
        lines.append(f'<rect class="gf-glyph-button" x="{gx}" y="{by}" width="64" height="16" rx="4"/>')
    return lines


def _grid_glyph(gx: int, gy: int, gw: int, gh: int, column_count: int) -> list[str]:
    lines = [f'<rect class="gf-glyph-head" x="{gx}" y="{gy}" width="{gw}" height="16"/>']
    columns = max(column_count, 1)
    for col in range(1, columns):
        cx = gx + round(col * gw / columns)
        lines.append(f'<line class="gf-glyph-line" x1="{cx}" y1="{gy}" x2="{cx}" y2="{gy + gh}"/>')
    for row in range(1, 4):
        ry = gy + 16 + row * 16
        if ry > gy + gh:
            break
        lines.append(f'<line class="gf-glyph-line" x1="{gx}" y1="{ry}" x2="{gx + gw}" y2="{ry}"/>')
    return lines


def _chart_glyph(gx: int, gy: int, gw: int, gh: int, chart_type: str) -> list[str]:
    base = gy + gh
    lines = [
        f'<line class="gf-glyph-axis" x1="{gx}" y1="{gy}" x2="{gx}" y2="{base}"/>',
        f'<line class="gf-glyph-axis" x1="{gx}" y1="{base}" x2="{gx + gw}" y2="{base}"/>',
    ]
    if chart_type == "chart_bar":
        bars = 4
        bar_width = max(6, round(gw / (bars * 2)))
        heights = [0.5, 0.8, 0.4, 0.95]
        for index in range(bars):
            bx = gx + 8 + index * round(gw / bars)
            bh = round((gh - 8) * heights[index % len(heights)])
            lines.append(f'<rect class="gf-glyph-bar" x="{bx}" y="{base - bh}" width="{bar_width}" height="{bh}"/>')
    else:
        points = [(0.0, 0.7), (0.25, 0.4), (0.5, 0.55), (0.75, 0.2), (1.0, 0.35)]
        coords = " ".join(f"{gx + round(px * gw)},{gy + round(py * gh)}" for px, py in points)
        lines.append(f'<polyline class="gf-glyph-series" points="{coords}"/>')
    return lines


def _gauge_glyph(gx: int, gy: int, gw: int, gh: int) -> list[str]:
    radius = max(10, min(gw, gh * 2) // 2 - 4)
    cx = gx + gw // 2
    cy = gy + min(gh - 4, radius)
    left_x, right_x = cx - radius, cx + radius
    return [
        f'<path class="gf-glyph-arc" d="M {left_x} {cy} A {radius} {radius} 0 0 1 {right_x} {cy}"/>',
        f'<line class="gf-glyph-needle" x1="{cx}" y1="{cy}" x2="{cx + round(radius * 0.6)}" y2="{cy - round(radius * 0.6)}"/>',
    ]


def _render_component_glyph(component: dict[str, Any], rect: tuple[int, int, int, int]) -> list[str]:
    x, y, width, height = rect
    gx, gy = x + 8, y + LABEL_OFFSET + 4
    gw, gh = max(8, width - 16), max(8, height - LABEL_OFFSET - 12)
    component_type = str(component.get("component_type", "container"))
    if component_type == "form":
        return _form_glyph(gx, gy, gw, gh, len(component.get("fields", []) or []))
    if component_type in {"data_grid", "table", "list"}:
        return _grid_glyph(gx, gy, gw, gh, len(component.get("columns", []) or []) or 1)
    if component_type.startswith("chart_") or component_type == "sparkline":
        return _chart_glyph(gx, gy, gw, gh, component_type)
    if component_type in {"gauge", "kpi", "metric_tile", "progress"}:
        return _gauge_glyph(gx, gy, gw, gh)
    return []


def render_web_svg_document(contract: dict[str, Any]) -> str:
    """Render an SVG blueprint from a web page contract."""

    if not isinstance(contract, dict):
        raise SchemaError("web SVG rendering needs a web page contract")

    zones = list(contract.get("zones", []) or [])
    bounds_index = zone_bounds_index(contract)
    components = contract.get("components", []) or []
    width, height = _canvas_size(zones)
    title = contract.get("title") or contract.get("page_id") or "Web Page"

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{_escape_attr(title)} blueprint">',
        f"  <title>{_escape_text(title)} blueprint</title>",
        f"  <desc>Component wireframe generated from the web page contract.</desc>",
        "  <style>",
        "    .gf-canvas { fill: #ffffff; stroke: #cbd5e1; }",
        "    .gf-zone { fill: #f8fafc; stroke: #334155; }",
        "    .gf-label { font-family: monospace; font-size: 12px; fill: #0f172a; }",
        "    .gf-glyph-input, .gf-glyph-head { fill: #e2e8f0; stroke: #94a3b8; }",
        "    .gf-glyph-button { fill: #2f6f4f; }",
        "    .gf-glyph-line, .gf-glyph-axis { stroke: #94a3b8; }",
        "    .gf-glyph-axis { stroke: #475569; }",
        "    .gf-glyph-bar { fill: #2f6f4f; }",
        "    .gf-glyph-series { fill: none; stroke: #2f6f4f; stroke-width: 2; }",
        "    .gf-glyph-arc { fill: none; stroke: #475569; stroke-width: 2; }",
        "    .gf-glyph-needle { stroke: #b91c1c; stroke-width: 2; }",
        "  </style>",
        f'  <rect class="gf-canvas" x="0" y="0" width="{width}" height="{height}"/>',
    ]

    for component in components:
        zone_id = str(component.get("zone_id", ""))
        bounds = (bounds_index.get(zone_id) or {}).get("bounds", {})
        x, y, box_w, box_h = _rect(bounds)
        component_type = str(component.get("component_type", "container"))
        label = str(component.get("label", ""))
        lines.append(
            f'  <g data-zone-id="{_escape_attr(zone_id)}" data-component-id="{_escape_attr(component.get("component_id", ""))}" '
            f'data-component-type="{_escape_attr(component_type)}">'
        )
        lines.append(f'    <rect class="gf-zone" x="{x}" y="{y}" width="{box_w}" height="{box_h}"/>')
        lines.append(f'    <text class="gf-label" x="{x + 6}" y="{y + 16}">{_escape_text(label)} [{_escape_text(component_type)}]</text>')
        for glyph_line in _render_component_glyph(component, (x, y, box_w, box_h)):
            lines.append(f"    {glyph_line}")
        lines.append("  </g>")

    lines.append("</svg>")
    return "\n".join(lines) + "\n"
