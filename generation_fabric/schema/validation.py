"""Validation helpers for JSON Schema documents and instances."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JsonSchemaSchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from generation_fabric.exceptions import SchemaError


def validate_schema_node(schema_node: Any) -> None:
    """Validate that a schema fragment is syntactically valid."""

    if not isinstance(schema_node, dict):
        raise SchemaError("validation target must be a JSON object schema")

    try:
        Draft202012Validator.check_schema(schema_node)
    except JsonSchemaSchemaError as exc:
        raise SchemaError(f"schema is invalid: {exc.message}") from exc


def validate_instance_against_schema(schema_node: Any, instance: Any) -> None:
    """Validate an instance against a JSON Schema fragment."""

    if not isinstance(schema_node, dict):
        raise SchemaError("validation target must be a JSON object schema")

    validator = Draft202012Validator(schema_node)
    try:
        validator.validate(instance)
    except JsonSchemaValidationError as exc:
        location = "/".join(str(part) for part in exc.path)
        suffix = f" at /{location}" if location else ""
        raise SchemaError(f"instance validation failed{suffix}: {exc.message}") from exc
