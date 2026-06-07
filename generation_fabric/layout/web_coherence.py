"""Component-aware coherence audit for the ASCII-to-web pipeline.

The audit verifies that the web page contract is internally consistent and that
its HTML, CSS, and SVG projections preserve every component. It answers
structure, data-binding, traceability, and accessibility questions
deterministically, then renders the result as a Markdown report through the
existing Markdown renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.css.web_renderer import render_web_css_document
from generation_fabric.exceptions import SchemaError
from generation_fabric.html.web_renderer import render_web_html_document
from generation_fabric.layout.component_intent import SUPPORTED_COMPONENT_TYPES
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node
from generation_fabric.svg.web_renderer import render_web_svg_document

_A11Y_TYPES = {"form", "data_grid", "table", "gauge", "kpi", "metric_tile"}


@dataclass(frozen=True)
class WebCoherenceReportPaths:
    """Describe the files produced by the web coherence audit."""

    schema_path: Path
    data_path: Path
    markdown_path: Path


def _check(name: str, status: str, detail: str, remediation: str = "") -> dict[str, str]:
    """Build one normalized check result."""

    return {"check": name, "status": status, "detail": detail, "remediation": remediation}


def _is_chart(component_type: str) -> bool:
    return component_type.startswith("chart_") or component_type == "sparkline"


def audit_web_coherence(contract: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic component-aware coherence checks over a web contract."""

    if not isinstance(contract, dict):
        raise SchemaError("web coherence audit needs a web page contract")

    components = contract.get("components", []) or []
    zone_ids = {str(zone.get("zone_id", "")) for zone in contract.get("zones", []) or []}
    component_ids = [str(c.get("component_id", "")) for c in components]

    checks: list[dict[str, str]] = []

    missing_zone = [c.get("component_id", "?") for c in components if str(c.get("zone_id", "")) not in zone_ids]
    checks.append(
        _check(
            "zone_component_coverage",
            "pass" if not missing_zone else "fail",
            "every component references an existing zone" if not missing_zone else f"components without a zone: {', '.join(missing_zone)}",
            "" if not missing_zone else "Re-run zone extraction so every component maps to a zone.",
        )
    )

    duplicates = sorted({cid for cid in component_ids if component_ids.count(cid) > 1})
    checks.append(
        _check(
            "component_ids_unique",
            "pass" if not duplicates else "fail",
            "component ids are unique" if not duplicates else f"duplicate component ids: {', '.join(duplicates)}",
            "" if not duplicates else "Disambiguate the zone labels that produced the colliding ids.",
        )
    )

    unsupported = [
        str(c.get("component_type", ""))
        for c in components
        if str(c.get("component_type", "")) not in SUPPORTED_COMPONENT_TYPES and str(c.get("component_type", "")) != "container"
    ]
    checks.append(
        _check(
            "component_type_supported",
            "pass" if not unsupported else "warn",
            "all component types are supported" if not unsupported else f"unsupported types degraded to container: {', '.join(sorted(set(unsupported)))}",
            "" if not unsupported else "Use a supported component family or add a renderer for the new type.",
        )
    )

    forms = [c for c in components if c.get("component_type") == "form"]
    bad_forms = [c.get("component_id", "?") for c in forms if not (c.get("fields") and c.get("actions"))]
    checks.append(
        _check(
            "form_controls_present",
            "pass" if not bad_forms else "warn",
            "forms declare fields and actions" if not bad_forms else f"forms missing fields or actions: {', '.join(bad_forms)}",
            "" if not bad_forms else "Add `fields:` and `action:` lines under the form zone.",
        )
    )

    grids = [c for c in components if c.get("component_type") in {"data_grid", "table", "list"}]
    bad_grids = [c.get("component_id", "?") for c in grids if not (c.get("columns") and c.get("data"))]
    checks.append(
        _check(
            "data_grid_columns_present",
            "pass" if not bad_grids else "warn",
            "data grids declare columns and a data source" if not bad_grids else f"data grids missing columns or data: {', '.join(bad_grids)}",
            "" if not bad_grids else "Add `columns:` and `data:` lines under the grid zone.",
        )
    )

    charts = [c for c in components if _is_chart(str(c.get("component_type", "")))]
    bad_charts = [c.get("component_id", "?") for c in charts if not ((c.get("measures") or {}).get("x") and (c.get("measures") or {}).get("y"))]
    checks.append(
        _check(
            "chart_axes_present",
            "pass" if not bad_charts else "warn",
            "charts declare x and y axes" if not bad_charts else f"charts missing axes: {', '.join(bad_charts)}",
            "" if not bad_charts else "Add an `x:` and `y:` line under the chart zone.",
        )
    )

    gauges = [c for c in components if c.get("component_type") in {"gauge", "progress"}]
    bad_gauges = [
        c.get("component_id", "?")
        for c in gauges
        if not all((c.get("measures") or {}).get(key) for key in ("value", "min", "max"))
    ]
    checks.append(
        _check(
            "gauge_range_present",
            "pass" if not bad_gauges else "warn",
            "gauges declare value, min, and max" if not bad_gauges else f"gauges missing range: {', '.join(bad_gauges)}",
            "" if not bad_gauges else "Add `value:`, `min:`, and `max:` lines under the gauge zone.",
        )
    )

    html = render_web_html_document(contract)
    missing_html = [cid for cid in component_ids if cid and f'data-component-id="{cid}"' not in html]
    checks.append(
        _check(
            "html_component_traceability",
            "pass" if not missing_html else "fail",
            "HTML preserves every component id" if not missing_html else f"components missing from HTML: {', '.join(missing_html)}",
            "" if not missing_html else "Ensure every component type has an HTML renderer branch.",
        )
    )

    css = render_web_css_document(contract)
    body_zone_ids = [str(c.get("zone_id", "")) for c in components if c.get("component_type") != "page"]
    missing_css = [zid for zid in body_zone_ids if zid and f'[data-zone-id="{zid}"]' not in css]
    has_component_classes = ".gf-form" in css and ".gf-data-grid" in css
    css_status = "pass" if not missing_css and has_component_classes else "fail"
    checks.append(
        _check(
            "css_component_ownership",
            css_status,
            "CSS owns zone placement and component classes" if css_status == "pass" else f"CSS missing ownership for: {', '.join(missing_css) or 'component classes'}",
            "" if css_status == "pass" else "Regenerate CSS so every body zone has a grid rule.",
        )
    )

    svg = render_web_svg_document(contract)
    missing_svg = [cid for cid in component_ids if cid and f'data-component-id="{cid}"' not in svg]
    checks.append(
        _check(
            "svg_component_representation",
            "pass" if not missing_svg else "fail",
            "SVG draws every component" if not missing_svg else f"components missing from SVG: {', '.join(missing_svg)}",
            "" if not missing_svg else "Ensure the SVG renderer emits a group per component.",
        )
    )

    needs_a11y = [c for c in components if c.get("component_type") in _A11Y_TYPES]
    missing_a11y = [c.get("component_id", "?") for c in needs_a11y if not (c.get("accessibility") or {}).get("aria_label")]
    checks.append(
        _check(
            "a11y_labels",
            "pass" if not missing_a11y else "warn",
            "interactive components carry accessible labels" if not missing_a11y else f"components missing aria labels: {', '.join(missing_a11y)}",
            "" if not missing_a11y else "Give each interactive zone a readable label.",
        )
    )

    pass_count = sum(1 for check in checks if check["status"] == "pass")
    warn_count = sum(1 for check in checks if check["status"] == "warn")
    fail_count = sum(1 for check in checks if check["status"] == "fail")
    total = len(checks)
    score = round((pass_count + 0.5 * warn_count) / total * 100, 1) if total else 0.0
    passed = fail_count == 0

    if passed and warn_count == 0:
        summary = f"All {total} web coherence checks passed across {len(components)} components."
    elif passed:
        summary = f"{pass_count}/{total} checks passed with {warn_count} warning(s) across {len(components)} components."
    else:
        summary = f"{fail_count} check(s) failed and {warn_count} warned across {len(components)} components."

    return {
        "page_id": str(contract.get("page_id", "")),
        "title": str(contract.get("title", "")),
        "score": score,
        "passed": passed,
        "summary": summary,
        "checks": checks,
        "components": [
            {
                "component_id": str(c.get("component_id", "")),
                "component_type": str(c.get("component_type", "")),
                "zone_id": str(c.get("zone_id", "")),
                "label": str(c.get("label", "")),
            }
            for c in components
        ],
        "warnings": list(contract.get("warnings", []) or []),
    }


def build_web_coherence_report_document(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a Markdown report contract and data from a web coherence audit."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Web Coherence Report",
        "description": "Deterministic component-aware coherence audit of a web page contract.",
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
                        "remediation": {"type": "string"},
                    },
                    "required": ["check", "status", "detail", "remediation"],
                    "additionalProperties": False,
                },
                "x-markdown": {"kind": "table"},
            },
            "components_heading": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "component_id": {"type": "string"},
                        "component_type": {"type": "string"},
                        "zone_id": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "required": ["component_id", "component_type", "zone_id", "label"],
                    "additionalProperties": False,
                },
                "x-markdown": {"kind": "table"},
            },
        },
        "required": ["page", "score", "status", "summary", "checks_heading", "checks", "components_heading", "components"],
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
        "components_heading": "Components",
        "components": list(report.get("components", [])),
    }
    validate_instance_against_schema(schema, data)
    return schema, data


def write_web_coherence_report(
    contract: dict[str, Any],
    *,
    output: str = "",
    overwrite: bool = False,
) -> tuple[WebCoherenceReportPaths, dict[str, Any]]:
    """Audit a web contract and write the coherence report plus sidecars."""

    report = audit_web_coherence(contract)
    report_schema, report_data = build_web_coherence_report_document(report)
    markdown = render_markdown_document(report_schema, report_data)

    markdown_path = Path(output) if output else Path("generated") / f"{report.get('page_id', 'page')}.web-coherence.md"
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

    paths = WebCoherenceReportPaths(schema_path=schema_path, data_path=data_path, markdown_path=markdown_path)
    return paths, report
