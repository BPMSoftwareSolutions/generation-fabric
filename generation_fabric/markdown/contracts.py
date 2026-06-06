"""Markdown contract scaffolding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from generation_fabric.core.io import load_json_file, read_json_file, write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

DEFAULT_MARKDOWN_CONTRACT_KIND = "release-notes"
REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"


def _release_notes_contract_paths() -> tuple[Path, Path]:
    """Return the canonical example asset paths for the release-notes contract."""

    return EXAMPLES_DIR / "release-notes.schema.json", EXAMPLES_DIR / "release-notes.json"


def load_release_notes_markdown_contract() -> tuple[dict[str, Any], Any]:
    """Load the canonical release-notes markdown contract and sample data."""

    schema_path, sample_path = _release_notes_contract_paths()
    schema = read_json_file(schema_path)
    sample = load_json_file(sample_path)

    validate_schema_node(schema)
    validate_instance_against_schema(schema, sample)
    return schema, sample


def build_release_notes_markdown_contract() -> tuple[dict[str, Any], Any]:
    """Backward-compatible alias for loading the canonical release-notes contract."""

    return load_release_notes_markdown_contract()


def build_markdown_contract(kind: str) -> tuple[dict[str, Any], Any]:
    """Build a markdown contract template for a supported kind."""

    normalized_kind = kind.strip().lower()
    if normalized_kind == DEFAULT_MARKDOWN_CONTRACT_KIND:
        return load_release_notes_markdown_contract()

    raise SchemaError(f"unsupported markdown contract kind: {kind}")


def scaffold_markdown_contract(
    directory: str,
    kind: str = DEFAULT_MARKDOWN_CONTRACT_KIND,
    base_name: str = "",
    with_markdown: bool = False,
    overwrite: bool = False,
) -> tuple[dict[str, Any], Any, str, str, str]:
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
