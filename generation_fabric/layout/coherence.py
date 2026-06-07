"""Deterministic coherence audit for layout zone taxonomies.

The audit answers the doctrine question from the ASCII-first governance vision:
not "does it look good?" but "does the visual structure preserve the intended
meaning?". It runs deterministic checks over a zone taxonomy and the artifacts
rendered from it, then expresses the result as a Markdown report rendered through
the existing Markdown renderer. The fabric audits itself with its own pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.css.renderer import render_css_document
from generation_fabric.exceptions import SchemaError
from generation_fabric.html.renderer import render_html_document
from generation_fabric.layout.ascii_sketch import find_zone_list
from generation_fabric.layout.box_model import build_box_model_document, leaf_boxes
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node
from generation_fabric.svg.renderer import render_svg_document


@dataclass(frozen=True)
class CoherenceReportPaths:
    """Describe the files produced by the coherence audit."""

    schema_path: Path
    data_path: Path
    markdown_path: Path


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    """Build one normalized check result."""

    return {"check": name, "status": "pass" if passed else "fail", "detail": detail}


def audit_layout_coherence(schema_node: dict[str, Any], data: Any) -> dict[str, Any]:
    """Run deterministic coherence checks over a zone taxonomy and its renders."""

    validate_schema_node(schema_node)
    validate_instance_against_schema(schema_node, data)

    _item_schema, zones = find_zone_list(schema_node, data)
    page_id = str(data.get("page_id", "")) if isinstance(data, dict) else ""
    title = str(data.get("title", "")) if isinstance(data, dict) else ""

    checks: list[dict[str, Any]] = []

    source_sketch = data.get("source_sketch", "") if isinstance(data, dict) else ""
    checks.append(_check("sketch_present", bool(source_sketch), "ASCII source sketch is recorded" if source_sketch else "no source sketch recorded"))
    checks.append(_check("zones_detected", bool(zones), f"{len(zones)} zones detected"))

    zone_ids = [str(zone.get("zone_id", "")) for zone in zones]
    duplicates = sorted({zid for zid in zone_ids if zone_ids.count(zid) > 1})
    checks.append(_check("unique_zone_ids", not duplicates, "all zone ids are unique" if not duplicates else f"duplicate zone ids: {', '.join(duplicates)}"))

    missing_labels = [zid or "<unknown>" for zid, zone in zip(zone_ids, zones) if not str(zone.get("label", "")).strip()]
    checks.append(_check("zones_have_labels", not missing_labels, "every zone has a label" if not missing_labels else f"zones missing labels: {', '.join(missing_labels)}"))

    missing_roles = [zid or "<unknown>" for zid, zone in zip(zone_ids, zones) if not str(zone.get("layout_role", "")).strip()]
    checks.append(_check("zones_have_layout_role", not missing_roles, "every zone has a layout role" if not missing_roles else f"zones missing layout role: {', '.join(missing_roles)}"))

    bad_bounds = [
        zid or "<unknown>"
        for zid, zone in zip(zone_ids, zones)
        if not (
            isinstance(zone.get("bounds"), dict)
            and int(zone["bounds"].get("width", 0)) > 0
            and int(zone["bounds"].get("height", 0)) > 0
        )
    ]
    checks.append(_check("zones_have_bounds", not bad_bounds, "every zone has positive bounds" if not bad_bounds else f"zones with empty bounds: {', '.join(bad_bounds)}"))

    def _order_key(zone: dict[str, Any]) -> tuple[int, int]:
        bounds = zone.get("bounds", {}) if isinstance(zone, dict) else {}
        return int(bounds.get("band", 0)), int(bounds.get("column", 0))

    reading_order_ok = list(zones) == sorted(zones, key=_order_key)
    checks.append(_check("reading_order_preserved", reading_order_ok, "zones follow band/column reading order" if reading_order_ok else "zones are not in reading order"))

    html = render_html_document(schema_node, data)
    missing_in_html = [zid for zid in zone_ids if zid and f'data-zone-id="{zid}"' not in html]
    checks.append(_check("html_preserves_zones", not missing_in_html, "every zone renders to an HTML section" if not missing_in_html else f"zones missing from HTML: {', '.join(missing_in_html)}"))

    css = render_css_document(schema_node, data)
    missing_in_css = [zid for zid in zone_ids if zid and f'[data-zone-id="{zid}"]' not in css]
    checks.append(_check("css_owns_zones", not missing_in_css, "every zone owns a CSS rule" if not missing_in_css else f"zones missing CSS ownership: {', '.join(missing_in_css)}"))

    svg = render_svg_document(schema_node, data)
    missing_in_svg = [zid for zid in zone_ids if zid and f'data-zone-id="{zid}"' not in svg]
    checks.append(_check("svg_preserves_zones", not missing_in_svg, "every zone draws an SVG box" if not missing_in_svg else f"zones missing from SVG: {', '.join(missing_in_svg)}"))

    box_model = build_box_model_document(data)
    surfaces = leaf_boxes(box_model)
    surface_ids = {str(box.get("box_id", "")) for box in surfaces}
    missing_boxes = [zid for zid in zone_ids if zid and zid not in surface_ids]
    checks.append(_check("box_model_covers_zones", not missing_boxes, "every zone maps to a box-model surface" if not missing_boxes else f"zones missing a box: {', '.join(missing_boxes)}"))

    unnamed_surfaces = [str(box.get("box_id", "")) for box in surfaces if not str(box.get("css_class", "")).startswith("surface")]
    checks.append(_check("box_surfaces_named", not unnamed_surfaces, "every surface box owns a named CSS class" if not unnamed_surfaces else f"surfaces missing a class: {', '.join(unnamed_surfaces)}"))

    passed_count = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    score = (passed_count / total * 100) if total else 0.0
    passed = passed_count == total

    return {
        "page_id": page_id,
        "title": title,
        "score": round(score, 1),
        "passed": passed,
        "summary": (
            f"{passed_count}/{total} coherence checks passed across {len(zones)} zones."
            if passed
            else f"{passed_count}/{total} coherence checks passed; {total - passed_count} need attention."
        ),
        "checks": checks,
        "zones": [
            {"zone_id": zid, "layout_role": str(zone.get("layout_role", "")), "label": str(zone.get("label", ""))}
            for zid, zone in zip(zone_ids, zones)
        ],
    }


def build_coherence_report_document(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a Markdown report contract and data from an audit result."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Layout Coherence Report",
        "description": "Deterministic coherence audit of a layout zone taxonomy.",
        "type": "object",
        "properties": {
            "page": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
            "score": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
            "status": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
            "summary": {"type": "string", "x-markdown": {"kind": "paragraph"}},
            "checks_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "check": {"type": "string"},
                        "status": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                    "required": ["check", "status", "detail"],
                    "additionalProperties": False,
                },
                "x-markdown": {"kind": "table"},
            },
            "zones_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "zones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "zone_id": {"type": "string"},
                        "layout_role": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "required": ["zone_id", "layout_role", "label"],
                    "additionalProperties": False,
                },
                "x-markdown": {"kind": "table"},
            },
        },
        "required": [
            "page",
            "score",
            "status",
            "summary",
            "checks_heading",
            "checks",
            "zones_heading",
            "zones",
        ],
        "additionalProperties": False,
    }
    validate_schema_node(schema)

    data = {
        "page": report.get("page_id", "") or "(unnamed)",
        "score": f"{float(report.get('score', 0.0)):.1f}%",
        "status": "coherent" if report.get("passed") else "needs attention",
        "summary": report.get("summary", ""),
        "checks_heading": "Checks",
        "checks": list(report.get("checks", [])),
        "zones_heading": "Zones",
        "zones": list(report.get("zones", [])),
    }
    validate_instance_against_schema(schema, data)
    return schema, data


def _resolve_report_path(output: str, page_id: str) -> Path:
    """Resolve the Markdown report output path."""

    if output:
        path = Path(output)
        if not path.suffix:
            path = path.with_suffix(".md")
        return path
    base = page_id or "layout-sketch"
    return Path("generated") / f"{base}.coherence.md"


def write_layout_coherence_report(
    schema_node: dict[str, Any],
    data: Any,
    *,
    output: str = "",
    overwrite: bool = False,
) -> tuple[CoherenceReportPaths, dict[str, Any]]:
    """Audit a zone taxonomy and write the coherence report plus its sidecars."""

    report = audit_layout_coherence(schema_node, data)
    report_schema, report_data = build_coherence_report_document(report)
    markdown = render_markdown_document(report_schema, report_data)

    markdown_path = _resolve_report_path(output, report.get("page_id", ""))
    stem = markdown_path.stem
    schema_path = markdown_path.with_name(f"{stem}.schema.json")
    data_path = markdown_path.with_name(f"{stem}.json")

    for target in (schema_path, data_path, markdown_path):
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_json_file_atomic(schema_path, report_schema)
    write_json_file_atomic(data_path, report_data)
    write_text_file_atomic(markdown_path, markdown)

    paths = CoherenceReportPaths(schema_path=schema_path, data_path=data_path, markdown_path=markdown_path)
    return paths, report
