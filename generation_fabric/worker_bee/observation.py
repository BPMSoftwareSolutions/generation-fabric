"""Code observation helpers for worker-bee sequence-diagram generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ast
import json
from pathlib import Path
from typing import Any, Iterable

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

from .taxonomy import _call_label_from_identifier, scan_python_source_taxonomy


@dataclass(frozen=True)
class CodeObservationDocumentPaths:
    """Describe the files produced by the code observation worker bee."""

    schema_path: Path
    data_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class PythonFunctionObservation:
    """Describe one observed Python execution path."""

    name: str
    kind: str
    signature: str
    docstring: str
    anchor: str = ""
    line_start: int = 0
    line_end: int = 0
    role: str = ""
    responsibility: str = ""
    participants: tuple[str, ...] = ()
    flow_steps: tuple[str, ...] = ()
    mutations: tuple[str, ...] = ()
    returns: tuple[str, ...] = ()
    mermaid: str = ""
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the observation into JSON-friendly data."""

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


def _normalize_brief(text: str) -> str:
    """Normalize whitespace for code-observation strings."""

    return " ".join(text.split()).strip()


def _indent(level: int) -> str:
    """Return a standard indentation prefix for Mermaid blocks."""

    return "    " * level


def _format_signature(node: ast.AST, qualified_name: str) -> str:
    """Render a Python signature for a function or method."""

    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return f"def {qualified_name}()"

    params: list[str] = []
    args = node.args

    positional = list(args.posonlyargs) + list(args.args)
    defaults_offset = len(positional) - len(args.defaults)
    for index, arg in enumerate(positional):
        rendered = arg.arg
        default_index = index - defaults_offset
        if default_index >= 0:
            default_value = args.defaults[default_index]
            rendered = f"{rendered}={ast.unparse(default_value) if hasattr(ast, 'unparse') else '...'}"
        params.append(rendered)

    if args.vararg is not None:
        params.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        params.append("*")

    for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is None:
            params.append(kwarg.arg)
        else:
            default_text = ast.unparse(default) if hasattr(ast, "unparse") else "..."
            params.append(f"{kwarg.arg}={default_text}")

    if args.kwarg is not None:
        params.append(f"**{args.kwarg.arg}")

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return_annotation = ""
    if getattr(node, "returns", None) is not None:
        return_annotation = f" -> {ast.unparse(node.returns) if hasattr(ast, 'unparse') else '...'}"
    return f"{prefix} {qualified_name}({', '.join(params)}){return_annotation}"


def _resolve_call_name(node: ast.AST) -> str:
    """Resolve a readable name for an AST call target."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _resolve_call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _resolve_call_name(node.func)
    return ""


def _normalize_participant_label(label: str) -> str:
    """Normalize a taxonomy participant label for Mermaid output."""

    return _normalize_brief(label)


def _mermaid_alias(label: str) -> str:
    """Build a Mermaid-safe alias from a display label."""

    alias = _normalize_participant_label(label).replace(".", "_").replace("-", "_")
    alias = "".join(character if character.isalnum() or character == "_" else "_" for character in alias)
    while "__" in alias:
        alias = alias.replace("__", "_")
    return alias.strip("_") or "participant"


class _FunctionFlowCollector(ast.NodeVisitor):
    """Collect ordered flow signals from a function body."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.flow_steps: list[str] = []
        self.branch_markers: list[str] = []

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802
        name = _resolve_call_name(node.func)
        if name:
            self.calls.append(name)
            self.flow_steps.append(f"call {name}")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> Any:  # noqa: N802
        self.branch_markers.append("if")
        self.flow_steps.append("branch: if")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:  # noqa: N802
        self.branch_markers.append("for")
        self.flow_steps.append("branch: for")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:  # noqa: N802
        self.branch_markers.append("while")
        self.flow_steps.append("branch: while")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> Any:  # noqa: N802
        self.branch_markers.append("try")
        self.flow_steps.append("branch: try")
        self.generic_visit(node)


def _unique_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    """Return values without duplicates while preserving order."""

    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return tuple(seen.keys())


def _build_mermaid_sequence(
    function_name: str,
    participants: tuple[str, ...],
    flow_steps: tuple[str, ...],
    *,
    function_label: str = "",
) -> str:
    """Build a simple Mermaid sequence diagram for an observed function."""

    lines = ["sequenceDiagram"]
    participant_aliases: dict[str, str] = {}
    for participant in participants:
        if participant == "Caller":
            lines.append(f"{_indent(1)}participant Caller")
            participant_aliases[participant] = "Caller"
        else:
            alias = _mermaid_alias(participant)
            participant_aliases[participant] = alias
            lines.append(f"{_indent(1)}participant {alias} as {participant}")

    resolved_function_label = _normalize_participant_label(function_label or function_name)
    function_alias = participant_aliases.get(resolved_function_label, _mermaid_alias(resolved_function_label))
    lines.append(f"{_indent(1)}Caller->>{function_alias}: invoke")
    pending_return_value = ""
    for step in flow_steps:
        if step.startswith("trigger "):
            target = step.removeprefix("trigger ").strip()
            target_label = _call_label_from_identifier(target)
            target_alias = participant_aliases.get(target_label, _mermaid_alias(target_label))
            if target_alias == function_alias:
                continue
            lines.append(f"{_indent(1)}{function_alias}->>{target_alias}: trigger")
            lines.append(f"{_indent(1)}{target_alias}-->>{function_alias}: return")
        elif step.startswith("data "):
            payload = step.removeprefix("data ").strip()
            if ": " in payload:
                target, message = payload.split(": ", 1)
            else:
                target, message = payload, ""
            target_label = _call_label_from_identifier(target)
            target_alias = participant_aliases.get(target_label, _mermaid_alias(target_label))
            if target_alias == function_alias:
                continue
            label = f"data: {message}" if message else "data"
            lines.append(f"{_indent(1)}{function_alias}->>{target_alias}: {label}")
            lines.append(f"{_indent(1)}{target_alias}-->>{function_alias}: return")
        elif step.startswith("mutation "):
            mutation = step.removeprefix("mutation ").strip()
            lines.append(f"{_indent(1)}note over {function_alias}: mutation observed - {mutation}")
        elif step.startswith("branch: "):
            branch = step.removeprefix("branch: ").strip()
            lines.append(f"{_indent(1)}note over {function_alias}: {branch} branch observed")
        elif step.startswith("return "):
            pending_return_value = step.removeprefix("return ").strip()
    if pending_return_value:
        lines.append(f"{_indent(1)}{function_alias}-->>Caller: return {pending_return_value}")
    else:
        lines.append(f"{_indent(1)}{function_alias}-->>Caller: return")
    return "\n".join(lines)


def _build_function_observation(
    node: ast.AST,
    qualified_name: str,
    kind: str,
    class_name: str = "",
) -> PythonFunctionObservation:
    """Build one observation from a function or method node."""

    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    collector = _FunctionFlowCollector()
    for statement in node.body:
        collector.visit(statement)

    docstring = ast.get_docstring(node) or ""
    signature = _format_signature(node, qualified_name)
    function_label = _call_label_from_identifier(qualified_name)
    participants = _unique_preserve_order(("Caller", function_label, *(_call_label_from_identifier(call) for call in collector.calls)))
    flow_steps: list[str] = [f"invoke {qualified_name}"]
    if class_name:
        flow_steps.append(f"owner {_call_label_from_identifier(class_name)}")
    flow_steps.extend(collector.flow_steps)
    if not collector.calls:
        flow_steps.append("no helper calls observed")
    flow_steps.append("return")

    notes = [f"Observed as a {kind} in the code flow."]
    if collector.branch_markers:
        notes.append(f"Branch markers detected: {', '.join(_unique_preserve_order(collector.branch_markers))}.")
    if docstring:
        notes.append("Docstring captured as part of the contract.")
    else:
        notes.append("No docstring was present; the flow was inferred from AST structure.")

    return PythonFunctionObservation(
        name=qualified_name,
        kind=kind,
        signature=signature,
        docstring=docstring,
        participants=participants,
        flow_steps=tuple(flow_steps),
        mermaid=_build_mermaid_sequence(
            qualified_name,
            participants,
            tuple(collector.flow_steps),
            function_label=function_label,
        ),
        notes=tuple(notes),
    )


def _observation_from_taxonomy_execution_path(path: dict[str, Any]) -> PythonFunctionObservation:
    """Convert a taxonomy execution path into an observation record."""

    participants = tuple(str(participant) for participant in path.get("participants", []))
    flow_steps = tuple(str(step) for step in path.get("flow_steps", []))
    notes = tuple(str(note) for note in path.get("notes", []))
    return PythonFunctionObservation(
        name=str(path.get("name", "")),
        kind=str(path.get("kind", "function")),
        signature=str(path.get("signature", "")),
        docstring=str(path.get("docstring", "")),
        anchor=str(path.get("anchor", "")),
        line_start=int(path.get("line_start", 0) or 0),
        line_end=int(path.get("line_end", 0) or 0),
        role=str(path.get("role", "")),
        responsibility=str(path.get("responsibility", "")),
        participants=participants,
        flow_steps=flow_steps,
        mutations=tuple(str(mutation) for mutation in path.get("mutations", [])),
        returns=tuple(str(value) for value in path.get("returns", [])),
        mermaid=_build_mermaid_sequence(
            str(path.get("name", "")),
            participants,
            flow_steps,
            function_label=str(path.get("role", "")),
        ),
        notes=notes,
    )


def _observations_from_taxonomy_data(taxonomy_data: dict[str, Any]) -> tuple[PythonFunctionObservation, ...]:
    """Convert a taxonomy document into observation records."""

    execution_paths = taxonomy_data.get("execution_paths", [])
    if not isinstance(execution_paths, list):
        raise SchemaError("taxonomy execution_paths must be an array")

    observations = tuple(
        _observation_from_taxonomy_execution_path(path)
        for path in execution_paths
        if isinstance(path, dict)
    )
    if not observations:
        raise SchemaError("no execution paths were found in the taxonomy document")
    return observations


def _symbol_inventory_rows(taxonomy_data: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Build a concise code inventory table from taxonomy symbol records."""

    symbols = taxonomy_data.get("symbols", [])
    if not isinstance(symbols, list):
        raise SchemaError("taxonomy symbols must be an array")

    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        if not isinstance(symbol, dict):
            continue
        rows.append(
            {
                "label": str(symbol.get("label", symbol.get("name", ""))),
                "kind": str(symbol.get("kind", "")),
                "role": str(symbol.get("role", "")),
                "responsibility": str(symbol.get("responsibility", "")),
                "anchor": str(symbol.get("anchor", "")),
                "line_start": int(symbol.get("line_start", 0) or 0),
                "line_end": int(symbol.get("line_end", 0) or 0),
            }
        )
    return tuple(rows)


def _build_observation_overview(
    taxonomy_data: dict[str, Any],
    source_path: Path,
    observations: tuple[PythonFunctionObservation, ...],
    *,
    shape: str,
) -> dict[str, Any]:
    """Build the overview block for a code-observation document."""

    return {
        "source_file": str(taxonomy_data.get("source_file", str(source_path))),
        "module_path": str(taxonomy_data.get("module_path", "")),
        "source_hash": str(taxonomy_data.get("source_hash", "")),
        "shape": shape,
        "summary": f"Observed {len(observations)} execution(s) in {source_path.name} and projected triggers, data batons, state changes, and returns into Mermaid sequence diagrams.",
    }


def _build_observation_document_payload(
    taxonomy_data: dict[str, Any],
    source_path: Path,
    observations: tuple[PythonFunctionObservation, ...],
    *,
    shape: str,
) -> dict[str, Any]:
    """Build the JSON payload for a code-observation document."""

    return {
        "overview": _build_observation_overview(taxonomy_data, source_path, observations, shape=shape),
        "inventory": {"rows": list(_symbol_inventory_rows(taxonomy_data))},
        "executions": [observation.to_dict() for observation in observations],
        "notes": [
            "The worker bee extracts a shape from code before rendering any Markdown.",
            "The code inventory anchors declarations, while executions show triggers, data batons, mutations, and returns.",
        ],
    }


def collect_python_function_observations(source_path: Path, include_private: bool = False) -> tuple[PythonFunctionObservation, ...]:
    """Collect ordered function and method observations from a Python source file."""

    taxonomy = scan_python_source_taxonomy(source_path, include_private=include_private)
    observations = _observations_from_taxonomy_data(taxonomy.to_dict())
    return observations


def build_code_observation_document_schema(
    source_path: Path,
    observations: tuple[PythonFunctionObservation, ...],
    taxonomy_data: dict[str, Any] | None = None,
    *,
    shape: str = "sequence-diagram",
    title: str = "",
) -> dict[str, Any]:
    """Build the JSON Schema contract for code observation output."""

    resolved_title = title.strip() or f"Code Observation: {source_path.stem}"
    taxonomy_data = taxonomy_data or {}
    inventory_rows = _symbol_inventory_rows(taxonomy_data)
    overview_sample = _build_observation_overview(taxonomy_data, source_path, observations, shape=shape)
    sample_paths = [observation.to_dict() for observation in observations]
    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": resolved_title,
        "description": "A contract-backed code observation that inventories the source file before rendering the observed executions, data batons, state changes, and returns as Mermaid sequence diagrams.",
        "type": "object",
        "properties": {
            "overview": {
                "type": "object",
                "properties": {
                    "source_file": {
                        "type": "string",
                        "x-sample": overview_sample["source_file"],
                        "x-markdown": {"kind": "paragraph", "label": True},
                    },
                    "module_path": {
                        "type": "string",
                        "x-sample": overview_sample["module_path"],
                        "x-markdown": {"kind": "paragraph", "label": True},
                    },
                    "source_hash": {
                        "type": "string",
                        "x-sample": overview_sample["source_hash"],
                        "x-markdown": {"kind": "paragraph", "label": True},
                    },
                    "shape": {
                        "type": "string",
                        "x-sample": overview_sample["shape"],
                        "x-markdown": {"kind": "paragraph", "label": True},
                    },
                    "summary": {
                        "type": "string",
                        "x-sample": overview_sample["summary"],
                        "x-markdown": {"kind": "paragraph"},
                    },
                },
                "required": ["source_file", "module_path", "source_hash", "shape", "summary"],
                "x-sample": overview_sample,
                "x-markdown": {"kind": "section", "heading": "Overview"},
            },
            "inventory": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph"},
                                },
                                "kind": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph"},
                                },
                                "role": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph"},
                                },
                                "responsibility": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph"},
                                },
                                "anchor": {
                                    "type": "string",
                                    "x-markdown": {"kind": "paragraph"},
                                },
                                "line_start": {
                                    "type": "integer",
                                },
                                "line_end": {
                                    "type": "integer",
                                },
                            },
                            "required": [
                                "label",
                                "kind",
                                "role",
                                "responsibility",
                                "anchor",
                                "line_start",
                                "line_end",
                            ],
                            "x-markdown": {"kind": "table"},
                        },
                        "x-sample": list(inventory_rows),
                        "x-markdown": {"kind": "table"},
                    }
                },
                "required": ["rows"],
                "x-sample": {"rows": list(inventory_rows)},
                "x-markdown": {"kind": "section", "heading": "Code Inventory"},
            },
            "executions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph", "label": True},
                        },
                        "kind": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph", "label": True},
                        },
                        "role": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph", "label": True},
                        },
                        "responsibility": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph", "label": True},
                        },
                        "anchor": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph", "label": True},
                        },
                        "signature": {
                            "type": "string",
                            "x-markdown": {"kind": "code", "language": "python"},
                        },
                        "docstring": {
                            "type": "string",
                            "x-markdown": {"kind": "raw"},
                        },
                        "participants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-markdown": {"kind": "list"},
                        },
                        "flow_steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-markdown": {"kind": "ordered-list"},
                        },
                        "mutations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-markdown": {"kind": "section", "heading": "State Changes", "item_heading": "Mutation"},
                        },
                        "returns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-markdown": {"kind": "section", "heading": "Returns", "item_heading": "Return"},
                        },
                        "mermaid": {
                            "type": "string",
                            "x-markdown": {"kind": "code", "language": "mermaid"},
                        },
                        "notes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "x-markdown": {"kind": "list"},
                        },
                    },
                    "required": [
                        "name",
                        "kind",
                        "role",
                        "responsibility",
                        "anchor",
                        "signature",
                        "docstring",
                        "participants",
                        "flow_steps",
                        "mutations",
                        "returns",
                        "mermaid",
                        "notes",
                    ],
                    "x-markdown": {"kind": "section"},
                },
                "x-sample": sample_paths,
                "x-markdown": {
                    "kind": "section",
                    "heading": "Executions",
                    "item_heading": "Execution",
                },
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
                "x-sample": [
                    "The worker bee extracts a shape from code before rendering any Markdown.",
                    "Mermaid sequence diagrams are generated from observed execution paths.",
                ],
                "x-markdown": {"kind": "list"},
            },
        },
        "required": ["overview", "inventory", "executions", "notes"],
    }
    validate_schema_node(schema)
    return schema


def build_code_observation_document(
    source_file: str,
    *,
    shape: str = "sequence-diagram",
    title: str = "",
    include_private: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build the schema, JSON data, and rendered Markdown for a source file."""

    source_path = Path(source_file)
    taxonomy = scan_python_source_taxonomy(source_path, include_private=include_private)
    taxonomy_data = taxonomy.to_dict()
    observations = _observations_from_taxonomy_data(taxonomy_data)
    schema = build_code_observation_document_schema(
        source_path,
        observations,
        taxonomy_data,
        shape=shape,
        title=title,
    )
    data = _build_observation_document_payload(taxonomy_data, source_path, observations, shape=shape)
    validate_instance_against_schema(schema, data)
    rendered = render_markdown_document(schema, data)
    return schema, data, rendered


def build_code_observation_document_from_taxonomy(
    taxonomy_data: dict[str, Any],
    *,
    shape: str = "sequence-diagram",
    title: str = "",
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build the observation contract from a saved taxonomy document."""

    source_file = str(taxonomy_data.get("source_file", "")).strip()
    if not source_file:
        raise SchemaError("taxonomy document is missing source_file")
    source_path = Path(source_file)
    observations = _observations_from_taxonomy_data(taxonomy_data)
    schema = build_code_observation_document_schema(
        source_path,
        observations,
        taxonomy_data,
        shape=shape,
        title=title,
    )
    data = _build_observation_document_payload(taxonomy_data, source_path, observations, shape=shape)
    validate_instance_against_schema(schema, data)
    rendered = render_markdown_document(schema, data)
    return schema, data, rendered


def write_code_observation_document(
    source_file: str,
    *,
    output: str = "",
    shape: str = "sequence-diagram",
    title: str = "",
    include_private: bool = False,
    overwrite: bool = False,
    ) -> CodeObservationDocumentPaths:
    """Write a code-observation document to disk."""

    schema, data, markdown = build_code_observation_document(
        source_file,
        shape=shape,
        title=title,
        include_private=include_private,
    )

    source_path = Path(source_file)
    if output:
        markdown_path = Path(output)
        if not markdown_path.suffix:
            markdown_path = markdown_path.with_suffix(".md")
    else:
        markdown_path = Path("generated") / f"{source_path.stem}-observation.md"

    if markdown_path.exists() and not overwrite:
        raise SchemaError(f"refusing to overwrite existing file: {markdown_path}")

    schema_path = markdown_path.with_name(f"{markdown_path.stem}.schema.json")
    data_path = markdown_path.with_name(f"{markdown_path.stem}.json")

    for target in (schema_path, data_path):
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_json_file_atomic(schema_path, schema)
    write_json_file_atomic(data_path, data)
    write_text_file_atomic(markdown_path, markdown)
    return CodeObservationDocumentPaths(schema_path=schema_path, data_path=data_path, markdown_path=markdown_path)


def write_code_observation_document_from_taxonomy(
    taxonomy_data: dict[str, Any],
    *,
    output: str = "",
    shape: str = "sequence-diagram",
    title: str = "",
    overwrite: bool = False,
) -> CodeObservationDocumentPaths:
    """Write a code-observation document from a saved taxonomy document."""

    schema, data, markdown = build_code_observation_document_from_taxonomy(
        taxonomy_data,
        shape=shape,
        title=title,
    )

    source_file = str(taxonomy_data.get("source_file", "")).strip()
    if not source_file:
        raise SchemaError("taxonomy document is missing source_file")
    source_path = Path(source_file)
    if output:
        markdown_path = Path(output)
        if not markdown_path.suffix:
            markdown_path = markdown_path.with_suffix(".md")
    else:
        markdown_path = Path("generated") / f"{source_path.stem}-observation.md"

    if markdown_path.exists() and not overwrite:
        raise SchemaError(f"refusing to overwrite existing file: {markdown_path}")

    schema_path = markdown_path.with_name(f"{markdown_path.stem}.schema.json")
    data_path = markdown_path.with_name(f"{markdown_path.stem}.json")

    for target in (schema_path, data_path):
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_json_file_atomic(schema_path, schema)
    write_json_file_atomic(data_path, data)
    write_text_file_atomic(markdown_path, markdown)
    return CodeObservationDocumentPaths(schema_path=schema_path, data_path=data_path, markdown_path=markdown_path)


__all__ = [
    "CodeObservationDocumentPaths",
    "PythonFunctionObservation",
    "build_code_observation_document_from_taxonomy",
    "build_code_observation_document",
    "build_code_observation_document_schema",
    "collect_python_function_observations",
    "write_code_observation_document_from_taxonomy",
    "write_code_observation_document",
]
