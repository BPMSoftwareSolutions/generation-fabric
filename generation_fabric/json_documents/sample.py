"""Schema-driven JSON sample generation helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from generation_fabric.core.pointer import get_node
from generation_fabric.exceptions import SchemaError
from generation_fabric.json_documents.crud import read_node
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

MAX_SAMPLE_DEPTH = 16
TYPE_PRIORITY = ("object", "array", "string", "integer", "number", "boolean", "null")


def _deepcopy_json(value: Any) -> Any:
    """Return a JSON-safe deep copy of a sample value."""

    return deepcopy(value)


def _explicit_sample(schema: dict[str, Any]) -> tuple[Any, bool]:
    """Return the strongest explicit sample hint on a schema node."""

    if "x-sample" in schema:
        return _deepcopy_json(schema["x-sample"]), True
    if "const" in schema:
        return _deepcopy_json(schema["const"]), True

    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return _deepcopy_json(examples[0]), True

    if "default" in schema:
        return _deepcopy_json(schema["default"]), True

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return _deepcopy_json(enum_values[0]), True

    return None, False


def _schema_types(schema: dict[str, Any]) -> list[str]:
    """Return the candidate JSON types for a schema node."""

    type_value = schema.get("type")
    if isinstance(type_value, str):
        return [type_value]
    if isinstance(type_value, list):
        return [item for item in type_value if isinstance(item, str)]

    if any(key in schema for key in ("properties", "required", "additionalProperties", "patternProperties")):
        return ["object"]
    if any(key in schema for key in ("items", "prefixItems", "contains", "minItems")):
        return ["array"]

    return []


def _choose_type(types: list[str]) -> str:
    """Pick a deterministic type from a schema type union."""

    seen = set(types)
    for candidate in TYPE_PRIORITY:
        if candidate in seen:
            return candidate
    if types:
        return types[0]
    return "object"


def _resolve_local_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolve a local JSON Schema reference."""

    if not ref.startswith("#"):
        raise SchemaError("only local $ref values are supported")
    if ref == "#":
        target = root_schema
    else:
        fragment = ref[1:]
        if not fragment.startswith("/"):
            raise SchemaError("only JSON Pointer local refs are supported")
        target = get_node(root_schema, fragment)

    if not isinstance(target, dict):
        raise SchemaError(f"$ref target must be a JSON object schema: {ref}")
    return target


def _deep_merge(left: Any, right: Any) -> Any:
    """Merge two JSON values for allOf composition."""

    if isinstance(left, dict) and isinstance(right, dict):
        merged = dict(left)
        for key, value in right.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = _deepcopy_json(value)
        return merged
    return _deepcopy_json(right)


def _placeholder_for_schema(schema: dict[str, Any]) -> Any:
    """Return a generic fallback sample for a schema node."""

    types = _schema_types(schema)
    chosen = _choose_type(types)
    if chosen == "object":
        return {}
    if chosen == "array":
        return []
    if chosen == "integer":
        return 1
    if chosen == "number":
        return 1.0
    if chosen == "boolean":
        return True
    if chosen == "null":
        return None
    return "sample"


def _string_sample(schema: dict[str, Any]) -> str:
    """Generate a representative string sample."""

    markdown = schema.get("x-markdown")
    if isinstance(markdown, dict):
        kind = str(markdown.get("kind", ""))
        language = str(markdown.get("language", "")).lower()

        if kind == "heading":
            return "Example Heading"
        if kind == "paragraph":
            return "Example paragraph text."
        if kind == "blockquote":
            return "Example quoted text."
        if kind == "raw":
            return "Example raw text.\nSecond line."
        if kind == "code":
            if language == "mermaid":
                return "flowchart LR\n  A[Source] --> B[Target]\n"
            if language in {"text", "plain", "plaintext"}:
                return (
                    "+----------------------+\n"
                    "| Example Sketch       |\n"
                    "+----------------------+\n"
                )
            if language == "json":
                return '{\n  "example": true\n}'
            if language in {"csharp", "cs", "c#"}:
                return (
                    "public sealed class Example\n"
                    "{\n"
                    "    public string Name { get; set; } = \"Example\";\n"
                    "}"
                )
            return "example code"

    string_format = str(schema.get("format", ""))
    if string_format == "email":
        return "user@example.com"
    if string_format == "uri":
        return "https://example.com"
    if string_format == "uuid":
        return "123e4567-e89b-12d3-a456-426614174000"
    if string_format == "date":
        return "2026-01-01"
    if string_format == "date-time":
        return "2026-01-01T00:00:00Z"
    if string_format == "time":
        return "12:00:00Z"
    if string_format == "ipv4":
        return "127.0.0.1"
    if string_format == "ipv6":
        return "::1"
    if string_format == "hostname":
        return "example.com"

    return "sample"


def _generate_object_sample(
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    depth: int,
    seen_refs: set[str],
) -> dict[str, Any]:
    """Generate a sample for an object schema."""

    result: dict[str, Any] = {}
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return result

    for key, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            continue
        result[key] = build_json_sample(prop_schema, root_schema=root_schema, depth=depth + 1, seen_refs=seen_refs)
    return result


def _generate_array_sample(
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    depth: int,
    seen_refs: set[str],
) -> list[Any]:
    """Generate a sample for an array schema."""

    prefix_items = schema.get("prefixItems")
    items_schema = schema.get("items")
    min_items = schema.get("minItems", 0)
    desired_length = 1
    if isinstance(min_items, int) and min_items > desired_length:
        desired_length = min_items
    if isinstance(prefix_items, list) and prefix_items:
        desired_length = max(desired_length, len(prefix_items))

    result: list[Any] = []

    if isinstance(prefix_items, list) and prefix_items:
        for item_schema in prefix_items:
            if not isinstance(item_schema, dict):
                continue
            result.append(build_json_sample(item_schema, root_schema=root_schema, depth=depth + 1, seen_refs=seen_refs))

    if isinstance(items_schema, dict):
        while len(result) < desired_length:
            result.append(build_json_sample(items_schema, root_schema=root_schema, depth=depth + 1, seen_refs=seen_refs))
    elif not result and desired_length > 0:
        result.append(None)

    return result


def _merge_allof_samples(samples: list[Any]) -> Any:
    """Merge samples produced from allOf branches."""

    if not samples:
        return {}

    merged = _deepcopy_json(samples[0])
    for sample in samples[1:]:
        merged = _deep_merge(merged, sample)
    return merged


def _generate_combinator_sample(
    schema: dict[str, Any],
    keyword: str,
    root_schema: dict[str, Any],
    depth: int,
    seen_refs: set[str],
) -> Any:
    """Generate a sample from oneOf, anyOf, or allOf branches."""

    variants = schema.get(keyword, [])
    if not isinstance(variants, list) or not variants:
        raise SchemaError(f"{keyword} requires at least one schema variant")

    if keyword == "allOf":
        samples = [
            build_json_sample(variant, root_schema=root_schema, depth=depth + 1, seen_refs=seen_refs)
            for variant in variants
            if isinstance(variant, dict)
        ]
        return _merge_allof_samples(samples)

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        sample = build_json_sample(variant, root_schema=root_schema, depth=depth + 1, seen_refs=seen_refs)
        try:
            validate_instance_against_schema(schema, sample)
        except SchemaError:
            continue
        return sample

    return build_json_sample(variants[0], root_schema=root_schema, depth=depth + 1, seen_refs=seen_refs)


def build_json_sample(
    schema: Any,
    *,
    root_schema: dict[str, Any] | None = None,
    depth: int = 0,
    seen_refs: set[str] | None = None,
) -> Any:
    """Generate a JSON sample from a JSON Schema node."""

    if not isinstance(schema, dict):
        raise SchemaError("schema nodes must be JSON object schemas")

    if root_schema is None:
        root_schema = schema
    if seen_refs is None:
        seen_refs = set()

    if depth > MAX_SAMPLE_DEPTH:
        return _placeholder_for_schema(schema)

    explicit_sample, has_explicit_sample = _explicit_sample(schema)
    if has_explicit_sample:
        return explicit_sample

    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str):
            raise SchemaError("$ref values must be strings")
        if ref in seen_refs:
            return _placeholder_for_schema(schema)
        seen_refs = set(seen_refs)
        seen_refs.add(ref)
        return build_json_sample(
            _resolve_local_ref(root_schema, ref),
            root_schema=root_schema,
            depth=depth + 1,
            seen_refs=seen_refs,
        )

    for keyword in ("allOf", "oneOf", "anyOf"):
        if keyword in schema:
            return _generate_combinator_sample(schema, keyword, root_schema, depth, seen_refs)

    types = _schema_types(schema)
    if types:
        chosen_type = _choose_type(types)
    elif "properties" in schema:
        chosen_type = "object"
    elif "items" in schema or "prefixItems" in schema:
        chosen_type = "array"
    else:
        chosen_type = "string"

    if chosen_type == "object":
        return _generate_object_sample(schema, root_schema, depth, seen_refs)
    if chosen_type == "array":
        return _generate_array_sample(schema, root_schema, depth, seen_refs)
    if chosen_type == "integer":
        return 1
    if chosen_type == "number":
        return 1.0
    if chosen_type == "boolean":
        return True
    if chosen_type == "null":
        return None
    return _string_sample(schema)


def build_json_sample_document(schema: dict[str, Any], root_schema: dict[str, Any] | None = None) -> Any:
    """Build and validate a sample document for a schema node."""

    validate_schema_node(schema)
    sample = build_json_sample(schema, root_schema=root_schema)
    validate_instance_against_schema(schema, sample)
    return sample


def build_json_sample_from_root(schema: dict[str, Any], pointer: str = "") -> Any:
    """Build and validate a sample from a schema root plus optional pointer."""

    target = read_node(schema, pointer) if pointer else schema
    if not isinstance(target, dict):
        raise SchemaError("schema nodes must be JSON object schemas")
    return build_json_sample_document(target, root_schema=schema)
