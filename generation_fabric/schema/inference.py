"""Schema inference helpers."""

from __future__ import annotations

import json
from typing import Any

from generation_fabric.exceptions import SchemaError


def schema_signature(value: Any) -> str:
    """Return a stable signature used for deduplicating inferred schemas."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def unique_values(values: list[Any]) -> list[Any]:
    """Deduplicate JSON-compatible values while preserving order."""

    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        signature = schema_signature(value)
        if signature in seen:
            continue
        seen.add(signature)
        result.append(value)
    return result


def infer_schema_from_value(value: Any) -> Any:
    """Infer a JSON Schema fragment from a JSON-compatible Python value."""

    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {}}
        items = [infer_schema_from_value(item) for item in value]
        return {"type": "array", "items": merge_schema_choices(items)}
    if isinstance(value, dict):
        properties: dict[str, Any] = {}
        required: list[str] = []
        for key, item in value.items():
            properties[key] = infer_schema_from_value(item)
            required.append(key)

        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    raise SchemaError(f"cannot infer a schema from value of type {type(value).__name__}")


def merge_object_schemas(schemas: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a set of inferred object schemas into one object schema."""

    if not schemas:
        return {"type": "object", "properties": {}}

    property_sets = [set(schema.get("properties", {}).keys()) for schema in schemas]
    all_keys = sorted(set().union(*property_sets))
    required = sorted(set.intersection(*property_sets)) if property_sets else []

    properties: dict[str, Any] = {}
    for key in all_keys:
        key_schemas = [schema["properties"][key] for schema in schemas if key in schema.get("properties", {})]
        properties[key] = merge_schema_choices(key_schemas)

    merged: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        merged["required"] = required
    return merged


def merge_schema_choices(schemas: list[Any]) -> Any:
    """Merge inferred schemas for heterogeneous arrays or variant sets."""

    choices = unique_values(schemas)
    if not choices:
        return {}
    if len(choices) == 1:
        return choices[0]

    if all(isinstance(schema, dict) and schema.get("type") == "object" for schema in choices):
        return merge_object_schemas([schema for schema in choices if isinstance(schema, dict)])

    if all(isinstance(schema, dict) and schema.get("type") == "array" for schema in choices):
        item_schemas = [schema.get("items", {}) for schema in choices if isinstance(schema, dict)]
        return {"type": "array", "items": merge_schema_choices(item_schemas)}

    scalar_types = {
        schema.get("type")
        for schema in choices
        if isinstance(schema, dict) and isinstance(schema.get("type"), str)
    }
    if len(scalar_types) == len(choices):
        if scalar_types == {"integer", "number"}:
            return {"type": "number"}
        if len(scalar_types) == 1:
            return choices[0]

    return {"anyOf": choices}


def build_inferred_schema(sample: Any, title: str, description: str, draft: str) -> dict[str, Any]:
    """Create a complete schema document from a sample JSON value."""

    schema: dict[str, Any] = infer_schema_from_value(sample)
    if not isinstance(schema, dict):
        schema = {"type": "object", "properties": {}}

    schema = dict(schema)
    schema["$schema"] = draft
    schema["title"] = title
    if description:
        schema["description"] = description

    return schema
