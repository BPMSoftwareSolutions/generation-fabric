"""Markdown import helpers for legacy document migration."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})(?P<language>[A-Za-z0-9_+-]*)\s*$")
UNORDERED_LIST_RE = re.compile(r"^\s*[-+*]\s+(.*\S?)\s*$")
ORDERED_LIST_RE = re.compile(r"^\s*\d+\.\s+(.*\S?)\s*$")


def _normalize_title(value: str) -> str:
    """Turn a file stem into a readable fallback title."""

    text = value.replace("_", " ").replace("-", " ").strip()
    return text.title() if text else "Imported Markdown"


def _split_table_cells(line: str) -> list[str]:
    """Split a Markdown table row into cells."""

    raw_cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [cell.replace(r"\|", "|").strip() for cell in raw_cells]


def _is_table_separator(line: str) -> bool:
    """Return True when a row looks like a Markdown table separator."""

    cells = _split_table_cells(line)
    return len(cells) >= 2 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _looks_like_table_start(lines: list[str], index: int) -> bool:
    """Return True when the current line starts a Markdown table."""

    if index + 1 >= len(lines):
        return False
    current = lines[index]
    return "|" in current and _is_table_separator(lines[index + 1])


def _is_block_start(lines: list[str], index: int) -> bool:
    """Return True when a line starts a new Markdown block."""

    line = lines[index]
    stripped = line.strip()
    if not stripped:
        return True
    if HEADING_RE.match(line):
        return True
    if FENCE_RE.match(stripped):
        return True
    if UNORDERED_LIST_RE.match(line):
        return True
    if ORDERED_LIST_RE.match(line):
        return True
    if line.lstrip().startswith(">"):
        return True
    return _looks_like_table_start(lines, index)


def _parse_markdown_blocks(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse a Markdown document into a title and an ordered block list."""

    lines = text.splitlines()
    title = ""
    title_claimed = False
    seen_content = False
    blocks: list[dict[str, Any]] = []
    paragraph_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines, seen_content
        if not paragraph_lines:
            return
        paragraph = "\n".join(part.rstrip() for part in paragraph_lines).rstrip()
        is_raw = len(paragraph_lines) > 1
        paragraph_lines = []
        if paragraph:
            blocks.append({"kind": "raw" if is_raw else "paragraph", "text": paragraph})
            seen_content = True

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            if not title_claimed and not seen_content and level == 1:
                title = heading_text
                title_claimed = True
                index += 1
                continue
            blocks.append({"kind": "heading", "level": level, "text": heading_text})
            seen_content = True
            index += 1
            continue

        fence_match = FENCE_RE.match(stripped)
        if fence_match:
            flush_paragraph()
            fence = fence_match.group("fence")
            language = fence_match.group("language") or ""
            index += 1
            code_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip().startswith(fence):
                    break
                code_lines.append(candidate)
                index += 1
            if index >= len(lines):
                raise SchemaError("unterminated fenced code block in Markdown source")
            index += 1
            blocks.append({"kind": "code", "language": language, "text": "\n".join(code_lines).rstrip("\n")})
            seen_content = True
            continue

        if _looks_like_table_start(lines, index):
            flush_paragraph()
            headers = _split_table_cells(lines[index])
            if any(not header for header in headers):
                raise SchemaError("table headers must not be empty")
            if len(set(headers)) != len(headers):
                raise SchemaError("table headers must be unique")

            index += 2
            rows: list[dict[str, Any]] = []
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip() or "|" not in candidate or _is_block_start(lines, index):
                    break
                cells = _split_table_cells(candidate)
                row = {}
                for position, header in enumerate(headers):
                    row[header] = cells[position] if position < len(cells) else ""
                rows.append(row)
                index += 1

            blocks.append({"kind": "table", "headers": headers, "rows": rows})
            seen_content = True
            continue

        unordered_match = UNORDERED_LIST_RE.match(line)
        ordered_match = ORDERED_LIST_RE.match(line)
        if unordered_match or ordered_match:
            flush_paragraph()
            ordered = bool(ordered_match)
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                current_match = ORDERED_LIST_RE.match(candidate) if ordered else UNORDERED_LIST_RE.match(candidate)
                if not current_match:
                    break
                item_text = current_match.group(1).strip()
                index += 1
                continuation: list[str] = []
                while index < len(lines):
                    continuation_line = lines[index]
                    if not continuation_line.strip():
                        break
                    if _is_block_start(lines, index):
                        break
                    if continuation_line.startswith(" ") or continuation_line.startswith("\t"):
                        continuation.append(continuation_line.strip())
                        index += 1
                        continue
                    break
                if continuation:
                    item_text = " ".join([item_text, *continuation]).strip()
                items.append(item_text)
                if index < len(lines) and not lines[index].strip():
                    break
            blocks.append({"kind": "ordered-list" if ordered else "list", "ordered": ordered, "items": items})
            seen_content = True
            continue

        if line.lstrip().startswith(">"):
            flush_paragraph()
            quote_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                if not candidate.lstrip().startswith(">"):
                    break
                quote_lines.append(re.sub(r"^\s*>\s?", "", candidate))
                index += 1
            blocks.append({"kind": "blockquote", "text": "\n".join(quote_lines).rstrip()})
            seen_content = True
            continue

        paragraph_lines.append(stripped)
        seen_content = True
        index += 1

    flush_paragraph()

    if not title:
        title = "Imported Markdown"

    return title, blocks


def _property_name(kind: str, count: int, level: int | None = None) -> str:
    """Generate a stable property name for an imported block."""

    if kind == "heading" and level is not None:
        return f"heading_h{level}_{count}"
    if kind == "ordered-list":
        return f"ordered_list_{count}"
    return f"{kind.replace('-', '_')}_{count}"


def _schema_and_value_for_block(block: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """Translate a parsed Markdown block into schema and sample data."""

    kind = block["kind"]
    if kind == "heading":
        return (
            {
                "type": "string",
                "x-markdown": {
                    "kind": "heading",
                    "level": int(block.get("level", 1)),
                },
            },
            block.get("text", ""),
        )

    if kind == "paragraph":
        return (
            {
                "type": "string",
                "x-markdown": {"kind": "paragraph"},
            },
            block.get("text", ""),
        )

    if kind == "raw":
        return (
            {
                "type": "string",
                "x-markdown": {"kind": "raw"},
            },
            block.get("text", ""),
        )

    if kind == "list":
        return (
            {
                "type": "array",
                "items": {"type": "string"},
                "x-markdown": {"kind": "list"},
            },
            block.get("items", []),
        )

    if kind == "ordered-list":
        return (
            {
                "type": "array",
                "items": {"type": "string"},
                "x-markdown": {"kind": "ordered-list"},
            },
            block.get("items", []),
        )

    if kind == "blockquote":
        return (
            {
                "type": "string",
                "x-markdown": {"kind": "blockquote"},
            },
            block.get("text", ""),
        )

    if kind == "code":
        return (
            {
                "type": "string",
                "x-markdown": {
                    "kind": "code",
                    "language": block.get("language", ""),
                },
            },
            block.get("text", ""),
        )

    if kind == "table":
        headers = list(block.get("headers", []))
        properties = {header: {"type": "string"} for header in headers}
        return (
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": headers,
                    "additionalProperties": False,
                },
                "x-markdown": {"kind": "table"},
            },
            block.get("rows", []),
        )

    raise SchemaError(f"unsupported Markdown block kind: {kind}")


def build_markdown_import_contract(
    text: str,
    title: str = "",
    description: str = "",
    draft: str = DEFAULT_SCHEMA_DRAFT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a schema and sample JSON contract from a Markdown document."""

    inferred_title, blocks = _parse_markdown_blocks(text)
    schema_title = title or inferred_title
    schema: dict[str, Any] = {
        "$schema": draft,
        "title": schema_title,
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    if description:
        schema["description"] = description

    sample: dict[str, Any] = {}
    counts: dict[str, int] = defaultdict(int)

    for block in blocks:
        counts[block["kind"]] += 1
        property_name = _property_name(block["kind"], counts[block["kind"]], block.get("level"))
        block_schema, block_value = _schema_and_value_for_block(block)
        schema["properties"][property_name] = block_schema
        schema["required"].append(property_name)
        sample[property_name] = block_value

    validate_schema_node(schema)
    validate_instance_against_schema(schema, sample)
    return schema, sample


def scaffold_markdown_import(
    source_file: str,
    directory: str,
    base_name: str = "",
    title: str = "",
    description: str = "",
    with_markdown: bool = False,
    overwrite: bool = False,
    draft: str = DEFAULT_SCHEMA_DRAFT,
) -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
    """Import a Markdown file into a schema, sample JSON, and optional rendered Markdown."""

    source_path = Path(source_file)
    if not source_path.exists():
        raise SchemaError(f"Markdown file does not exist: {source_path}")
    if not source_path.is_file():
        raise SchemaError(f"Markdown path is not a file: {source_path}")

    text = source_path.read_text(encoding="utf-8")
    schema, sample = build_markdown_import_contract(text, title=title, description=description, draft=draft)

    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    effective_base = base_name or source_path.stem
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
