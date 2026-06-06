"""CRUD operations for generic JSON documents."""

from __future__ import annotations

from typing import Any

from generation_fabric.core.pointer import decode_pointer, get_node, parse_list_index, resolve_parent
from generation_fabric.exceptions import SchemaError


def create_node(root: Any, pointer: str, value: Any) -> Any:
    """Create a value at a JSON Pointer path."""

    segments = decode_pointer(pointer)
    if not segments:
        raise SchemaError("refusing to create at the root")

    parent, key = resolve_parent(root, segments, create_missing=True)

    if isinstance(parent, dict):
        if key in parent:
            raise SchemaError(f"path already exists: {pointer}")
        parent[key] = value
    elif isinstance(parent, list):
        if key == "-":
            parent.append(value)
        else:
            index = parse_list_index(key, len(parent), allow_end=True)
            if index < len(parent):
                raise SchemaError(f"path already exists: {pointer}")
            parent.insert(index, value)
    else:
        raise SchemaError("cannot create inside a non-container JSON value")

    return root


def update_node(root: Any, pointer: str, value: Any) -> Any:
    """Replace a value at a JSON Pointer path."""

    segments = decode_pointer(pointer)
    if not segments:
        raise SchemaError("refusing to replace the root document")

    parent, key = resolve_parent(root, segments, create_missing=False)

    if isinstance(parent, dict):
        if key not in parent:
            raise SchemaError(f"path does not exist: {pointer}")
        parent[key] = value
    elif isinstance(parent, list):
        index = parse_list_index(key, len(parent), allow_end=False)
        parent[index] = value
    else:
        raise SchemaError("cannot update inside a non-container JSON value")

    return root


def delete_node(root: Any, pointer: str) -> Any:
    """Delete a value at a JSON Pointer path."""

    segments = decode_pointer(pointer)
    if not segments:
        raise SchemaError("refusing to delete the root document")

    parent, key = resolve_parent(root, segments, create_missing=False)

    if isinstance(parent, dict):
        if key not in parent:
            raise SchemaError(f"path does not exist: {pointer}")
        del parent[key]
    elif isinstance(parent, list):
        index = parse_list_index(key, len(parent), allow_end=False)
        del parent[index]
    else:
        raise SchemaError("cannot delete inside a non-container JSON value")

    return root


def read_node(root: Any, pointer: str = "") -> Any:
    """Read a node from a JSON document."""

    return get_node(root, pointer)
