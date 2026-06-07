"""Shared JSON-friendly serialization helpers."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any


def to_jsonable_dataclass(value: Any) -> Any:
    """Convert a dataclass into JSON-friendly data with stable tuple handling."""

    return json.loads(json.dumps(asdict(value), ensure_ascii=False))


__all__ = ["to_jsonable_dataclass"]
