"""Shared artifact path and writer helpers for generated contract files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError


@dataclass(frozen=True)
class SchemaDataPaths:
    """Describe a schema plus JSON sidecar pair."""

    schema_path: Path
    data_path: Path

    def all_paths(self) -> tuple[Path, ...]:
        """Return all paths that belong to this artifact set."""

        return (self.schema_path, self.data_path)


@dataclass(frozen=True)
class SidecarPaths(SchemaDataPaths):
    """Describe a schema, JSON data, and primary rendered artifact."""

    primary_path: Path

    @property
    def markdown_path(self) -> Path:
        """Provide a compatibility alias for Markdown-oriented reports."""

        return self.primary_path

    def all_paths(self) -> tuple[Path, ...]:
        """Return all paths that belong to this artifact set."""

        return (self.schema_path, self.data_path, self.primary_path)


@dataclass(frozen=True)
class SchemaDataArtifact:
    """Hold the JSON schema and JSON data for a generated artifact."""

    schema: dict[str, Any]
    data: Any


@dataclass(frozen=True)
class ContractArtifact:
    """Hold the schema, JSON data, and rendered text for a generated artifact."""

    schema: dict[str, Any]
    data: Any
    primary_text: str


def resolve_schema_data_paths(output: str, default_path: Path) -> SchemaDataPaths:
    """Resolve the standard schema plus JSON sidecar filenames."""

    path = Path(output) if output else default_path
    if not path.suffix:
        path = path.with_suffix(".json")
    return SchemaDataPaths(schema_path=path.with_name(f"{path.stem}.schema.json"), data_path=path)


def resolve_sidecar_paths(output: str, default_path: Path) -> SidecarPaths:
    """Resolve the standard schema, JSON, and primary artifact filenames."""

    path = Path(output) if output else default_path
    if not path.suffix:
        path = path.with_suffix(".md")
    stem = path.stem
    return SidecarPaths(
        schema_path=path.with_name(f"{stem}.schema.json"),
        data_path=path.with_name(f"{stem}.json"),
        primary_path=path,
    )


def assert_can_write(paths: SchemaDataPaths, overwrite: bool) -> None:
    """Refuse to overwrite any existing artifact when overwrite is disabled."""

    for target in paths.all_paths():
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")


def write_schema_data_artifact(paths: SchemaDataPaths, artifact: SchemaDataArtifact, *, overwrite: bool = False) -> None:
    """Write a schema plus JSON artifact pair to disk."""

    assert_can_write(paths, overwrite)
    write_json_file_atomic(paths.schema_path, artifact.schema)
    write_json_file_atomic(paths.data_path, artifact.data)


def write_contract_artifact(paths: SidecarPaths, artifact: ContractArtifact, *, overwrite: bool = False) -> None:
    """Write a schema, JSON data, and rendered text artifact set to disk."""

    assert_can_write(paths, overwrite)
    write_json_file_atomic(paths.schema_path, artifact.schema)
    write_json_file_atomic(paths.data_path, artifact.data)
    write_text_file_atomic(paths.primary_path, artifact.primary_text)


__all__ = [
    "ContractArtifact",
    "SchemaDataArtifact",
    "SchemaDataPaths",
    "SidecarPaths",
    "assert_can_write",
    "resolve_schema_data_paths",
    "resolve_sidecar_paths",
    "write_contract_artifact",
    "write_schema_data_artifact",
]
