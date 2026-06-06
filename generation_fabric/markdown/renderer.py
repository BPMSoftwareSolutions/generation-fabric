"""Markdown rendering from schema-driven JSON content."""

from __future__ import annotations

import json
from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

MARKDOWN_META_KEY = "x-markdown"


def markdown_meta(schema_node: Any) -> dict[str, Any]:
    """Return markdown-specific metadata from a schema node."""

    if not isinstance(schema_node, dict):
        return {}

    meta = schema_node.get(MARKDOWN_META_KEY, {})
    if meta is None:
        return {}
    if isinstance(meta, str):
        return {"kind": meta}
    if not isinstance(meta, dict):
        raise SchemaError(f"{MARKDOWN_META_KEY} must be a string or an object")
    return meta


def markdown_inline_text(value: Any) -> str:
    """Render a value as a single-line markdown-safe string."""

    if isinstance(value, str):
        return value.replace("\r", " ").replace("\n", " ").strip()
    return json.dumps(value, ensure_ascii=False)


def markdown_heading(text: Any, level: int) -> str:
    """Render a markdown heading with a clamped heading level."""

    heading_level = max(1, min(6, int(level)))
    return f"{'#' * heading_level} {markdown_inline_text(text)}"


def markdown_paragraph(value: Any) -> str:
    """Render a paragraph block."""

    if value is None:
        return "_null_"
    if isinstance(value, list):
        return "\n\n".join(markdown_inline_text(item) for item in value)
    return markdown_inline_text(value)


def markdown_raw(value: Any) -> str:
    """Render a raw Markdown block without normalization."""

    if isinstance(value, str):
        return value.rstrip()
    if isinstance(value, list):
        return "\n".join(str(item) for item in value).rstrip()
    return markdown_inline_text(value)


def markdown_list(value: Any, ordered: bool = False) -> str:
    """Render a list block."""

    items = value if isinstance(value, list) else [value]
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        bullet = f"{index}." if ordered else "-"
        lines.append(f"{bullet} {markdown_inline_text(item)}")
    return "\n".join(lines)


def markdown_blockquote(value: Any) -> str:
    """Render a blockquote block."""

    if isinstance(value, str):
        lines = value.splitlines() or [value]
    elif isinstance(value, list):
        lines = [markdown_inline_text(item) for item in value] or [""]
    else:
        text = markdown_inline_text(value)
        lines = text.splitlines() or [text]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def markdown_code_block(value: Any, language: str = "") -> str:
    """Render a fenced code block."""

    if isinstance(value, str):
        code = value.rstrip()
    else:
        code = json.dumps(value, indent=2, ensure_ascii=False)
    fence = f"```{language.strip()}" if language.strip() else "```"
    return f"{fence}\n{code}\n```"


def markdown_escape_cell(value: Any) -> str:
    """Escape markdown table cell content."""

    text = markdown_inline_text(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def markdown_table(value: Any, schema_node: Any) -> str:
    """Render a markdown table from a list of row objects."""

    if isinstance(value, dict):
        rows = [value]
    elif isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict)]
    else:
        return markdown_paragraph(value)

    if not rows:
        return "_No rows_"

    columns: list[str] = []
    items_schema = schema_node.get("items") if isinstance(schema_node, dict) else {}
    if isinstance(items_schema, dict):
        properties = items_schema.get("properties")
        if isinstance(properties, dict):
            columns.extend(properties.keys())

    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)

    if not columns:
        return markdown_paragraph(value)

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(markdown_escape_cell(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def infer_markdown_kind(schema_node: Any, value: Any) -> str:
    """Infer the most appropriate markdown renderer for a value."""

    meta = markdown_meta(schema_node)
    kind = meta.get("kind")
    if kind:
        return str(kind)

    if isinstance(value, dict):
        if isinstance(schema_node, dict) and isinstance(schema_node.get("properties"), dict):
            return "section"
        return "paragraph"
    if isinstance(value, list):
        if not value:
            return "list"
        if all(isinstance(item, dict) for item in value):
            return "table"
        return "list"
    if value is None or isinstance(value, (str, int, float, bool)):
        return "paragraph"
    return "paragraph"


def render_markdown_key_values(mapping: dict[str, Any]) -> list[str]:
    """Fallback renderer for raw object content."""

    return [f"- **{key}**: {markdown_inline_text(value)}" for key, value in mapping.items()]


def render_markdown_properties(schema_node: Any, data: Any, level: int) -> list[str]:
    """Render the properties of an object schema in definition order."""

    if not isinstance(schema_node, dict) or not isinstance(data, dict):
        return []

    properties = schema_node.get("properties", {})
    if not isinstance(properties, dict):
        return []

    blocks: list[str] = []
    for name, property_schema in properties.items():
        if name not in data:
            continue
        blocks.extend(render_markdown_field(name, property_schema, data[name], level))
    return blocks


def render_markdown_field(field_name: str, schema_node: Any, value: Any, level: int) -> list[str]:
    """Render a single schema-backed value as markdown blocks."""

    if not isinstance(schema_node, dict):
        return [markdown_paragraph(value)]

    meta = markdown_meta(schema_node)
    kind = infer_markdown_kind(schema_node, value)
    heading_level = max(1, min(6, int(meta.get("level", level))))
    blocks: list[str] = []

    if kind == "heading":
        heading_text = meta.get("heading", value if isinstance(value, str) else field_name)
        blocks.append(markdown_heading(heading_text, heading_level))
        return blocks

    if kind == "paragraph":
        if meta.get("label"):
            return [f"**{field_name}**: {markdown_paragraph(value)}"]
        return [markdown_paragraph(value)]

    if kind == "raw":
        return [markdown_raw(value)]

    if kind == "list":
        return [markdown_list(value, ordered=False)]

    if kind == "ordered-list":
        return [markdown_list(value, ordered=True)]

    if kind == "table":
        return [markdown_table(value, schema_node)]

    if kind == "code":
        return [markdown_code_block(value, str(meta.get("language", "")))]

    if kind == "blockquote":
        return [markdown_blockquote(value)]

    if kind == "section":
        heading_text = meta.get("heading", schema_node.get("title", field_name))
        if heading_text:
            blocks.append(markdown_heading(heading_text, heading_level))

        if isinstance(value, dict):
            child_blocks = render_markdown_properties(schema_node, value, heading_level + 1)
            if child_blocks:
                blocks.extend(child_blocks)
            else:
                blocks.extend(render_markdown_key_values(value))
            return blocks

        if isinstance(value, list):
            item_schema = schema_node.get("items", {})
            for index, item in enumerate(value, start=1):
                item_heading = meta.get("item_heading", f"{field_name} {index}")
                if isinstance(item_schema, dict) and item_schema:
                    blocks.extend(render_markdown_field(item_heading, item_schema, item, heading_level + 1))
                else:
                    blocks.append(markdown_heading(item_heading, heading_level + 1))
                    blocks.append(markdown_paragraph(item))
            return blocks

        blocks.append(markdown_paragraph(value))
        return blocks

    if isinstance(value, dict):
        child_blocks = render_markdown_properties(schema_node, value, level)
        if child_blocks:
            return child_blocks
        return render_markdown_key_values(value)

    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return [markdown_table(value, schema_node)]
        return [markdown_list(value)]

    return [markdown_paragraph(value)]


def render_markdown_document(schema_node: dict[str, Any], data: Any) -> str:
    """Render a full markdown document from a schema contract and matching data."""

    validate_schema_node(schema_node)
    validate_instance_against_schema(schema_node, data)

    blocks: list[str] = []
    title = schema_node.get("title")
    if title:
        blocks.append(markdown_heading(title, 1))

    description = schema_node.get("description")
    if description:
        blocks.append(markdown_paragraph(description))

    if schema_node.get("type") == "object" and isinstance(data, dict):
        body_blocks = render_markdown_properties(schema_node, data, 2 if title else 1)
        if not body_blocks:
            body_blocks = render_markdown_key_values(data)
        blocks.extend(body_blocks)
    else:
        blocks.extend(render_markdown_field(schema_node.get("title", "Document"), schema_node, data, 2 if title else 1))

    rendered = "\n\n".join(block for block in blocks if block).rstrip()
    return f"{rendered}\n"
