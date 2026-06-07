"""Semantic HTML rendering from a schema-driven zone taxonomy.

This renderer is the HTML target counterpart to the Markdown renderer: it walks a
JSON Schema contract plus matching data and emits markup, dispatching on the
``x-html`` annotation namespace instead of ``x-markdown``. One contract can carry
several render-target namespaces at once, so the same zone taxonomy that renders
Markdown can also render governed, semantic HTML.
"""

from __future__ import annotations

import json
from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

HTML_META_KEY = "x-html"
INDENT = "  "


def html_meta(schema_node: Any) -> dict[str, Any]:
    """Return html-specific metadata from a schema node."""

    if not isinstance(schema_node, dict):
        return {}

    meta = schema_node.get(HTML_META_KEY, {})
    if meta is None:
        return {}
    if isinstance(meta, str):
        return {"kind": meta}
    if not isinstance(meta, dict):
        raise SchemaError(f"{HTML_META_KEY} must be a string or an object")
    return meta


def escape_html_text(value: Any) -> str:
    """Escape a value for use as HTML text content."""

    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_html_attr(value: Any) -> str:
    """Escape a value for use inside a double-quoted HTML attribute."""

    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _indent(lines: list[str]) -> list[str]:
    """Indent a block of rendered lines by one level."""

    return [f"{INDENT}{line}" for line in lines]


def _attribute_name(property_name: str, meta: dict[str, Any]) -> str:
    """Resolve the HTML attribute name for an attribute-bound property."""

    explicit = meta.get("attribute")
    if isinstance(explicit, str) and explicit:
        return explicit
    return f"data-{property_name.replace('_', '-')}"


def collect_element_attributes(schema_node: Any, data: Any, meta: dict[str, Any]) -> list[tuple[str, str]]:
    """Collect HTML attributes for an element from its meta and data."""

    attributes: list[tuple[str, str]] = []
    class_name = meta.get("class")
    if isinstance(class_name, str) and class_name:
        attributes.append(("class", class_name))

    properties = schema_node.get("properties") if isinstance(schema_node, dict) else None
    if isinstance(properties, dict) and isinstance(data, dict):
        for name, property_schema in properties.items():
            property_meta = html_meta(property_schema)
            if property_meta.get("kind") != "attribute":
                continue
            if name not in data:
                continue
            value = data[name]
            if value in (None, "", [], {}):
                continue
            attributes.append((_attribute_name(name, property_meta), escape_html_attr(value)))
    return attributes


def _open_tag(tag: str, attributes: list[tuple[str, str]]) -> str:
    """Render an opening tag with its attributes."""

    rendered = "".join(f' {name}="{value}"' for name, value in attributes)
    return f"<{tag}{rendered}>"


def wrap_element(tag: str, attributes: list[tuple[str, str]], children: list[str]) -> list[str]:
    """Wrap rendered child lines inside an element with indentation."""

    open_tag = _open_tag(tag, attributes)
    if not children:
        return [f"{open_tag}</{tag}>"]
    return [open_tag, *_indent(children), f"</{tag}>"]


def render_html_element(schema_node: Any, data: Any, *, default_tag: str) -> list[str]:
    """Render an object schema as an HTML element with attributes and children."""

    meta = html_meta(schema_node)
    tag = str(meta.get("tag", default_tag))
    attributes = collect_element_attributes(schema_node, data, meta)
    children = render_html_children(schema_node, data)
    return wrap_element(tag, attributes, children)


def render_html_children(schema_node: Any, data: Any) -> list[str]:
    """Render the body content of an object schema in definition order."""

    if not isinstance(schema_node, dict) or not isinstance(data, dict):
        if data in (None, ""):
            return []
        return [escape_html_text(data)]

    properties = schema_node.get("properties", {})
    if not isinstance(properties, dict):
        return []

    lines: list[str] = []
    for name, property_schema in properties.items():
        if name not in data:
            continue
        kind = html_meta(property_schema).get("kind")
        if kind in ("attribute", "ignore"):
            continue
        lines.extend(render_html_field(name, property_schema, data[name]))
    return lines


def render_html_list(value: Any) -> list[str]:
    """Render an array of scalars as an unordered list."""

    items = value if isinstance(value, list) else [value]
    rendered_items = [item for item in items if item not in (None, "")]
    if not rendered_items:
        return []
    body = [f"<li>{escape_html_text(item)}</li>" for item in rendered_items]
    return wrap_element("ul", [], body)


def render_html_field(field_name: str, schema_node: Any, value: Any) -> list[str]:
    """Render a single schema-backed value as HTML lines."""

    if not isinstance(schema_node, dict):
        if value in (None, ""):
            return []
        return [f"<p>{escape_html_text(value)}</p>"]

    meta = html_meta(schema_node)
    kind = meta.get("kind")

    if kind == "heading":
        if value in (None, ""):
            return []
        level = max(1, min(6, int(meta.get("level", 2))))
        return [f"<h{level}>{escape_html_text(value)}</h{level}>"]

    if kind in ("text", "paragraph"):
        if value in (None, ""):
            return []
        return [f"<p>{escape_html_text(value)}</p>"]

    if kind == "list":
        return render_html_list(value)

    if kind in ("zone", "section", "element"):
        return render_html_element(schema_node, value, default_tag=str(meta.get("tag", "section")))

    if kind == "zone-list":
        item_schema = schema_node.get("items", {})
        item_tag = str(html_meta(item_schema).get("tag", "section"))
        lines: list[str] = []
        for item in value if isinstance(value, list) else [value]:
            lines.extend(render_html_element(item_schema, item, default_tag=item_tag))
        return lines

    # Fallbacks keep the renderer usable without exhaustive annotations.
    if isinstance(value, dict):
        return render_html_element(schema_node, value, default_tag=str(meta.get("tag", "div")))
    if isinstance(value, list):
        item_schema = schema_node.get("items", {})
        if value and all(isinstance(item, dict) for item in value):
            lines = []
            for item in value:
                lines.extend(render_html_element(item_schema, item, default_tag="section"))
            return lines
        return render_html_list(value)
    if value in (None, ""):
        return []
    return [f"<p>{escape_html_text(value)}</p>"]


def render_html_body(schema_node: dict[str, Any], data: Any) -> str:
    """Render the body element (without the surrounding HTML document)."""

    default_tag = str(html_meta(schema_node).get("tag", "main"))
    return "\n".join(render_html_element(schema_node, data, default_tag=default_tag))


def render_html_document(schema_node: dict[str, Any], data: Any) -> str:
    """Render a full HTML5 document from a schema contract and matching data."""

    validate_schema_node(schema_node)
    validate_instance_against_schema(schema_node, data)

    default_tag = str(html_meta(schema_node).get("tag", "main"))
    body_lines = render_html_element(schema_node, data, default_tag=default_tag)

    title = ""
    if isinstance(data, dict):
        title = data.get("title") or data.get("page_id") or ""
    title = title or schema_node.get("title") or "Document"

    document = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        f'{INDENT}<meta charset="utf-8">',
        f'{INDENT}<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"{INDENT}<title>{escape_html_text(title)}</title>",
        "</head>",
        "<body>",
        *_indent(body_lines),
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(document)
