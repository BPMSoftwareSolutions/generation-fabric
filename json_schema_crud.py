#!/usr/bin/env python3
"""Compatibility wrapper for the generation fabric CLI."""

from generation_fabric.cli import DEFAULT_SCHEMA_DRAFT, SchemaError, main

__all__ = ["DEFAULT_SCHEMA_DRAFT", "SchemaError", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
