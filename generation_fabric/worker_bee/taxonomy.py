"""Deterministic taxonomy extraction for worker-bee code observation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

from generation_fabric.core.io import write_json_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node


@dataclass(frozen=True)
class CodeTaxonomyCondition:
    """Describe one captured branch or exception condition."""

    kind: str
    source_text: str
    meaning: str
    line_start: int
    line_end: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the condition into JSON-friendly data."""

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


@dataclass(frozen=True)
class CodeTaxonomySymbol:
    """Describe one observed declaration in a Python source file."""

    name: str
    label: str
    kind: str
    anchor: str
    line_start: int
    line_end: int
    signature: str
    docstring: str
    parent_class: str
    role: str
    responsibility: str
    decorators: tuple[str, ...]
    calls: tuple[str, ...]
    conditions: tuple[CodeTaxonomyCondition, ...]
    branch_markers: tuple[str, ...]
    return_points: tuple[int, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the symbol into JSON-friendly data."""

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


@dataclass(frozen=True)
class CodeTaxonomyExecutionPath:
    """Describe one observed execution path in a Python source file."""

    name: str
    label: str
    kind: str
    anchor: str
    line_start: int
    line_end: int
    signature: str
    docstring: str
    parent_class: str
    participants: tuple[str, ...]
    flow_steps: tuple[str, ...]
    calls: tuple[str, ...]
    conditions: tuple[CodeTaxonomyCondition, ...]
    branch_markers: tuple[str, ...]
    return_points: tuple[int, ...]
    role: str
    responsibility: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution path into JSON-friendly data."""

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


@dataclass(frozen=True)
class CodeTaxonomyDocument:
    """Describe the deterministic taxonomy for a Python source file."""

    source_file: str
    module_path: str
    source_hash: str
    shape: str
    summary: str
    symbols: tuple[CodeTaxonomySymbol, ...]
    execution_paths: tuple[CodeTaxonomyExecutionPath, ...]
    notes: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the taxonomy into JSON-friendly data."""

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


@dataclass(frozen=True)
class CodeTaxonomyDocumentPaths:
    """Describe the files produced by the taxonomy worker bee."""

    schema_path: Path
    data_path: Path


def _repo_root() -> Path:
    """Return the repository root."""

    return Path(__file__).resolve().parents[2]


def _normalize_brief(text: str) -> str:
    """Normalize whitespace for taxonomy strings."""

    return " ".join(text.split()).strip()


BUILTIN_CALL_NAMES = {
    "all",
    "any",
    "bool",
    "bytes",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
}

ROLE_PREFIXES = {
    "build": "Builder",
    "collect": "Collector",
    "create": "Creator",
    "delete": "Deleter",
    "derive": "Deriver",
    "detect": "Detector",
    "explain": "Explainer",
    "format": "Formatter",
    "generate": "Generator",
    "infer": "Inference",
    "load": "Loader",
    "normalize": "Normalizer",
    "parse": "Parser",
    "read": "Reader",
    "render": "Renderer",
    "scan": "Scanner",
    "serialize": "Serializer",
    "slugify": "Slugifier",
    "summarize": "Summarizer",
    "update": "Updater",
    "validate": "Validator",
    "write": "Writer",
}

MODULE_ROLE_LABELS = {
    "ast": "AST",
    "collections": "Collections",
    "contextlib": "Context",
    "dataclasses": "Dataclass",
    "hashlib": "Hashing",
    "io": "IO",
    "json": "JSON",
    "pathlib": "Path",
    "re": "Regex",
    "tempfile": "Temporary File",
    "typing": "Typing",
}


def _display_source_path(source_path: Path) -> str:
    """Return a stable repository-relative display path when possible."""

    repo_root = _repo_root()
    try:
        return source_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return source_path.as_posix()


def _module_path(source_path: Path) -> str:
    """Infer a dotted module path from a Python source path."""

    repo_root = _repo_root()
    resolved = source_path.resolve()
    try:
        relative = resolved.relative_to(repo_root)
        if relative.suffix == ".py":
            relative = relative.with_suffix("")
        return ".".join(relative.parts)
    except ValueError:
        return source_path.with_suffix("").name.replace("/", ".").replace("\\", ".")


def _source_hash(source_text: str) -> str:
    """Compute a deterministic hash for a source file."""

    return f"sha256:{sha256(source_text.encode('utf-8')).hexdigest()}"


def _first_sentence(text: str) -> str:
    """Return the first sentence or line from a docstring."""

    normalized = _normalize_brief(text)
    if not normalized:
        return ""
    for separator in (". ", ".\n", "\n"):
        if separator in normalized:
            return normalized.split(separator, 1)[0].strip().rstrip(".")
    return normalized.rstrip(".")


def _humanize_identifier(identifier: str) -> str:
    """Render a stable human-readable label from an identifier."""

    text = identifier.replace(".", " ").replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else identifier


def _role_label_from_identifier(identifier: str) -> str:
    """Render a noun-like participant label from an identifier."""

    if not identifier:
        return identifier

    if "." in identifier:
        owner, member = identifier.rsplit(".", 1)
        owner_label = MODULE_ROLE_LABELS.get(owner.split(".", 1)[0], _humanize_identifier(owner))
        member_key = member.lower()
        if owner.split(".", 1)[0] == "json":
            if member_key == "loads":
                return "JSON Loader"
            if member_key == "dumps":
                return "JSON Dumper"
        if owner.split(".", 1)[0] == "re":
            return "Regex Engine"
        if owner.split(".", 1)[0] == "ast":
            return "AST Tool"
        if owner.split(".", 1)[0] == "dataclasses" and member_key == "asdict":
            return "Dataclass Serializer"
        if member_key == "to_dict":
            return f"{owner_label} Serializer"
        if member_key in ROLE_PREFIXES:
            return f"{owner_label} {ROLE_PREFIXES[member_key]}"
        return f"{owner_label} {_humanize_identifier(member)}"

    parts = identifier.split("_")
    if not parts:
        return _humanize_identifier(identifier)
    prefix = parts[0].lower()
    if identifier == "asdict":
        return "Dataclass Serializer"
    if prefix in ROLE_PREFIXES and len(parts) > 1:
        remainder = _humanize_identifier("_".join(parts[1:]))
        return f"{remainder} {ROLE_PREFIXES[prefix]}"
    return _humanize_identifier(identifier)


def _call_label_from_identifier(identifier: str) -> str:
    """Render a readable call label for flow steps and participants."""

    return _role_label_from_identifier(identifier)


def _sanitize_mermaid_alias(value: str) -> str:
    """Build a Mermaid-safe alias from a human-readable label."""

    alias = value.replace(".", "_").replace("-", "_")
    alias = re.sub(r"[^0-9A-Za-z_]+", "_", alias)
    alias = re.sub(r"_+", "_", alias).strip("_")
    return alias or "participant"


def _anchor(source_path: Path, node: ast.AST) -> str:
    """Build a line-range anchor for an AST node."""

    display_path = _display_source_path(source_path)
    line_start = max(1, int(getattr(node, "lineno", 1) or 1))
    line_end = max(line_start, int(getattr(node, "end_lineno", line_start) or line_start))
    return f"{display_path}:{line_start}-{line_end}"


def _line_span(node: ast.AST) -> tuple[int, int]:
    """Return a stable 1-based line span for an AST node."""

    line_start = max(1, int(getattr(node, "lineno", 1) or 1))
    line_end = max(line_start, int(getattr(node, "end_lineno", line_start) or line_start))
    return line_start, line_end


def _format_signature(node: ast.AST, qualified_name: str) -> str:
    """Render a Python signature for a function or method."""

    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return f"class {qualified_name}"

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


def _format_class_signature(node: ast.ClassDef, qualified_name: str) -> str:
    """Render a Python class signature."""

    bases: list[str] = []
    for base in node.bases:
        if hasattr(ast, "unparse"):
            bases.append(ast.unparse(base))
        else:  # pragma: no cover - Python 3.8 fallback
            bases.append(getattr(base, "id", "object"))
    suffix = f"({', '.join(bases)})" if bases else ""
    return f"class {qualified_name}{suffix}"


def _resolve_call_name(node: ast.AST) -> str:
    """Resolve a readable name for an AST call target."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Call):
            return ""
        parent = _resolve_call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _collect_import_aliases(tree: ast.AST) -> tuple[str, ...]:
    """Collect imported names that can be treated as meaningful dependencies."""

    aliases: list[str] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases.append(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases.append(alias.asname or alias.name)
    return _unique_preserve_order(aliases)


def _collect_local_symbol_names(tree: ast.AST) -> tuple[str, ...]:
    """Collect top-level declaration names from a Python module."""

    names: list[str] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return _unique_preserve_order(names)


def _is_meaningful_call_target(name: str, local_symbols: Iterable[str], import_aliases: Iterable[str]) -> bool:
    """Return True when a call target should appear in the taxonomy."""

    if not name:
        return False
    base = name.split(".", 1)[0]
    if base in BUILTIN_CALL_NAMES:
        return False
    if base.endswith("Error") or base.endswith("Exception"):
        return False
    local_set = set(local_symbols)
    import_set = set(import_aliases)
    if name in local_set:
        return True
    if base in local_set:
        return True
    if base in import_set:
        return True
    return False


def _unique_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    """Return values without duplicates while preserving order."""

    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return tuple(seen.keys())


def _collect_conditions_text(source_text: str, node: ast.AST) -> str:
    """Return a readable condition or expression snippet."""

    segment = ast.get_source_segment(source_text, node)
    if segment:
        return _normalize_brief(segment)
    if hasattr(ast, "unparse"):
        try:
            return _normalize_brief(ast.unparse(node))
        except Exception:  # pragma: no cover - defensive fallback
            return ""
    return ""


class _TaxonomyFlowCollector(ast.NodeVisitor):
    """Collect ordered flow signals from a function body."""

    def __init__(self, source_text: str, local_symbols: Iterable[str], import_aliases: Iterable[str]) -> None:
        self.source_text = source_text
        self.local_symbols = set(local_symbols)
        self.import_aliases = set(import_aliases)
        self.calls: list[str] = []
        self.flow_steps: list[str] = []
        self.branch_markers: list[str] = []
        self.conditions: list[CodeTaxonomyCondition] = []
        self.return_points: list[int] = []

    def _add_condition(self, kind: str, node: ast.AST, source_text: str, meaning: str) -> None:
        line_start, line_end = _line_span(node)
        self.conditions.append(
            CodeTaxonomyCondition(
                kind=kind,
                source_text=source_text,
                meaning=meaning,
                line_start=line_start,
                line_end=line_end,
            )
        )

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802
        name = _resolve_call_name(node.func)
        if _is_meaningful_call_target(name, self.local_symbols, self.import_aliases):
            self.calls.append(name)
            self.flow_steps.append(f"call {name}")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> Any:  # noqa: N802
        source_text = _collect_conditions_text(self.source_text, node.test)
        self.branch_markers.append("if")
        self.flow_steps.append(f"branch: if {source_text}".strip())
        self._add_condition("if", node, source_text, f"branch on {source_text}" if source_text else "branch on if")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:  # noqa: N802
        if hasattr(ast, "unparse"):
            target = _normalize_brief(ast.unparse(node.target))
            iterator = _normalize_brief(ast.unparse(node.iter))
            source_text = f"for {target} in {iterator}"
        else:  # pragma: no cover - Python 3.8 fallback
            source_text = "for-loop"
        self.branch_markers.append("for")
        self.flow_steps.append(f"branch: {source_text}")
        self._add_condition("for", node, source_text, f"loop over {source_text.removeprefix('for ').strip()}")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:  # noqa: N802
        source_text = _collect_conditions_text(self.source_text, node.test)
        self.branch_markers.append("while")
        self.flow_steps.append(f"branch: while {source_text}".strip())
        self._add_condition("while", node, source_text, f"loop while {source_text}" if source_text else "while loop")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> Any:  # noqa: N802
        self.branch_markers.append("try")
        self.flow_steps.append("branch: try")
        self._add_condition("try", node, "try", "exception handling block")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:  # noqa: N802
        source_text = "except"
        if node.type is not None:
            if hasattr(ast, "unparse"):
                source_text = f"except {_normalize_brief(ast.unparse(node.type))}"
            else:  # pragma: no cover - Python 3.8 fallback
                source_text = "except"
        self.branch_markers.append("except")
        self.flow_steps.append(f"branch: {source_text}")
        self._add_condition("except", node, source_text, f"exception path {source_text}")
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> Any:  # noqa: N802
        line_start, _ = _line_span(node)
        self.return_points.append(line_start)
        self.flow_steps.append("return")
        self.generic_visit(node)


def _collect_decorators(node: ast.AST) -> tuple[str, ...]:
    """Collect readable decorator names from a declaration node."""

    decorators = getattr(node, "decorator_list", [])
    names: list[str] = []
    for decorator in decorators:
        if hasattr(ast, "unparse"):
            names.append(_normalize_brief(ast.unparse(decorator)))
        elif isinstance(decorator, ast.Name):  # pragma: no cover - Python 3.8 fallback
            names.append(decorator.id)
    return _unique_preserve_order(names)


def _collect_docstring(node: ast.AST) -> str:
    """Collect and normalize a docstring from a declaration node."""

    return _normalize_brief(ast.get_docstring(node) or "")


def _collect_symbol_notes(
    kind: str,
    docstring: str,
    branch_markers: tuple[str, ...],
    return_points: tuple[int, ...],
) -> tuple[str, ...]:
    """Build summary notes for a symbol declaration."""

    notes = [f"Observed as a {kind} declaration in the source file."]
    if branch_markers:
        notes.append(f"Branch markers detected: {', '.join(branch_markers)}.")
    if return_points:
        notes.append(f"Return points detected on lines: {', '.join(str(point) for point in return_points)}.")
    if docstring:
        notes.append("Docstring captured as part of the taxonomy.")
    else:
        notes.append("No docstring was present; the declaration was inferred from AST structure.")
    return tuple(notes)


def _collect_execution_path_notes(
    kind: str,
    docstring: str,
    branch_markers: tuple[str, ...],
    return_points: tuple[int, ...],
    conditions: tuple[CodeTaxonomyCondition, ...],
) -> tuple[str, ...]:
    """Build summary notes for an execution path."""

    notes = [f"Observed as a {kind} in the code flow."]
    if branch_markers:
        notes.append(f"Branch markers detected: {', '.join(branch_markers)}.")
    if conditions:
        notes.append(f"Captured {len(conditions)} condition(s) for reuse by the worker bee.")
    if return_points:
        notes.append(f"Return points detected on lines: {', '.join(str(point) for point in return_points)}.")
    if docstring:
        notes.append("Docstring captured as part of the contract.")
    else:
        notes.append("No docstring was present; the flow was inferred from AST structure.")
    return tuple(notes)


def _build_symbol_from_node(
    source_path: Path,
    source_text: str,
    local_symbols: Iterable[str],
    import_aliases: Iterable[str],
    node: ast.AST,
    qualified_name: str,
    kind: str,
    parent_class: str = "",
) -> CodeTaxonomySymbol:
    """Build a taxonomy symbol from a function, method, or class node."""

    if isinstance(node, ast.ClassDef):
        collector = None
        signature = _format_class_signature(node, qualified_name)
    else:
        collector = _TaxonomyFlowCollector(source_text, local_symbols, import_aliases)
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for statement in node.body:
            collector.visit(statement)
        signature = _format_signature(node, qualified_name)

    docstring = _collect_docstring(node)
    decorators = _collect_decorators(node)
    line_start, line_end = _line_span(node)
    label = _humanize_identifier(qualified_name)
    role = _role_label_from_identifier(qualified_name)
    responsibility = _first_sentence(docstring) or f"Observed {kind} declaration in the source file"
    anchor = _anchor(source_path, node)
    if collector is None:
        branch_markers = ()
        return_points = ()
        calls: tuple[str, ...] = ()
        conditions: tuple[CodeTaxonomyCondition, ...] = ()
        notes = (
            f"Observed as a {kind} declaration in the source file.",
            "Class declarations are inventory anchors; methods carry the execution paths.",
            "Docstring captured as part of the taxonomy." if docstring else "No docstring was present; the declaration was inferred from AST structure.",
        )
    else:
        branch_markers = _unique_preserve_order(collector.branch_markers)
        return_points = tuple(collector.return_points)
        calls = _unique_preserve_order(collector.calls)
        conditions = tuple(collector.conditions)
        notes = _collect_symbol_notes(kind, docstring, branch_markers, return_points)

    return CodeTaxonomySymbol(
        name=qualified_name,
        label=label,
        kind=kind,
        anchor=anchor,
        line_start=line_start,
        line_end=line_end,
        signature=signature,
        docstring=docstring,
        parent_class=parent_class,
        role=role,
        responsibility=responsibility,
        decorators=decorators,
        calls=calls,
        conditions=conditions,
        branch_markers=branch_markers,
        return_points=return_points,
        notes=notes,
    )


def _build_execution_path_from_node(
    source_path: Path,
    source_text: str,
    local_symbols: Iterable[str],
    import_aliases: Iterable[str],
    node: ast.AST,
    qualified_name: str,
    kind: str,
    parent_class: str = "",
) -> CodeTaxonomyExecutionPath:
    """Build a taxonomy execution path from a function or method node."""

    collector = _TaxonomyFlowCollector(source_text, local_symbols, import_aliases)
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    for statement in node.body:
        collector.visit(statement)

    docstring = _collect_docstring(node)
    signature = _format_signature(node, qualified_name)
    line_start, line_end = _line_span(node)
    branch_markers = _unique_preserve_order(collector.branch_markers)
    call_targets = _unique_preserve_order(collector.calls)
    participants = _unique_preserve_order(
        ("Caller", _role_label_from_identifier(qualified_name), *(_call_label_from_identifier(call) for call in call_targets))
    )
    flow_steps: list[str] = [f"invoke {_call_label_from_identifier(qualified_name)}"]
    if parent_class:
        flow_steps.append(f"owner {_role_label_from_identifier(parent_class)}")
    flow_steps.extend(
        f"call {_call_label_from_identifier(step.removeprefix('call ').strip())}" if step.startswith("call ") else step
        for step in collector.flow_steps
    )
    if not call_targets:
        flow_steps.append("no helper calls observed")
    flow_steps.append("return")
    label = _humanize_identifier(qualified_name)
    role = _role_label_from_identifier(qualified_name)
    responsibility = _first_sentence(docstring) or f"Observed {kind} execution path in the source file"
    anchor = _anchor(source_path, node)
    notes = _collect_execution_path_notes(kind, docstring, branch_markers, tuple(collector.return_points), tuple(collector.conditions))

    return CodeTaxonomyExecutionPath(
        name=qualified_name,
        label=label,
        kind=kind,
        anchor=anchor,
        line_start=line_start,
        line_end=line_end,
        signature=signature,
        docstring=docstring,
        parent_class=parent_class,
        participants=participants,
        flow_steps=tuple(flow_steps),
        calls=call_targets,
        conditions=tuple(collector.conditions),
        branch_markers=branch_markers,
        return_points=tuple(collector.return_points),
        role=role,
        responsibility=responsibility,
        notes=notes,
    )


def scan_python_source_taxonomy(source_path: Path, include_private: bool = False) -> CodeTaxonomyDocument:
    """Scan a Python file into a deterministic code taxonomy document."""

    if not source_path.exists():
        raise SchemaError(f"source file does not exist: {source_path}")
    if not source_path.is_file():
        raise SchemaError(f"source path is not a file: {source_path}")

    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"cannot read source file {source_path}: {exc}") from exc

    try:
        tree = ast.parse(source_text, filename=str(source_path))
    except SyntaxError as exc:
        raise SchemaError(f"source file is not valid Python: {source_path}: {exc}") from exc

    local_symbols = _collect_local_symbol_names(tree)
    import_aliases = _collect_import_aliases(tree)

    def should_include(name: str) -> bool:
        return include_private or not name.startswith("_")

    symbols: list[CodeTaxonomySymbol] = []
    execution_paths: list[CodeTaxonomyExecutionPath] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not should_include(node.name):
                continue
            qualified_name = node.name
            symbols.append(
                _build_symbol_from_node(
                    source_path,
                    source_text,
                    local_symbols,
                    import_aliases,
                    node,
                    qualified_name,
                    "class",
                )
            )
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and should_include(member.name):
                    qualified_name = f"{node.name}.{member.name}"
                    symbols.append(
                        _build_symbol_from_node(
                            source_path,
                            source_text,
                            local_symbols,
                            import_aliases,
                            member,
                            qualified_name,
                            "method",
                            parent_class=node.name,
                        )
                    )
                    execution_paths.append(
                        _build_execution_path_from_node(
                            source_path,
                            source_text,
                            local_symbols,
                            import_aliases,
                            member,
                            qualified_name,
                            "method",
                            parent_class=node.name,
                        )
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if should_include(node.name):
                symbols.append(
                    _build_symbol_from_node(
                        source_path,
                        source_text,
                        local_symbols,
                        import_aliases,
                        node,
                        node.name,
                        "function",
                    )
                )
                execution_paths.append(
                    _build_execution_path_from_node(
                        source_path,
                        source_text,
                        local_symbols,
                        import_aliases,
                        node,
                        node.name,
                        "function",
                    )
                )

    if not symbols:
        raise SchemaError(f"no public declarations were found in {source_path}")

    display_source = _display_source_path(source_path)
    summary = (
        f"Extracted {len(symbols)} symbol(s) and {len(execution_paths)} execution path(s) from {Path(display_source).name}."
    )
    notes = (
        "The worker bee extracts a deterministic taxonomy before any model review.",
        "The taxonomy JSON is the reusable source of truth for later CRUD and observation passes.",
    )
    metadata = {
        "source": "generation_fabric.worker_bee.taxonomy",
        "include_private": include_private,
        "symbol_count": len(symbols),
        "execution_path_count": len(execution_paths),
    }

    return CodeTaxonomyDocument(
        source_file=display_source,
        module_path=_module_path(source_path),
        source_hash=_source_hash(source_text),
        shape="code-taxonomy",
        summary=summary,
        symbols=tuple(symbols),
        execution_paths=tuple(execution_paths),
        notes=notes,
        metadata=metadata,
    )


def build_code_taxonomy_document_schema(
    source_path: Path,
    taxonomy: CodeTaxonomyDocument,
    *,
    title: str = "",
) -> dict[str, Any]:
    """Build the JSON Schema contract for code taxonomy output."""

    resolved_title = title.strip() or f"Code Taxonomy: {source_path.stem}"
    symbol_sample = [symbol.to_dict() for symbol in taxonomy.symbols[:3]]
    path_sample = [path.to_dict() for path in taxonomy.execution_paths[:3]]
    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": resolved_title,
        "type": "object",
        "properties": {
            "source_file": {
                "type": "string",
                "x-sample": taxonomy.source_file,
            },
            "module_path": {
                "type": "string",
                "x-sample": taxonomy.module_path,
            },
            "source_hash": {
                "type": "string",
                "x-sample": taxonomy.source_hash,
            },
            "shape": {
                "type": "string",
                "x-sample": taxonomy.shape,
            },
            "summary": {
                "type": "string",
                "x-sample": taxonomy.summary,
            },
            "symbols": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "label": {"type": "string"},
                        "kind": {"type": "string"},
                        "anchor": {"type": "string"},
                        "line_start": {"type": "integer"},
                        "line_end": {"type": "integer"},
                        "signature": {"type": "string"},
                        "docstring": {"type": "string"},
                        "parent_class": {"type": "string"},
                        "role": {"type": "string"},
                        "responsibility": {"type": "string"},
                        "decorators": {"type": "array", "items": {"type": "string"}},
                        "calls": {"type": "array", "items": {"type": "string"}},
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string"},
                                    "source_text": {"type": "string"},
                                    "meaning": {"type": "string"},
                                    "line_start": {"type": "integer"},
                                    "line_end": {"type": "integer"},
                                },
                                "required": ["kind", "source_text", "meaning", "line_start", "line_end"],
                            },
                        },
                        "branch_markers": {"type": "array", "items": {"type": "string"}},
                        "return_points": {"type": "array", "items": {"type": "integer"}},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "name",
                        "label",
                        "kind",
                        "anchor",
                        "line_start",
                        "line_end",
                        "signature",
                        "docstring",
                        "parent_class",
                        "role",
                        "responsibility",
                        "decorators",
                        "calls",
                        "conditions",
                        "branch_markers",
                        "return_points",
                        "notes",
                    ],
                },
                "x-sample": symbol_sample,
            },
            "execution_paths": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "label": {"type": "string"},
                        "kind": {"type": "string"},
                        "anchor": {"type": "string"},
                        "line_start": {"type": "integer"},
                        "line_end": {"type": "integer"},
                        "signature": {"type": "string"},
                        "docstring": {"type": "string"},
                        "parent_class": {"type": "string"},
                        "participants": {"type": "array", "items": {"type": "string"}},
                        "flow_steps": {"type": "array", "items": {"type": "string"}},
                        "calls": {"type": "array", "items": {"type": "string"}},
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string"},
                                    "source_text": {"type": "string"},
                                    "meaning": {"type": "string"},
                                    "line_start": {"type": "integer"},
                                    "line_end": {"type": "integer"},
                                },
                                "required": ["kind", "source_text", "meaning", "line_start", "line_end"],
                            },
                        },
                        "branch_markers": {"type": "array", "items": {"type": "string"}},
                        "return_points": {"type": "array", "items": {"type": "integer"}},
                        "role": {"type": "string"},
                        "responsibility": {"type": "string"},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "name",
                        "label",
                        "kind",
                        "anchor",
                        "line_start",
                        "line_end",
                        "signature",
                        "docstring",
                        "parent_class",
                        "participants",
                        "flow_steps",
                        "calls",
                        "conditions",
                        "branch_markers",
                        "return_points",
                        "role",
                        "responsibility",
                        "notes",
                    ],
                },
                "x-sample": path_sample,
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
                "x-sample": list(taxonomy.notes),
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "include_private": {"type": "boolean"},
                    "symbol_count": {"type": "integer"},
                    "execution_path_count": {"type": "integer"},
                },
                "required": ["source", "include_private", "symbol_count", "execution_path_count"],
                "x-sample": taxonomy.metadata,
            },
        },
        "required": ["source_file", "module_path", "source_hash", "shape", "summary", "symbols", "execution_paths", "notes"],
    }
    validate_schema_node(schema)
    return schema


def build_code_taxonomy_document(
    source_file: str,
    *,
    title: str = "",
    include_private: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the schema and JSON data for a source file taxonomy."""

    source_path = Path(source_file)
    taxonomy = scan_python_source_taxonomy(source_path, include_private=include_private)
    schema = build_code_taxonomy_document_schema(source_path, taxonomy, title=title)
    data = taxonomy.to_dict()
    validate_instance_against_schema(schema, data)
    return schema, data


def write_code_taxonomy_document(
    source_file: str,
    *,
    output: str = "",
    title: str = "",
    include_private: bool = False,
    overwrite: bool = False,
) -> CodeTaxonomyDocumentPaths:
    """Write a taxonomy contract to disk."""

    schema, data = build_code_taxonomy_document(
        source_file,
        title=title,
        include_private=include_private,
    )

    source_path = Path(source_file)
    if output:
        data_path = Path(output)
        if not data_path.suffix:
            data_path = data_path.with_suffix(".json")
    else:
        data_path = Path("generated") / f"{source_path.stem}-taxonomy.json"

    if data_path.exists() and not overwrite:
        raise SchemaError(f"refusing to overwrite existing file: {data_path}")

    schema_path = data_path.with_name(f"{data_path.stem}.schema.json")
    if schema_path.exists() and not overwrite:
        raise SchemaError(f"refusing to overwrite existing file: {schema_path}")

    write_json_file_atomic(schema_path, schema)
    write_json_file_atomic(data_path, data)
    return CodeTaxonomyDocumentPaths(schema_path=schema_path, data_path=data_path)


__all__ = [
    "CodeTaxonomyCondition",
    "CodeTaxonomyDocument",
    "CodeTaxonomyDocumentPaths",
    "CodeTaxonomyExecutionPath",
    "CodeTaxonomySymbol",
    "build_code_taxonomy_document",
    "build_code_taxonomy_document_schema",
    "scan_python_source_taxonomy",
    "write_code_taxonomy_document",
]
