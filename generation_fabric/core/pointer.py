"""JSON Pointer helpers."""

from __future__ import annotations

from typing import Any

from generation_fabric.exceptions import SchemaError


def decode_pointer(pointer: str) -> list[str]:
    """Decode a JSON Pointer into path segments."""

    if pointer in ("", "/"):
        return []
    if not pointer.startswith("/"):
        raise SchemaError("JSON Pointer must start with '/' or be empty for the root")

    segments = pointer.split("/")[1:]
    return [segment.replace("~1", "/").replace("~0", "~") for segment in segments]


def encode_pointer_segment(segment: str) -> str:
    """Encode a JSON Pointer segment."""

    return segment.replace("~", "~0").replace("/", "~1")


def parse_list_index(segment: str, length: int, allow_end: bool) -> int:
    """Parse a list index from a JSON Pointer segment."""

    if segment == "-" and allow_end:
        return length

    try:
        index = int(segment)
    except ValueError as exc:
        raise SchemaError(f"expected a list index, got '{segment}'") from exc

    if index < 0:
        raise SchemaError("list indices cannot be negative")
    if index > length or (not allow_end and index >= length):
        raise SchemaError("list index out of range")
    return index


def resolve_parent(root: Any, segments: list[str], create_missing: bool) -> tuple[Any, str]:
    """Resolve the parent node for a JSON Pointer path."""

    if not segments:
        raise SchemaError("root pointer cannot be used for this operation")

    node = root
    for segment in segments[:-1]:
        if isinstance(node, dict):
            if segment not in node:
                if not create_missing:
                    raise SchemaError(f"missing path segment: /{'/'.join(encode_pointer_segment(s) for s in segments)}")
                node[segment] = {}
            node = node[segment]
        elif isinstance(node, list):
            index = parse_list_index(segment, len(node), allow_end=False)
            node = node[index]
        else:
            raise SchemaError("cannot traverse through a non-container JSON value")
    return node, segments[-1]


def get_node(root: Any, pointer: str) -> Any:
    """Return the value at a JSON Pointer path."""

    segments = decode_pointer(pointer)
    node = root
    for segment in segments:
        if isinstance(node, dict):
            if segment not in node:
                raise SchemaError(f"missing path: {pointer or '/'}")
            node = node[segment]
        elif isinstance(node, list):
            index = parse_list_index(segment, len(node), allow_end=False)
            node = node[index]
        else:
            raise SchemaError("cannot traverse through a non-container JSON value")
    return node
