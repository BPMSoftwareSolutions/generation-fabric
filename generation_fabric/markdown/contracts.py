"""Markdown contract scaffolding."""

from __future__ import annotations

from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

DEFAULT_MARKDOWN_CONTRACT_KIND = "release-notes"


def build_release_notes_markdown_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the canonical release-notes markdown contract and sample data."""

    schema: dict[str, Any] = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": "Release Notes",
        "description": "Contract-driven release notes generated from a JSON Schema.",
        "type": "object",
        "properties": {
            "version": {
                "type": "string",
                "x-markdown": {"kind": "paragraph", "label": True},
            },
            "released_on": {
                "type": "string",
                "x-markdown": {"kind": "paragraph", "label": True},
            },
            "summary": {
                "type": "string",
                "x-markdown": {"kind": "paragraph"},
            },
            "highlights": {
                "type": "array",
                "items": {"type": "string"},
                "x-markdown": {"kind": "list"},
            },
            "sections": {
                "type": "array",
                "x-markdown": {"kind": "section", "heading": ""},
                "items": {
                    "type": "object",
                    "x-markdown": {"kind": "section", "heading": ""},
                    "properties": {
                        "title": {
                            "type": "string",
                            "x-markdown": {"kind": "heading", "level": 2},
                        },
                        "summary": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph"},
                        },
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-markdown": {"kind": "list"},
                        },
                    },
                    "required": ["title", "summary", "bullets"],
                },
            },
        },
        "required": ["version", "released_on", "summary", "highlights", "sections"],
    }

    sample: dict[str, Any] = {
        "version": "1.0.0",
        "released_on": "2026-06-06",
        "summary": "Contract-driven Markdown generation is now part of the generation fabric.",
        "highlights": [
            "Schema-defined content structure",
            "Deterministic Markdown rendering",
            "Reusable scaffolding for new documents",
        ],
        "sections": [
            {
                "title": "Renderer",
                "summary": "The renderer now validates data and emits Markdown from a schema contract.",
                "bullets": [
                    "Validates the schema before rendering",
                    "Validates the JSON instance against the schema",
                    "Writes output atomically",
                ],
            },
            {
                "title": "Quality",
                "summary": "The contract ships with tests and a canonical example payload.",
                "bullets": [
                    "Unit tests cover the scaffold and render paths",
                    "Example files live in the repository",
                    "The schema and sample stay in sync",
                ],
            },
        ],
    }

    validate_schema_node(schema)
    validate_instance_against_schema(schema, sample)
    return schema, sample


def build_markdown_contract(kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a markdown contract template for a supported kind."""

    normalized_kind = kind.strip().lower()
    if normalized_kind == DEFAULT_MARKDOWN_CONTRACT_KIND:
        return build_release_notes_markdown_contract()

    raise SchemaError(f"unsupported markdown contract kind: {kind}")


def scaffold_markdown_contract(
    directory: str,
    kind: str = DEFAULT_MARKDOWN_CONTRACT_KIND,
    base_name: str = "",
    with_markdown: bool = False,
    overwrite: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
    """Write a contract schema, sample JSON, and optional rendered Markdown."""

    schema, sample = build_markdown_contract(kind)

    from pathlib import Path

    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    effective_base = base_name or kind.strip().lower().replace(" ", "-")
    schema_path = target_dir / f"{effective_base}.schema.json"
    data_path = target_dir / f"{effective_base}.json"
    markdown_path = target_dir / f"{effective_base}.md"

    targets = [schema_path, data_path]
    if with_markdown:
        targets.append(markdown_path)

    for target in targets:
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_json_file_atomic(schema_path, schema)
    write_json_file_atomic(data_path, sample)

    if with_markdown:
        rendered = render_markdown_document(schema, sample)
        write_text_file_atomic(markdown_path, rendered)

    return schema, sample, str(schema_path), str(data_path), str(markdown_path)
