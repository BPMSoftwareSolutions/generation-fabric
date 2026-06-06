"""Atomic JSON and text file helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from generation_fabric.exceptions import SchemaError


def parse_value(raw: str, force_string: bool = False) -> Any:
    """Parse a CLI value into JSON when possible."""

    if force_string:
        return raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def read_json_file(path: Path) -> Any:
    """Load and validate a JSON object from disk."""

    if not path.exists():
        raise SchemaError(f"schema file does not exist: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SchemaError("JSON Schema root must be a JSON object")

    return data


def write_json_file_atomic(path: Path, data: Any) -> None:
    """Write JSON to disk atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_text_file_atomic(path: Path, text: str) -> None:
    """Write text to disk atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def load_json_source(source: str) -> Any:
    """Load JSON from an inline string or a JSON file path."""

    candidate = Path(source)
    if candidate.exists() and candidate.is_file():
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SchemaError(f"invalid JSON in {candidate}: {exc}") from exc

    try:
        return json.loads(source)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid JSON value: {exc}") from exc


def load_json_file(path_text: str) -> Any:
    """Load JSON from an explicit file path."""

    path = Path(path_text)
    if not path.exists():
        raise SchemaError(f"JSON file does not exist: {path}")
    if not path.is_file():
        raise SchemaError(f"JSON path is not a file: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid JSON in {path}: {exc}") from exc
