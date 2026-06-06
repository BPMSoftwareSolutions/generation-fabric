"""Schema document creation and mutation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic
from generation_fabric.core.pointer import decode_pointer, parse_list_index, resolve_parent
from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.validation import validate_schema_node

DEFAULT_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def parse_type_spec(raw: str) -> Any:
    """Parse a JSON Schema type value."""

    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise SchemaError("root type cannot be empty")
    if len(parts) == 1:
        return parts[0]
    return parts


def new_schema(
    output: Path,
    title: str,
    description: str = "",
    root_type: str = "object",
    draft: str = DEFAULT_SCHEMA_DRAFT,
    extra_json: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create a new JSON Schema document and write it to disk."""

    if output.exists() and not overwrite:
        raise SchemaError(f"refusing to overwrite existing file: {output}")

    schema: dict[str, Any] = {
        "$schema": draft,
        "title": title,
        "type": parse_type_spec(root_type),
    }

    if description:
        schema["description"] = description

    root_type_value = schema["type"]
    if root_type_value == "object" or (isinstance(root_type_value, list) and "object" in root_type_value):
        schema.setdefault("properties", {})
        schema.setdefault("required", [])
    if root_type_value == "array" or (isinstance(root_type_value, list) and "array" in root_type_value):
        schema.setdefault("items", {})

    if extra_json:
        try:
            extra = json.loads(extra_json)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"invalid JSON for --extra-json: {exc}") from exc
        if not isinstance(extra, dict):
            raise SchemaError("--extra-json must decode to a JSON object")
        schema.update(extra)

    validate_schema_node(schema)
    write_json_file_atomic(output, schema)
    return schema


def attach_combinator(root: dict[str, Any], pointer: str, keyword: str, variants: list[Any]) -> dict[str, Any]:
    """Attach oneOf/anyOf metadata at the requested schema node."""

    if not variants:
        raise SchemaError(f"{keyword} requires at least one variant")

    segments = decode_pointer(pointer)
    if not segments:
        node: Any = root
    else:
        parent, key = resolve_parent(root, segments, create_missing=True)
        if isinstance(parent, dict):
            if key not in parent:
                parent[key] = {}
            node = parent[key]
        elif isinstance(parent, list):
            if key == "-":
                parent.append({})
                node = parent[-1]
            else:
                index = parse_list_index(key, len(parent), allow_end=True)
                if index == len(parent):
                    parent.append({})
                    node = parent[-1]
                else:
                    node = parent[index]
        else:
            raise SchemaError("cannot attach a combinator inside a non-container JSON value")

    if not isinstance(node, dict):
        raise SchemaError("combinator targets must be JSON object schemas")

    node[keyword] = variants
    return root
