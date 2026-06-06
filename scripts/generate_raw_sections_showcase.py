"""Generate the raw-sections showcase example using the portable generation fabric."""

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
SCHEMA_PATH = OUTPUT_DIR / "raw-sections-showcase.schema.json"
SAMPLE_PATH = OUTPUT_DIR / "raw-sections-showcase.json"
MARKDOWN_PATH = OUTPUT_DIR / "raw-sections-showcase.md"

RAW_SECTIONS_SCHEMA: dict[str, object] = {
    "$schema": DEFAULT_SCHEMA_DRAFT,
    "title": "Raw Sections Showcase",
    "description": "A contract-driven example that keeps raw Markdown syntax editable as structured sections.",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intro": {
            "type": "string",
            "x-sample": "This example shows that raw Markdown syntax can still be captured as editable JSON sections.",
            "x-markdown": {"kind": "paragraph"},
        },
        "sections": {
            "type": "array",
            "x-sample": [
                {
                    "title": "Inline HTML",
                    "summary": "Inline HTML can be preserved as raw Markdown text and edited through JSON.",
                    "snippet": "<details>\n  <summary>Expand me</summary>\n  <p>Hidden content can stay in the Markdown source.</p>\n</details>",
                    "notes": [
                        "The raw block is preserved without inventing a new HTML model.",
                        "The section remains editable through JSON CRUD operations.",
                    ],
                },
                {
                    "title": "Footnotes",
                    "summary": "Footnote references and definitions can be preserved as raw Markdown text.",
                    "snippet": "Here is a sentence with a footnote.[^1]\n\n[^1]: Footnotes are captured as raw markdown text.",
                    "notes": [
                        "The source remains easy to edit.",
                        "The renderer does not need special footnote semantics to keep the text intact.",
                    ],
                },
                {
                    "title": "Task Lists",
                    "summary": "Task list checkboxes can remain plain Markdown while still being tracked in JSON.",
                    "snippet": "- [ ] Draft schema\n- [x] Render output\n- [ ] Verify round-trip",
                    "notes": [
                        "Checkbox syntax stays visible in the output.",
                        "The JSON layer can still update the section body atomically.",
                    ],
                },
                {
                    "title": "Nested Lists",
                    "summary": "Nested list syntax can be preserved as raw Markdown content.",
                    "snippet": "- Parent\n  - Child\n  - Another child\n- Sibling",
                    "notes": [
                        "The structure remains readable in source control.",
                        "No custom nested-list model is required for pass-through use cases.",
                    ],
                },
                {
                    "title": "Definition Lists",
                    "summary": "Definition list syntax can be carried through as raw text.",
                    "snippet": "Term\n: Definition\nAnother term\n: Another definition",
                    "notes": [
                        "The importer does not need to normalize this into a special shape.",
                        "Editors can still update the text through CRUD operations.",
                    ],
                },
                {
                    "title": "Admonitions",
                    "summary": "Flavor-specific admonition syntax can live inside a raw section.",
                    "snippet": "> [!NOTE]\n> This content is preserved as blockquote-style markdown.\n> It can still be edited as raw text.",
                    "notes": [
                        "The fabric can preserve the syntax even when it does not interpret it semantically.",
                        "The source remains deterministic and diffable.",
                    ],
                },
                {
                    "title": "HTML Tables",
                    "summary": "HTML table markup can be preserved as raw Markdown source when needed.",
                    "snippet": "<table>\n  <tr><th>Name</th><th>Value</th></tr>\n  <tr><td>Alpha</td><td>1</td></tr>\n</table>",
                    "notes": [
                        "This keeps custom table layouts intact.",
                        "It avoids forcing HTML into a simplified Markdown table model.",
                    ],
                },
                {
                    "title": "Math",
                    "summary": "Inline and block math can remain raw source text in a Markdown section.",
                    "snippet": "Euler said $e^{i\\pi} + 1 = 0$ and display math can stay as plain text:\n$$\nx^2 + y^2 = z^2\n$$",
                    "notes": [
                        "Math delimiters stay visible in source.",
                        "A richer math renderer can be added later if we choose to invest in it.",
                    ],
                },
                {
                    "title": "Embedded Media",
                    "summary": "Images, iframes, and other embedded media can be preserved as raw content.",
                    "snippet": "<img src=\"diagram.png\" alt=\"Diagram\" />\n<iframe src=\"https://example.com/demo\"></iframe>",
                    "notes": [
                        "The section stays editable as raw Markdown text.",
                        "Media semantics can be layered on later if needed.",
                    ],
                },
            ],
            "x-markdown": {"kind": "section", "heading": ""},
            "items": {
                "type": "object",
                "x-markdown": {"kind": "section", "heading": ""},
                "properties": {
                    "title": {"type": "string", "x-markdown": {"kind": "heading", "level": 2}},
                    "summary": {"type": "string", "x-markdown": {"kind": "paragraph"}},
                    "snippet": {"type": "string", "x-markdown": {"kind": "raw"}},
                    "notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "x-markdown": {"kind": "list"},
                    },
                },
                "required": ["title", "summary", "snippet", "notes"],
                "additionalProperties": False,
            },
        },
        "closing_note": {
            "type": "string",
            "x-sample": "The section body can remain raw text while still being fully editable through JSON CRUD operations.",
            "x-markdown": {"kind": "blockquote"},
        },
    },
    "required": ["intro", "sections", "closing_note"],
}


def generate_raw_sections_showcase() -> tuple[dict[str, object], dict[str, object], str]:
    """Write the raw sections showcase schema, sample JSON, and Markdown files."""

    schema = RAW_SECTIONS_SCHEMA
    sample = build_json_sample_document(schema)
    markdown = render_markdown_document(schema, sample)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json_file_atomic(SCHEMA_PATH, schema)
    write_json_file_atomic(SAMPLE_PATH, sample)
    write_text_file_atomic(MARKDOWN_PATH, markdown)
    return schema, sample, markdown


def main() -> int:
    """Generate the showcase artifacts and report the output paths."""

    generate_raw_sections_showcase()
    print(f"generated: {SCHEMA_PATH}")
    print(f"generated: {SAMPLE_PATH}")
    print(f"generated: {MARKDOWN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
