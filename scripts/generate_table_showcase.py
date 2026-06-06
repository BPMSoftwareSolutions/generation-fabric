"""Generate the table showcase example using the portable generation fabric."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.json_documents.sample import build_json_sample_document
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT

OUTPUT_DIR = REPO_ROOT / "examples"
SCHEMA_PATH = OUTPUT_DIR / "table-showcase.schema.json"
SAMPLE_PATH = OUTPUT_DIR / "table-showcase.json"
MARKDOWN_PATH = OUTPUT_DIR / "table-showcase.md"

TABLE_SHOWCASE_SCHEMA: dict[str, object] = {
    "$schema": DEFAULT_SCHEMA_DRAFT,
    "title": "Table Showcase",
    "description": "A contract-driven example that demonstrates Markdown tables and structured document generation.",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intro": {
            "type": "string",
            "x-sample": "This example shows how the generation fabric can render tables from structured JSON.",
            "x-markdown": {"kind": "paragraph"},
        },
        "status_table": {
            "type": "array",
            "x-sample": [
                {
                    "artifact": "Schema",
                    "source": "json_schema_crud.py new",
                    "format": "JSON Schema",
                    "notes": "Defines the contract",
                },
                {
                    "artifact": "Sample JSON",
                    "source": "json-sample",
                    "format": "JSON",
                    "notes": "Generated from schema hints",
                },
                {
                    "artifact": "Markdown",
                    "source": "markdown",
                    "format": "Markdown",
                    "notes": "Rendered deterministically",
                },
            ],
            "x-markdown": {"kind": "table"},
            "items": {
                "type": "object",
                "properties": {
                    "artifact": {"type": "string"},
                    "source": {"type": "string"},
                    "format": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["artifact", "source", "format", "notes"],
                "additionalProperties": False,
            },
        },
        "action_items": {
            "type": "array",
            "items": {"type": "string"},
            "x-sample": [
                "Define the schema contract",
                "Generate the JSON sample",
                "Render Markdown from the sample",
            ],
            "x-markdown": {"kind": "ordered-list"},
        },
        "closing_note": {
            "type": "string",
            "x-sample": "The table is generated from JSON, and the JSON is generated from the schema.",
            "x-markdown": {"kind": "blockquote"},
        },
    },
    "required": ["intro", "status_table", "action_items", "closing_note"],
}


def generate_table_showcase() -> tuple[dict[str, object], dict[str, object], str]:
    """Write the table showcase schema, sample JSON, and Markdown files."""

    schema = TABLE_SHOWCASE_SCHEMA
    sample = build_json_sample_document(schema)
    markdown = render_markdown_document(schema, sample)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json_file_atomic(SCHEMA_PATH, schema)
    write_json_file_atomic(SAMPLE_PATH, sample)
    write_text_file_atomic(MARKDOWN_PATH, markdown)
    return schema, sample, markdown


def main() -> int:
    """Generate the showcase artifacts and report the output paths."""

    generate_table_showcase()
    print(f"generated: {SCHEMA_PATH}")
    print(f"generated: {SAMPLE_PATH}")
    print(f"generated: {MARKDOWN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
