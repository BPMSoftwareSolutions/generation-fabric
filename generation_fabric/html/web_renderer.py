"""Component-aware semantic HTML rendering from a web page contract.

Each component intent is projected into accessible, static, semantic markup —
forms become ``<form>`` with labeled controls, data grids become tables, charts
become figures with data hooks, gauges become readable metric components. Every
component root carries traceability attributes back to its zone and component id,
so HTML stays auditable against the contract.
"""

from __future__ import annotations

from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.html.renderer import escape_html_attr, escape_html_text

INDENT = "  "

_INPUT_TYPE_BY_FIELD = {
    "date": "date",
    "email": "email",
    "password": "password",
    "number": "number",
    "search": "search",
    "tel": "tel",
    "time": "time",
    "url": "url",
}


def _indent(lines: list[str], depth: int = 1) -> list[str]:
    """Indent rendered lines by the given depth."""

    pad = INDENT * depth
    return [f"{pad}{line}" for line in lines]


def _attr(name: str, value: Any) -> str:
    """Render a single attribute when the value is non-empty."""

    if value in (None, "", [], {}):
        return ""
    return f' {name}="{escape_html_attr(value)}"'


def _traceability(component: dict[str, Any], *, role: bool = True) -> str:
    """Build the shared traceability + accessibility attributes for a component root."""

    attrs = [
        _attr("data-zone-id", component.get("zone_id")),
        _attr("data-component-id", component.get("component_id")),
        _attr("data-component-type", component.get("component_type")),
        _attr("data-variant", component.get("variant")),
    ]
    if role:
        attrs.append(_attr("role", component.get("role")))
    aria = (component.get("accessibility") or {}).get("aria_label")
    attrs.append(_attr("aria-label", aria))
    return "".join(attr for attr in attrs if attr)


def _input_type(field: dict[str, Any]) -> str:
    """Resolve the HTML input type for a form field."""

    name = str(field.get("name", "")).lower()
    declared = str(field.get("type", "")).lower()
    return _INPUT_TYPE_BY_FIELD.get(declared) or _INPUT_TYPE_BY_FIELD.get(name) or "text"


def _render_form(component: dict[str, Any]) -> list[str]:
    """Render a form component."""

    label = component.get("label", "Form")
    lines = [f"<form class=\"gf-form\"{_traceability(component)}>"]
    body = [f"<h2 class=\"gf-form__title\">{escape_html_text(label)}</h2>"]
    fields = component.get("fields", []) or []
    if fields:
        body.append("<div class=\"gf-form__fields\">")
        for field in fields:
            field_id = f"{component.get('component_id', 'form')}-{field.get('name', 'field')}"
            control = (
                f'<input class="gf-input" id="{escape_html_attr(field_id)}" '
                f'name="{escape_html_attr(field.get("name", ""))}" type="{_input_type(field)}">'
            )
            body.extend(
                _indent(
                    [
                        "<div class=\"gf-field\">",
                        *_indent(
                            [
                                f'<label class="gf-label" for="{escape_html_attr(field_id)}">{escape_html_text(field.get("label", ""))}</label>',
                                control,
                            ]
                        ),
                        "</div>",
                    ]
                )
            )
        body.append("</div>")
    actions = component.get("actions", []) or []
    if actions:
        body.append("<div class=\"gf-form__actions\">")
        for action in actions:
            body.append(
                f'{INDENT}<button class="gf-button" type="submit" data-action="{escape_html_attr(action.get("name", ""))}">'
                f"{escape_html_text(action.get('label', 'Submit'))}</button>"
            )
        body.append("</div>")
    lines.extend(_indent(body))
    lines.append("</form>")
    return lines


def _render_data_grid(component: dict[str, Any]) -> list[str]:
    """Render a data grid / table component."""

    label = component.get("label", "Data")
    columns = component.get("columns", []) or []
    data = component.get("data") or {}
    item_name = data.get("item_name", "row")
    extra = _attr("data-source", data.get("source"))

    lines = [f"<section class=\"gf-data-grid\"{_traceability(component)}{extra}>"]
    body = [f"<h2 class=\"gf-data-grid__title\">{escape_html_text(label)}</h2>"]
    header_cells = "".join(f"<th scope=\"col\">{escape_html_text(column.get('label', column.get('name', '')))}</th>" for column in columns)
    span = max(1, len(columns))
    body.extend(
        [
            "<table class=\"gf-table\">",
            f"{INDENT}<thead><tr>{header_cells}</tr></thead>",
            f"{INDENT}<tbody>",
            f'{INDENT}{INDENT}<tr class="gf-table__empty"><td colspan="{span}">No {escape_html_text(item_name)} records yet</td></tr>',
            f"{INDENT}</tbody>",
            "</table>",
        ]
    )
    for action in component.get("actions", []) or []:
        body.append(
            f'<button class="gf-button gf-button--ghost" data-action="{escape_html_attr(action.get("name", ""))}">'
            f"{escape_html_text(action.get('label', ''))}</button>"
        )
    lines.extend(_indent(body))
    lines.append("</section>")
    return lines


def _render_chart(component: dict[str, Any]) -> list[str]:
    """Render a chart component as an accessible figure placeholder."""

    label = component.get("label", "Chart")
    measures = component.get("measures") or {}
    chart_type = component.get("component_type", "chart")
    extra = _attr("data-chart-type", chart_type) + _attr("data-x", measures.get("x")) + _attr("data-y", measures.get("y"))
    aria = f"{label} {chart_type.replace('chart_', '')} chart"
    lines = [f"<figure class=\"gf-chart\"{_traceability(component)}{extra}>"]
    lines.extend(
        _indent(
            [
                f"<figcaption class=\"gf-chart__caption\">{escape_html_text(label)}</figcaption>",
                f'<div class="gf-chart__canvas" role="img" aria-label="{escape_html_attr(aria)}"></div>',
            ]
        )
    )
    lines.append("</figure>")
    return lines


def _render_metric(component: dict[str, Any]) -> list[str]:
    """Render a gauge / kpi / metric tile component."""

    label = component.get("label", "Metric")
    measures = component.get("measures") or {}
    extra = (
        _attr("data-value", measures.get("value"))
        + _attr("data-min", measures.get("min"))
        + _attr("data-max", measures.get("max"))
        + _attr("data-unit", measures.get("unit"))
    )
    lines = [f"<section class=\"gf-metric\"{_traceability(component)}{extra}>"]
    body = [
        f"<h2 class=\"gf-metric__title\">{escape_html_text(label)}</h2>",
        '<p class="gf-metric__value" aria-live="polite">&mdash;</p>',
    ]
    binding = measures.get("value")
    if binding:
        body.append(f"<p class=\"gf-metric__caption\">Bound to {escape_html_text(binding)}</p>")
    lines.extend(_indent(body))
    lines.append("</section>")
    return lines


def _render_region(component: dict[str, Any]) -> list[str]:
    """Render a generic region / container / card component."""

    label = component.get("label", "Section")
    lines = [f"<section class=\"gf-region\"{_traceability(component)}>"]
    lines.extend(_indent([f"<h2 class=\"gf-region__title\">{escape_html_text(label)}</h2>"]))
    lines.append("</section>")
    return lines


_METRIC_TYPES = {"gauge", "kpi", "metric_tile", "progress"}


def render_component(component: dict[str, Any]) -> list[str]:
    """Render one component to HTML lines based on its type."""

    component_type = str(component.get("component_type", "container"))
    if component_type == "form":
        return _render_form(component)
    if component_type in {"data_grid", "table", "list"}:
        return _render_data_grid(component)
    if component_type.startswith("chart_") or component_type == "sparkline":
        return _render_chart(component)
    if component_type in _METRIC_TYPES:
        return _render_metric(component)
    return _render_region(component)


def render_web_html_document(contract: dict[str, Any]) -> str:
    """Render a full HTML5 document from a web page contract."""

    if not isinstance(contract, dict):
        raise SchemaError("web HTML rendering needs a web page contract")

    components = contract.get("components", []) or []
    title = contract.get("title") or contract.get("page_id") or "Web Page"
    page_id = contract.get("page_id", "")

    page_components = [c for c in components if c.get("component_type") == "page"]
    body_components = [c for c in components if c.get("component_type") != "page"]

    body: list[str] = []
    for page_component in page_components:
        # A native <header> child of <body> is already the banner landmark, so we
        # suppress the component role here to avoid a second "main" landmark.
        body.append(f"<header class=\"gf-page-header\"{_traceability(page_component, role=False)}>")
        body.append(f"{INDENT}<h1 class=\"gf-page-title\">{escape_html_text(page_component.get('label', title))}</h1>")
        body.append("</header>")

    main_lines = [f'<main class="gf-web-page" role="main"{_attr("data-page-id", page_id)}>']
    for component in body_components:
        main_lines.extend(_indent(render_component(component)))
    main_lines.append("</main>")
    body.extend(main_lines)

    document = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        f'{INDENT}<meta charset="utf-8">',
        f'{INDENT}<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"{INDENT}<title>{escape_html_text(title)}</title>",
        f'{INDENT}<link rel="stylesheet" href="{escape_html_attr(str(page_id))}.css">',
        "</head>",
        '<body class="gf-web">',
        *_indent(body),
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(document)
