"""Command-line entry point for the generation fabric."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import load_json_file, load_json_source, parse_value, read_json_file, write_json_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.json_documents.crud import create_node, delete_node, read_node, update_node
from generation_fabric.markdown.contracts import (
    DEFAULT_MARKDOWN_CONTRACT_KIND,
    scaffold_markdown_contract,
)
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.markdown.registry import list_markdown_contract_kinds
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT, attach_combinator, new_schema
from generation_fabric.schema.inference import build_inferred_schema
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node


@dataclass
class SchemaSession:
    """Mutable session state for the interactive shell."""

    schema: dict[str, Any] | None = None
    path: Path | None = None


def ensure_session_schema(session: SchemaSession) -> dict[str, Any]:
    """Return the active schema document or fail loudly."""

    if session.schema is None:
        raise SchemaError("no schema is loaded")
    return session.schema


def autosave_session(session: SchemaSession) -> None:
    """Write the current session schema back to disk when backed by a file."""

    if session.schema is not None and session.path is not None:
        write_json_file_atomic(session.path, session.schema)


def load_session_schema(session: SchemaSession, path: str) -> None:
    """Load a schema into an interactive session."""

    session.path = Path(path)
    session.schema = read_json_file(session.path)


def create_session_schema(session: SchemaSession, output: str, title: str) -> None:
    """Create a new interactive session schema."""

    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": title,
        "type": "object",
        "properties": {},
        "required": [],
    }
    validate_schema_node(schema)
    session.schema = schema
    session.path = Path(output)
    write_json_file_atomic(session.path, schema)


def print_session_node(session: SchemaSession, pointer: str = "") -> None:
    """Print the selected schema node as formatted JSON."""

    schema = ensure_session_schema(session)
    node = read_node(schema, pointer)
    print(json.dumps(node, indent=2, ensure_ascii=False))


def session_mutate(session: SchemaSession, mutation: str, pointer: str, value: Any = None) -> None:
    """Apply one JSON document mutation to the active session schema."""

    schema = ensure_session_schema(session)
    if mutation == "create":
        schema = create_node(schema, pointer, value)
    elif mutation == "update":
        schema = update_node(schema, pointer, value)
    elif mutation == "delete":
        schema = delete_node(schema, pointer)
    else:
        raise SchemaError(f"unknown mutation: {mutation}")
    validate_schema_node(schema)
    session.schema = schema
    autosave_session(session)


def session_validate(session: SchemaSession, pointer: str = "", instance_source: str = "") -> None:
    """Validate the active session schema and an optional instance."""

    schema = ensure_session_schema(session)
    target = read_node(schema, pointer) if pointer else schema
    validate_schema_node(target)
    if instance_source:
        instance = load_json_source(instance_source)
        validate_instance_against_schema(target, instance)


def session_infer(session: SchemaSession, sample_source: str, output: str = "") -> None:
    """Infer a schema from sample JSON into the active session."""

    sample = load_json_source(sample_source)
    schema = build_inferred_schema(sample, "InferredSchema", "", DEFAULT_SCHEMA_DRAFT)
    session.schema = schema
    if output:
        session.path = Path(output)
        write_json_file_atomic(session.path, schema)
    else:
        autosave_session(session)


def session_combinator(session: SchemaSession, pointer: str, keyword: str, variants_source: str) -> None:
    """Attach a oneOf/anyOf block to the active schema."""

    schema = ensure_session_schema(session)
    variants = load_json_source(variants_source)
    if not isinstance(variants, list):
        raise SchemaError("combinator variants must be a JSON array")
    schema = attach_combinator(schema, pointer, keyword, variants)
    validate_schema_node(schema)
    session.schema = schema
    autosave_session(session)


def interactive_help() -> None:
    """Print the interactive shell usage summary."""

    print(
        "Commands: load <file>, save [file], new <output> [title], show [pointer], "
        "create <pointer> <value>, update <pointer> <value>, delete <pointer>, "
        "validate [instance], infer <sample> [output], oneof <pointer> <variants>, "
        "anyof <pointer> <variants>, help, exit"
    )


def interactive_command(args: argparse.Namespace) -> int:
    """Run the interactive schema shell."""

    session = SchemaSession()
    if args.file:
        load_session_schema(session, args.file)
        print(f"loaded {args.file}")

    print("interactive mode ready; type 'help' for commands")
    while True:
        prompt = f"schema[{session.path.name if session.path else 'memory'}]> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        line = line.strip()
        if not line:
            continue

        try:
            parts = shlex.split(line, posix=False)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            continue

        command = parts[0].lower()
        rest = parts[1:]

        try:
            if command in {"exit", "quit", "q"}:
                break
            if command == "help":
                interactive_help()
                continue
            if command == "load":
                if not rest:
                    raise SchemaError("load requires a file path")
                load_session_schema(session, rest[0])
                print(f"loaded {rest[0]}")
                continue
            if command == "save":
                target = Path(rest[0]) if rest else session.path
                if target is None:
                    raise SchemaError("save requires a file path when no schema file is loaded")
                ensure_session_schema(session)
                session.path = target
                autosave_session(session)
                print(f"saved {target}")
                continue
            if command == "new":
                if not rest:
                    raise SchemaError("new requires an output path")
                output = rest[0]
                title = rest[1] if len(rest) > 1 else "UntitledSchema"
                create_session_schema(session, output, title)
                print(f"created and loaded {output}")
                continue
            if command in {"show", "read"}:
                pointer = rest[0] if rest else ""
                print_session_node(session, pointer)
                continue
            if command in {"create", "update"}:
                if len(rest) < 2:
                    raise SchemaError(f"{command} requires a pointer and a value")
                pointer = rest[0]
                value = parse_value(" ".join(rest[1:]))
                session_mutate(session, command, pointer, value)
                print(f"{command}d at {pointer or '/'}")
                continue
            if command == "delete":
                if not rest:
                    raise SchemaError("delete requires a pointer")
                session_mutate(session, "delete", rest[0])
                print(f"deleted {rest[0]}")
                continue
            if command == "validate":
                pointer = ""
                instance_source = ""
                if rest:
                    pointer = rest[0] if rest[0].startswith("/") else ""
                    instance_source = " ".join(rest[1:] if pointer else rest)
                    if pointer and len(rest) > 1:
                        instance_source = " ".join(rest[1:])
                session_validate(session, pointer, instance_source)
                print("valid")
                continue
            if command == "infer":
                if not rest:
                    raise SchemaError("infer requires a sample JSON value or file path")
                sample_source = rest[0]
                output = rest[1] if len(rest) > 1 else ""
                session_infer(session, sample_source, output)
                print("inferred schema loaded")
                continue
            if command in {"oneof", "anyof"}:
                if len(rest) < 2:
                    raise SchemaError(f"{command} requires a pointer and a JSON array of variants")
                pointer = rest[0]
                variants_source = " ".join(rest[1:])
                session_combinator(session, pointer, "oneOf" if command == "oneof" else "anyOf", variants_source)
                print(f"{command} updated at {pointer or '/'}")
                continue

            print(f"error: unknown command '{command}'", file=sys.stderr)
        except SchemaError as exc:
            print(f"error: {exc}", file=sys.stderr)

    return 0


def validate_command(args: argparse.Namespace) -> int:
    """Validate a schema file or schema node."""

    schema = read_json_file(Path(args.file))
    target = read_node(schema, args.pointer) if args.pointer else schema
    validate_schema_node(target)

    if args.instance and args.instance_file:
        raise SchemaError("use either --instance or --instance-file, not both")
    if args.instance or args.instance_file:
        instance = load_json_file(args.instance_file) if args.instance_file else load_json_source(args.instance)
        validate_instance_against_schema(target, instance)
        print("schema and instance are valid")
    else:
        print("schema is valid")
    return 0


def infer_command(args: argparse.Namespace) -> int:
    """Infer a schema from sample JSON."""

    sample = load_json_file(args.sample_file) if args.sample_file else load_json_source(args.sample)
    schema = build_inferred_schema(sample, args.title, args.description, args.draft)

    if args.output:
        output = Path(args.output)
        if output.exists() and not args.overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {output}")
        write_json_file_atomic(output, schema)
        print(f"inferred schema written to: {output}")
    else:
        print(json.dumps(schema, indent=2, ensure_ascii=False))
    return 0


def combinator_command(args: argparse.Namespace, keyword: str) -> int:
    """Attach a oneOf or anyOf block to a schema node."""

    schema = read_json_file(Path(args.file))
    variants: list[Any] = []
    for raw_variant in args.variant:
        variants.append(load_json_source(raw_variant))
    if args.variants_file:
        variants_data = load_json_file(args.variants_file)
        if not isinstance(variants_data, list):
            raise SchemaError("--variants-file must contain a JSON array")
        variants.extend(variants_data)

    schema = attach_combinator(schema, args.pointer, keyword, variants)
    validate_schema_node(schema)
    write_json_file_atomic(Path(args.file), schema)
    print(f"{keyword} updated: {args.file} @ {args.pointer or '/'}")
    return 0


def markdown_command(args: argparse.Namespace) -> int:
    """Render Markdown from a schema contract and JSON data."""

    schema = read_json_file(Path(args.schema))
    data = load_json_file(args.data_file) if args.data_file else load_json_source(args.data)
    rendered = render_markdown_document(schema, data)

    output = Path(args.output) if args.output else None
    if output is not None:
        if output.exists() and not args.overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {output}")
        from generation_fabric.core.io import write_text_file_atomic

        write_text_file_atomic(output, rendered)
        print(f"markdown written: {output}")
    else:
        print(rendered, end="")
    return 0


def markdown_contract_command(args: argparse.Namespace) -> int:
    """Scaffold a canonical markdown contract and sample data."""

    schema, sample, schema_path, data_path, markdown_path = scaffold_markdown_contract(
        args.directory,
        kind=args.kind,
        base_name=args.base_name,
        with_markdown=args.with_markdown,
        overwrite=args.overwrite,
    )
    print(f"scaffolded markdown contract in: {args.directory}")
    if args.with_markdown:
        print(f"generated: {schema_path}, {data_path}, {markdown_path}")
    else:
        print(f"generated: {schema_path}, {data_path}")
    return 0


def create_schema_command(args: argparse.Namespace) -> int:
    """Create a schema file and return an exit code."""

    new_schema(
        Path(args.output),
        args.title,
        description=args.description,
        root_type=args.root_type,
        draft=args.draft,
        extra_json=args.extra_json,
        overwrite=args.overwrite,
    )
    print(f"created schema: {args.output}")
    return 0


def read_command(args: argparse.Namespace) -> int:
    """Read a schema file or a node inside it."""

    schema = read_json_file(Path(args.file))
    node = read_node(schema, args.pointer)
    print(json.dumps(node, indent=2, ensure_ascii=False))
    return 0


def mutate_command(args: argparse.Namespace, mutation: str) -> int:
    """Apply a single CRUD mutation to a schema document."""

    path = Path(args.file)
    schema = read_json_file(path)

    value_file = getattr(args, "value_file", "")
    value_text = getattr(args, "value", "")
    force_string = getattr(args, "as_string", False)

    if value_file:
        value = load_json_file(value_file)
    else:
        value = parse_value(value_text, force_string=force_string)

    if mutation == "create":
        schema = create_node(schema, args.pointer, value)
    elif mutation == "update":
        schema = update_node(schema, args.pointer, value)
    elif mutation == "delete":
        schema = delete_node(schema, args.pointer)
    else:
        raise SchemaError(f"unknown mutation: {mutation}")

    validate_schema_node(schema)
    write_json_file_atomic(path, schema)
    print(f"{mutation}d: {path} @ {args.pointer or '/'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        description="Create, infer, validate, and edit JSON Schema files with atomic operations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Create a brand-new schema file")
    new_parser.add_argument("--output", required=True, help="Path for the new schema file")
    new_parser.add_argument("--title", default="UntitledSchema", help="Schema title")
    new_parser.add_argument("--description", default="", help="Schema description")
    new_parser.add_argument(
        "--root-type",
        default="object",
        help='Root schema type, e.g. "object", "array", or "string,null"',
    )
    new_parser.add_argument(
        "--draft",
        default=DEFAULT_SCHEMA_DRAFT,
        help="JSON Schema draft URI to store in $schema",
    )
    new_parser.add_argument(
        "--extra-json",
        default="",
        help="Inline JSON object merged into the new schema after the default fields",
    )
    new_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing file",
    )
    new_parser.set_defaults(func=create_schema_command)

    read_parser = subparsers.add_parser("read", help="Read the full schema or a node inside it")
    read_parser.add_argument("--file", required=True, help="Existing schema file")
    read_parser.add_argument(
        "--pointer",
        default="",
        help="JSON Pointer to read, e.g. /properties/name",
    )
    read_parser.set_defaults(func=read_command)

    create_parser = subparsers.add_parser("create", help="Create a new node in an existing schema")
    create_parser.add_argument("--file", required=True, help="Existing schema file")
    create_parser.add_argument("--pointer", required=True, help="JSON Pointer to create")
    create_parser.add_argument("--value", default="", help="Inline JSON value or plain text")
    create_parser.add_argument("--value-file", default="", help="Load the value from a JSON file")
    create_parser.add_argument(
        "--as-string",
        action="store_true",
        help="Store --value as a literal string instead of parsing JSON",
    )
    create_parser.set_defaults(func=lambda args: mutate_command(args, "create"))

    update_parser = subparsers.add_parser("update", help="Update an existing node in a schema")
    update_parser.add_argument("--file", required=True, help="Existing schema file")
    update_parser.add_argument("--pointer", required=True, help="JSON Pointer to update")
    update_parser.add_argument("--value", default="", help="Inline JSON value or plain text")
    update_parser.add_argument("--value-file", default="", help="Load the value from a JSON file")
    update_parser.add_argument(
        "--as-string",
        action="store_true",
        help="Store --value as a literal string instead of parsing JSON",
    )
    update_parser.set_defaults(func=lambda args: mutate_command(args, "update"))

    delete_parser = subparsers.add_parser("delete", help="Delete a node from a schema")
    delete_parser.add_argument("--file", required=True, help="Existing schema file")
    delete_parser.add_argument("--pointer", required=True, help="JSON Pointer to delete")
    delete_parser.set_defaults(func=lambda args: mutate_command(args, "delete"))

    validate_parser = subparsers.add_parser("validate", help="Validate a schema or a subschema")
    validate_parser.add_argument("--file", required=True, help="Existing schema file")
    validate_parser.add_argument(
        "--pointer",
        default="",
        help="Optional JSON Pointer to validate a subschema",
    )
    validate_parser.add_argument("--instance", default="", help="Inline JSON instance to validate")
    validate_parser.add_argument(
        "--instance-file",
        default="",
        help="Path to a JSON file to validate against the schema",
    )
    validate_parser.set_defaults(func=validate_command)

    infer_parser = subparsers.add_parser("infer", help="Infer a schema from sample JSON")
    infer_parser.add_argument("--sample", default="", help="Inline JSON sample")
    infer_parser.add_argument("--sample-file", default="", help="Path to a JSON sample file")
    infer_parser.add_argument("--output", default="", help="Write the inferred schema to a file")
    infer_parser.add_argument("--title", default="InferredSchema", help="Schema title")
    infer_parser.add_argument("--description", default="", help="Schema description")
    infer_parser.add_argument(
        "--draft",
        default=DEFAULT_SCHEMA_DRAFT,
        help="JSON Schema draft URI to store in $schema",
    )
    infer_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output file",
    )
    infer_parser.set_defaults(func=infer_command)

    oneof_parser = subparsers.add_parser("oneof", help="Attach a oneOf array to a schema node")
    oneof_parser.add_argument("--file", required=True, help="Existing schema file")
    oneof_parser.add_argument("--pointer", default="", help="JSON Pointer to attach oneOf at")
    oneof_parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Inline JSON schema variant; repeat to add multiple variants",
    )
    oneof_parser.add_argument(
        "--variants-file",
        default="",
        help="Path to a JSON array of schema variants",
    )
    oneof_parser.set_defaults(func=lambda args: combinator_command(args, "oneOf"))

    anyof_parser = subparsers.add_parser("anyof", help="Attach an anyOf array to a schema node")
    anyof_parser.add_argument("--file", required=True, help="Existing schema file")
    anyof_parser.add_argument("--pointer", default="", help="JSON Pointer to attach anyOf at")
    anyof_parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Inline JSON schema variant; repeat to add multiple variants",
    )
    anyof_parser.add_argument(
        "--variants-file",
        default="",
        help="Path to a JSON array of schema variants",
    )
    anyof_parser.set_defaults(func=lambda args: combinator_command(args, "anyOf"))

    markdown_parser = subparsers.add_parser(
        "markdown",
        help="Render Markdown from a JSON Schema contract and JSON data",
    )
    markdown_parser.add_argument("--schema", required=True, help="Path to the JSON Schema contract")
    markdown_parser.add_argument("--data", default="", help="Inline JSON data to render")
    markdown_parser.add_argument("--data-file", default="", help="Path to a JSON file with render data")
    markdown_parser.add_argument("--output", default="", help="Write rendered Markdown to a file")
    markdown_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing Markdown file",
    )
    markdown_parser.set_defaults(func=markdown_command)

    markdown_contract_parser = subparsers.add_parser(
        "markdown-contract",
        help="Scaffold a markdown contract schema plus sample data",
    )
    markdown_contract_parser.add_argument(
        "--kind",
        default=DEFAULT_MARKDOWN_CONTRACT_KIND,
        choices=list_markdown_contract_kinds(),
        help="Contract kind to scaffold",
    )
    markdown_contract_parser.add_argument(
        "--directory",
        default="examples",
        help="Directory where the scaffolded files should be written",
    )
    markdown_contract_parser.add_argument(
        "--base-name",
        default="",
        help="Override the default filename prefix",
    )
    markdown_contract_parser.add_argument(
        "--with-markdown",
        action="store_true",
        help="Also render a Markdown example alongside the schema and JSON sample",
    )
    markdown_contract_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing scaffold files",
    )
    markdown_contract_parser.set_defaults(func=markdown_contract_command)

    interactive_parser = subparsers.add_parser("interactive", help="Start a tiny interactive shell")
    interactive_parser.add_argument("--file", default="", help="Optional schema file to load at startup")
    interactive_parser.set_defaults(func=interactive_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
