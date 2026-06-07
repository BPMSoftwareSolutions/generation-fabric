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
    participants: tuple[str, ...]
    flow_steps: tuple[str, ...]
    mermaid: str
    notes: tuple[str, ...]

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


def _build_mermaid_sequence(function_name: str, participants: tuple[str, ...], flow_steps: tuple[str, ...]) -> str:
    """Build a simple Mermaid sequence diagram for an observed function."""

    lines = ["sequenceDiagram"]
    for participant in participants:
        if participant == "Caller":
            lines.append(f"{_indent(1)}participant Caller")
        else:
            alias = participant.replace(".", "_").replace("-", "_")
            lines.append(f"{_indent(1)}participant {alias} as {participant}")

    function_alias = function_name.replace(".", "_").replace("-", "_")
    lines.append(f"{_indent(1)}Caller->>{function_alias}: invoke")
    for step in flow_steps:
        if step.startswith("call "):
            target = step.removeprefix("call ").strip()
            target_alias = target.replace(".", "_").replace("-", "_")
            lines.append(f"{_indent(1)}{function_alias}->>{target_alias}: {target}")
        elif step.startswith("branch: "):
            branch = step.removeprefix("branch: ").strip()
            lines.append(f"{_indent(1)}note over {function_alias}: {branch} branch observed")
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
    participants = _unique_preserve_order(("Caller", qualified_name, *collector.calls))
    flow_steps: list[str] = [f"invoke {qualified_name}"]
    if class_name:
        flow_steps.append(f"owner {class_name}")
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
        mermaid=_build_mermaid_sequence(qualified_name, participants, tuple(collector.flow_steps)),
        notes=tuple(notes),
    )


def collect_python_function_observations(source_path: Path, include_private: bool = False) -> tuple[PythonFunctionObservation, ...]:
    """Collect ordered function and method observations from a Python source file."""

    if not source_path.exists():
        raise SchemaError(f"source file does not exist: {source_path}")
    if not source_path.is_file():
        raise SchemaError(f"source path is not a file: {source_path}")

    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"cannot read source file {source_path}: {exc}") from exc

    tree = ast.parse(source_text, filename=str(source_path))
    observations: list[PythonFunctionObservation] = []

    def should_include(name: str) -> bool:
        return include_private or not name.startswith("_")

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if should_include(node.name):
                observations.append(
                    _build_function_observation(
                        node,
                        node.name,
                        "function",
                    )
                )
        elif isinstance(node, ast.ClassDef):
            if not should_include(node.name):
                continue
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and should_include(member.name):
                    qualified_name = f"{node.name}.{member.name}"
                    observations.append(
                        _build_function_observation(
                            member,
                            qualified_name,
                            "method",
                            class_name=node.name,
                        )
                    )

    if not observations:
        raise SchemaError(f"no public functions or methods were found in {source_path}")

    return tuple(observations)


def build_code_observation_document_schema(
    source_path: Path,
    observations: tuple[PythonFunctionObservation, ...],
    *,
    shape: str = "sequence-diagram",
    title: str = "",
) -> dict[str, Any]:
    """Build the JSON Schema contract for code observation output."""

    resolved_title = title.strip() or f"Code Observation: {source_path.stem}"
    participants = _unique_preserve_order(
        participant for observation in observations for participant in observation.participants
    )
    sample_paths = [observation.to_dict() for observation in observations]
    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": resolved_title,
        "type": "object",
        "properties": {
            "source_file": {
                "type": "string",
                "x-sample": str(source_path),
                "x-markdown": {"kind": "paragraph", "label": True},
            },
            "shape": {
                "type": "string",
                "x-sample": shape,
                "x-markdown": {"kind": "paragraph", "label": True},
            },
            "summary": {
                "type": "string",
                "x-sample": (
                    f"Observed {len(observations)} execution path(s) and projected them into Mermaid sequence diagrams."
                ),
                "x-markdown": {"kind": "paragraph"},
            },
            "participants": {
                "type": "array",
                "items": {"type": "string"},
                "x-sample": list(participants),
                "x-markdown": {"kind": "list"},
            },
            "execution_paths": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "x-markdown": {"kind": "heading", "level": 3},
                        },
                        "kind": {
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
                        "signature",
                        "docstring",
                        "participants",
                        "flow_steps",
                        "mermaid",
                        "notes",
                    ],
                    "x-markdown": {"kind": "section"},
                },
                "x-sample": sample_paths,
                "x-markdown": {
                    "kind": "section",
                    "heading": "Execution Paths",
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
        "required": ["source_file", "shape", "summary", "participants", "execution_paths", "notes"],
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
    observations = collect_python_function_observations(source_path, include_private=include_private)
    schema = build_code_observation_document_schema(source_path, observations, shape=shape, title=title)
    data = {
        "source_file": str(source_path),
        "shape": shape,
        "summary": f"Observed {len(observations)} execution path(s) from {source_path.name}.",
        "participants": list(
            _unique_preserve_order(participant for observation in observations for participant in observation.participants)
        ),
        "execution_paths": [observation.to_dict() for observation in observations],
        "notes": [
            "The worker bee turns code shape into a contract before rendering Markdown.",
            "Sequence diagrams make the participants and call order visible at a glance.",
        ],
    }
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


__all__ = [
    "CodeObservationDocumentPaths",
    "PythonFunctionObservation",
    "build_code_observation_document",
    "build_code_observation_document_schema",
    "collect_python_function_observations",
    "write_code_observation_document",
]
