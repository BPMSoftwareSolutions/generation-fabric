"""Registry of supported Markdown contract kinds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import load_json_file, read_json_file
from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

DEFAULT_MARKDOWN_CONTRACT_KIND = "release-notes"
REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"


@dataclass(frozen=True)
class MarkdownContractSpec:
    """Describe a Markdown contract kind and its canonical assets."""

    kind: str
    schema_path: Path
    sample_path: Path
    base_name: str = ""


MARKDOWN_CONTRACTS: dict[str, MarkdownContractSpec] = {
    DEFAULT_MARKDOWN_CONTRACT_KIND: MarkdownContractSpec(
        kind=DEFAULT_MARKDOWN_CONTRACT_KIND,
        schema_path=EXAMPLES_DIR / "release-notes.schema.json",
        sample_path=EXAMPLES_DIR / "release-notes.json",
        base_name="release-notes",
    ),
    "docs-showcase": MarkdownContractSpec(
        kind="docs-showcase",
        schema_path=EXAMPLES_DIR / "docs-showcase.schema.json",
        sample_path=EXAMPLES_DIR / "docs-showcase.json",
        base_name="docs-showcase",
    ),
    "readme": MarkdownContractSpec(
        kind="readme",
        schema_path=EXAMPLES_DIR / "readme.schema.json",
        sample_path=EXAMPLES_DIR / "readme.json",
        base_name="readme",
    ),
    "workflow-showcase": MarkdownContractSpec(
        kind="workflow-showcase",
        schema_path=EXAMPLES_DIR / "workflow-showcase.schema.json",
        sample_path=EXAMPLES_DIR / "workflow-showcase.json",
        base_name="workflow-showcase",
    ),
    "table-showcase": MarkdownContractSpec(
        kind="table-showcase",
        schema_path=EXAMPLES_DIR / "table-showcase.schema.json",
        sample_path=EXAMPLES_DIR / "table-showcase.json",
        base_name="table-showcase",
    ),
    "raw-sections-showcase": MarkdownContractSpec(
        kind="raw-sections-showcase",
        schema_path=EXAMPLES_DIR / "raw-sections-showcase.schema.json",
        sample_path=EXAMPLES_DIR / "raw-sections-showcase.json",
        base_name="raw-sections-showcase",
    ),
}


def normalize_markdown_contract_kind(kind: str) -> str:
    """Normalize a contract kind for registry lookup."""

    return kind.strip().lower().replace(" ", "-")


def list_markdown_contract_kinds() -> list[str]:
    """Return the supported contract kinds in deterministic order."""

    return sorted(MARKDOWN_CONTRACTS.keys())


def get_markdown_contract_spec(kind: str) -> MarkdownContractSpec:
    """Look up the registered contract spec for a kind."""

    normalized_kind = normalize_markdown_contract_kind(kind)
    try:
        return MARKDOWN_CONTRACTS[normalized_kind]
    except KeyError as exc:
        raise SchemaError(f"unsupported markdown contract kind: {kind}") from exc


def load_markdown_contract(kind: str) -> tuple[dict[str, Any], Any]:
    """Load and validate a registered Markdown contract."""

    spec = get_markdown_contract_spec(kind)
    schema = read_json_file(spec.schema_path)
    sample = load_json_file(spec.sample_path)
    validate_schema_node(schema)
    validate_instance_against_schema(schema, sample)
    return schema, sample
