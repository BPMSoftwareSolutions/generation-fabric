"""Deterministic object-model extraction and report generation for worker-bee observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import ast
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from generation_fabric.core.artifacts import ContractArtifact, SidecarPaths, resolve_sidecar_paths, write_contract_artifact
from generation_fabric.core.serialization import to_jsonable_dataclass
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

from .object_coherence import audit_object_model_coherence, classify_object_pattern
from .object_diagram import render_object_model_class_diagram, render_object_model_package_diagrams


ObjectModelPaths = SidecarPaths

IGNORED_CALL_NAMES = {
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "print",
    "range",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
}

MUTATING_CALL_KEYWORDS = {
    "append",
    "clear",
    "create",
    "delete",
    "extend",
    "insert",
    "persist",
    "pop",
    "remove",
    "save",
    "setdefault",
    "update",
    "write",
}

CLASS_KIND_PRIORITY = (
    "protocol",
    "visitor",
    "exception",
    "artifact_paths",
    "artifact_bundle",
    "provider",
    "command_session",
    "report_builder",
    "renderer_target",
    "frozen_value_object",
    "value_object",
)


@dataclass(frozen=True)
class ObjectModelField:
    """Describe one observed class field."""

    name: str
    annotation: str
    default_kind: str
    line_start: int
    line_end: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the field into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelMethod:
    """Describe one observed class method."""

    name: str
    signature: str
    decorators: tuple[str, ...]
    calls: tuple[str, ...]
    mutations: tuple[str, ...]
    returns: tuple[str, ...]
    line_start: int
    line_end: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the method into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelClass:
    """Describe one observed class declaration."""

    name: str
    qualified_name: str
    module_path: str
    source_file: str
    anchor: str
    bases: tuple[str, ...]
    decorators: tuple[str, ...]
    fields: tuple[ObjectModelField, ...]
    methods: tuple[ObjectModelMethod, ...]
    kind: str
    role: str
    responsibility: str
    pattern_signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the class into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelRelationship:
    """Describe one observed relationship between object-model nodes."""

    source: str
    target: str
    relationship_type: str
    evidence: str
    anchor: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the relationship into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelPatternSignal:
    """Describe one observed design-pattern signal."""

    class_name: str
    pattern: str
    status: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the pattern signal into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelCoherenceCheck:
    """Describe one deterministic object-model coherence check."""

    check: str
    status: str
    detail: str
    symbols: tuple[str, ...]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the coherence check into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelDiagram:
    """Describe one rendered Mermaid diagram."""

    scope: str
    name: str
    language: str
    diagram: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diagram into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ObjectModelDocument:
    """Describe the deterministic object model for a set of Python source files."""

    source_roots: tuple[str, ...]
    source_files: tuple[str, ...]
    source_hash: str
    shape: str
    scope: str
    summary: str
    classes: tuple[ObjectModelClass, ...]
    relationships: tuple[ObjectModelRelationship, ...]
    patterns: tuple[ObjectModelPatternSignal, ...]
    checks: tuple[ObjectModelCoherenceCheck, ...]
    diagrams: tuple[ObjectModelDiagram, ...]
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the document into JSON-friendly data."""

        return to_jsonable_dataclass(self)


def _repo_root() -> Path:
    """Return the repository root."""

    return Path(__file__).resolve().parents[2]


def _normalize_text(value: Any) -> str:
    """Render a stable object-model string."""

    return " ".join(str(value).split()).strip()


def _humanize_identifier(identifier: str) -> str:
    """Render a stable human-readable label from an identifier."""

    text = identifier.replace(".", " ").replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else identifier


def _first_sentence(text: str) -> str:
    """Return the first sentence or line from a docstring."""

    normalized = _normalize_text(text)
    if not normalized:
        return ""
    for separator in (". ", ".\n", "\n"):
        if separator in normalized:
            return normalized.split(separator, 1)[0].strip().rstrip(".")
    return normalized.rstrip(".")


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


def _source_hash(source_texts: Iterable[tuple[Path, str]]) -> str:
    """Compute a deterministic hash for a set of source files."""

    hasher = sha256()
    for source_path, source_text in source_texts:
        hasher.update(source_path.as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(source_text.encode("utf-8"))
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def _line_span(node: ast.AST) -> tuple[int, int]:
    """Return a stable 1-based line span for an AST node."""

    line_start = max(1, int(getattr(node, "lineno", 1) or 1))
    line_end = max(line_start, int(getattr(node, "end_lineno", line_start) or line_start))
    return line_start, line_end


def _anchor(source_path: Path, node: ast.AST) -> str:
    """Build a line-range anchor for an AST node."""

    display_path = _display_source_path(source_path)
    line_start, line_end = _line_span(node)
    return f"{display_path}:{line_start}-{line_end}"


def _normalize_decorators(node: ast.AST) -> tuple[str, ...]:
    """Return normalized decorator text for a class or method."""

    decorators: list[str] = []
    for decorator in getattr(node, "decorator_list", []):
        if hasattr(ast, "unparse"):
            decorators.append(f"@{_normalize_text(ast.unparse(decorator))}")
        else:  # pragma: no cover - Python 3.8 fallback
            decorators.append(f"@{getattr(decorator, 'id', 'decorator')}")
    return tuple(decorators)


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


def _is_mutating_call_target(name: str) -> bool:
    """Return True when a call target mutates state or writes data."""

    if not name:
        return False
    lowered = name.lower()
    segments = re.split(r"[^a-z0-9]+", lowered)
    for keyword in MUTATING_CALL_KEYWORDS:
        if keyword in segments or any(segment.startswith(keyword) for segment in segments):
            return True
    return False


def _expression_text(source_text: str, node: ast.AST, *, max_length: int = 120) -> str:
    """Render a readable expression snippet."""

    segment = ""
    if source_text:
        try:
            segment = ast.get_source_segment(source_text, node) or ""
        except Exception:  # pragma: no cover - defensive fallback
            segment = ""
    if not segment and hasattr(ast, "unparse"):
        try:
            segment = ast.unparse(node)
        except Exception:  # pragma: no cover - defensive fallback
            segment = ""
    normalized = _normalize_text(segment or "")
    if not normalized:
        return ""
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max(0, max_length - 3)].rstrip() + "..."


def _annotation_text(node: ast.AST | None) -> str:
    """Render a type annotation as text."""

    if node is None:
        return ""
    if hasattr(ast, "unparse"):
        try:
            return _normalize_text(ast.unparse(node))
        except Exception:  # pragma: no cover - defensive fallback
            return ""
    return getattr(node, "id", "")


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
        annotation = _annotation_text(arg.annotation)
        if annotation:
            rendered = f"{rendered}: {annotation}"
        default_index = index - defaults_offset
        if default_index >= 0:
            default_value = args.defaults[default_index]
            default_text = _expression_text("", default_value) if isinstance(default_value, ast.AST) else ""
            if not default_text and hasattr(ast, "unparse"):
                default_text = _normalize_text(ast.unparse(default_value))
            if default_text:
                rendered = f"{rendered} = {default_text}"
        params.append(rendered)

    if args.vararg is not None:
        params.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        params.append("*")

    for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
        rendered = kwarg.arg
        annotation = _annotation_text(kwarg.annotation)
        if annotation:
            rendered = f"{rendered}: {annotation}"
        if default is not None:
            default_text = _expression_text("", default) if isinstance(default, ast.AST) else ""
            if not default_text and hasattr(ast, "unparse"):
                default_text = _normalize_text(ast.unparse(default))
            if default_text:
                rendered = f"{rendered} = {default_text}"
        params.append(rendered)

    if args.kwarg is not None:
        params.append(f"**{args.kwarg.arg}")

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return_annotation = ""
    if getattr(node, "returns", None) is not None:
        return_annotation = f" -> {_annotation_text(node.returns)}"
    return f"{prefix} {qualified_name}({', '.join(params)}){return_annotation}"


def _collect_import_aliases(tree: ast.AST) -> tuple[str, ...]:
    """Collect imported names that may show up in annotations and calls."""

    aliases: list[str] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases.append(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases.append(alias.asname or alias.name)
    return tuple(dict.fromkeys(aliases))


def _collect_local_class_names(tree: ast.AST, include_private: bool) -> tuple[str, ...]:
    """Collect top-level class names from a module."""

    names: list[str] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and (include_private or not node.name.startswith("_")):
            names.append(node.name)
    return tuple(dict.fromkeys(names))


def _collect_docstring(node: ast.AST) -> str:
    """Collect the docstring for a class or method."""

    return ast.get_docstring(node) or ""


def _collect_class_field(node: ast.stmt) -> ObjectModelField | None:
    """Convert one class-level statement into a field record when possible."""

    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        line_start, line_end = _line_span(node)
        default_kind = "missing"
        value = getattr(node, "value", None)
        if value is None:
            default_kind = "missing"
        elif isinstance(value, ast.Call):
            call_name = _resolve_call_name(value.func)
            if call_name.endswith("field"):
                default_kind = "factory" if any(keyword.arg == "default_factory" for keyword in value.keywords) else "call"
            else:
                default_kind = "call"
        elif isinstance(value, ast.Constant):
            default_kind = "none" if value.value is None else "literal"
        else:
            default_kind = "expression"
        return ObjectModelField(
            name=node.target.id,
            annotation=_annotation_text(node.annotation),
            default_kind=default_kind,
            line_start=line_start,
            line_end=line_end,
        )

    if isinstance(node, ast.Assign):
        targets = [target for target in node.targets if isinstance(target, ast.Name)]
        if not targets:
            return None
        line_start, line_end = _line_span(node)
        value = getattr(node, "value", None)
        if isinstance(value, ast.Call):
            default_kind = "call"
        elif isinstance(value, ast.Constant):
            default_kind = "none" if value.value is None else "literal"
        else:
            default_kind = "expression"
        return ObjectModelField(
            name=targets[0].id,
            annotation="",
            default_kind=default_kind,
            line_start=line_start,
            line_end=line_end,
        )

    return None


def _self_assignment_text(source_text: str, target: ast.AST, value: ast.AST | None = None) -> str:
    """Render a mutation description for a self attribute assignment."""

    if not isinstance(target, ast.Attribute):
        return ""
    if not isinstance(target.value, ast.Name) or target.value.id not in {"self", "cls"}:
        return ""
    rendered_target = _expression_text(source_text, target, max_length=80)
    rendered_value = _expression_text(source_text, value, max_length=80) if value is not None else ""
    if rendered_value:
        return f"{rendered_target} = {rendered_value}"
    return f"{rendered_target} = ..."


class _MethodBodyCollector(ast.NodeVisitor):
    """Collect method-level calls, mutations, and returns."""

    def __init__(self, source_text: str) -> None:
        self.source_text = source_text
        self.calls: list[str] = []
        self.mutations: list[str] = []
        self.returns: list[str] = []

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802
        name = _resolve_call_name(node.func)
        if name and name not in IGNORED_CALL_NAMES:
            self.calls.append(name)
            if _is_mutating_call_target(name):
                payload = []
                for arg in node.args[:3]:
                    text = _expression_text(self.source_text, arg, max_length=40)
                    if text:
                        payload.append(text)
                for keyword in node.keywords[:3]:
                    value_text = _expression_text(self.source_text, keyword.value, max_length=32)
                    if not value_text:
                        continue
                    if keyword.arg:
                        payload.append(f"{keyword.arg}={value_text}")
                    else:
                        payload.append(f"**{value_text}")
                suffix = f": {', '.join(payload)}" if payload else ""
                self.mutations.append(f"{name}{suffix}")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: N802
        for target in node.targets:
            mutation = _self_assignment_text(self.source_text, target, getattr(node, "value", None))
            if mutation:
                self.mutations.append(mutation)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:  # noqa: N802
        mutation = _self_assignment_text(self.source_text, node.target, getattr(node, "value", None))
        if mutation:
            self.mutations.append(mutation)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:  # noqa: N802
        mutation = _self_assignment_text(self.source_text, node.target, getattr(node, "value", None))
        if mutation:
            self.mutations.append(f"{mutation} (augmented)")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> Any:  # noqa: N802
        for target in node.targets:
            mutation = _self_assignment_text(self.source_text, target)
            if mutation:
                self.mutations.append(f"delete {mutation}")
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> Any:  # noqa: N802
        if node.value is not None:
            text = _expression_text(self.source_text, node.value, max_length=120)
            if text:
                self.returns.append(text)
        self.generic_visit(node)


def _collect_method_names(methods: Sequence[ObjectModelMethod]) -> tuple[str, ...]:
    """Return method names in declaration order."""

    return tuple(method.name for method in methods)


def _class_role(kind: str, class_name: str) -> str:
    """Return a human-readable role label for a class kind."""

    mapping = {
        "protocol": "Protocol",
        "visitor": "Visitor",
        "exception": "Exception",
        "artifact_paths": "Artifact Paths",
        "artifact_bundle": "Artifact Bundle",
        "provider": "Provider",
        "command_session": "Command Session",
        "report_builder": "Report Builder",
        "renderer_target": "Renderer Target",
        "frozen_value_object": "Value Object",
        "value_object": "Value Object",
    }
    return mapping.get(kind, _humanize_identifier(class_name))


def _class_responsibility(kind: str, docstring: str) -> str:
    """Return a readable responsibility summary for a class."""

    summary = _first_sentence(docstring)
    if summary:
        return summary
    return f"Observed as a {kind.replace('_', ' ')} declaration in the source file"


def _class_kind(pattern_names: tuple[str, ...], class_name: str, methods: tuple[ObjectModelMethod, ...]) -> str:
    """Choose a canonical class kind from the observed pattern signals."""

    if "protocol" in pattern_names:
        return "protocol"
    if "visitor" in pattern_names:
        return "visitor"
    if "exception" in pattern_names:
        return "exception"
    if "artifact_paths" in pattern_names:
        return "artifact_paths"
    if "artifact_bundle" in pattern_names:
        return "artifact_bundle"
    if "provider" in pattern_names:
        return "provider"
    if "command_session" in pattern_names:
        return "command_session"
    if "report_builder" in pattern_names:
        return "report_builder"
    if "renderer_target" in pattern_names:
        return "renderer_target"
    if "frozen_value_object" in pattern_names:
        return "frozen_value_object"
    if "value_object" in pattern_names:
        return "value_object"
    if class_name.endswith("Session"):
        return "command_session"
    if any(method.name == "to_dict" for method in methods):
        return "value_object"
    return "plain_class"


def _class_relationship_targets(annotation: str, class_names: set[str]) -> tuple[str, ...]:
    """Extract class targets from an annotation string."""

    if not annotation:
        return ()
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation)
    targets = [token for token in tokens if token in class_names]
    return tuple(dict.fromkeys(targets))


def _method_relationship_targets(method: ObjectModelMethod, class_names: set[str]) -> tuple[str, ...]:
    """Extract class targets from method call and return text."""

    targets: list[str] = []
    for call in method.calls:
        if call in class_names:
            targets.append(call)
        elif "." in call:
            tail = call.rsplit(".", 1)[-1]
            if tail in class_names:
                targets.append(tail)
        elif call in {"to_jsonable_dataclass", "write_contract_artifact", "render_markdown_document"}:
            targets.append(call)
    for returned in method.returns:
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", returned)
        for token in tokens:
            if token in class_names:
                targets.append(token)
    return tuple(dict.fromkeys(targets))


def _build_class_relationships(
    model_class: ObjectModelClass,
    class_names: set[str],
    class_lookup: dict[str, ObjectModelClass],
) -> tuple[ObjectModelRelationship, ...]:
    """Build relationship records for one class."""

    relationships: list[ObjectModelRelationship] = []
    source = model_class.name
    anchor = model_class.anchor

    for base in model_class.bases:
        base_name = base.rsplit(".", 1)[-1]
        if base_name in class_names:
            relationships.append(
                ObjectModelRelationship(
                    source=source,
                    target=base_name,
                    relationship_type="inherits",
                    evidence=base,
                    anchor=anchor,
                    confidence="high",
                )
            )

    if model_class.kind != "protocol":
        source_methods = {method.name for method in model_class.methods if not method.name.startswith("_")}
        for protocol_name, protocol_class in class_lookup.items():
            if protocol_class.kind != "protocol" or protocol_name == source:
                continue
            protocol_methods = {method.name for method in protocol_class.methods if not method.name.startswith("_")}
            if protocol_methods and protocol_methods.issubset(source_methods):
                relationships.append(
                    ObjectModelRelationship(
                        source=source,
                        target=protocol_name,
                        relationship_type="implements_protocol",
                        evidence="structural method parity",
                        anchor=anchor,
                        confidence="high",
                    )
                )

    field_targets: list[str] = []
    for field in model_class.fields:
        field_targets.extend(_class_relationship_targets(field.annotation, class_names))
    for target in tuple(dict.fromkeys(field_targets)):
        if target != source:
            relationships.append(
                ObjectModelRelationship(
                    source=source,
                    target=target,
                    relationship_type="composes",
                    evidence="field annotation",
                    anchor=anchor,
                    confidence="high",
                )
            )

    for method in model_class.methods:
        method_targets = _method_relationship_targets(method, class_names)
        for target in method_targets:
            if target == source:
                continue
            relationship_type = "instantiates"
            evidence = "method call"
            confidence = "medium"
            if target == "to_jsonable_dataclass":
                relationship_type = "serializes"
                evidence = "shared dataclass serializer helper"
                confidence = "high"
            elif target == "write_contract_artifact" or target.startswith("write_"):
                relationship_type = "writes_artifact"
                evidence = "artifact write helper"
                confidence = "high"
            elif target.startswith("render_"):
                relationship_type = "uses_renderer"
                evidence = "renderer helper"
                confidence = "high"
            elif target in class_names:
                relationship_type = "instantiates"
                evidence = "class constructor call"
                confidence = "high"
            relationships.append(
                ObjectModelRelationship(
                    source=source,
                    target=target,
                    relationship_type=relationship_type,
                    evidence=evidence,
                    anchor=anchor,
                    confidence=confidence,
                )
            )

    return tuple(relationships)


def _collect_source_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    """Expand a sequence of source roots into concrete Python files."""

    source_files: list[Path] = []
    for path in paths:
        if path.is_file():
            if path.suffix == ".py":
                source_files.append(path)
            continue
        if path.is_dir():
            source_files.extend(sorted(candidate for candidate in path.rglob("*.py") if candidate.is_file()))
            continue
        raise SchemaError(f"source path does not exist: {path}")
    deduped = tuple(dict.fromkeys(candidate.resolve() for candidate in source_files))
    if not deduped:
        raise SchemaError("no Python source files were found for object-model scanning")
    return deduped


def _collect_source_roots(paths: Sequence[Path]) -> tuple[str, ...]:
    """Render stable display strings for the observed scan roots."""

    roots: list[str] = []
    for path in paths:
        display = _display_source_path(path)
        if display not in roots:
            roots.append(display)
    return tuple(roots)


def _scan_classes(
    source_files: Sequence[Path],
    *,
    include_private: bool = False,
) -> tuple[ObjectModelClass, tuple[ObjectModelPatternSignal, ...]]:
    """Scan class declarations from a set of Python files."""

    classes: list[ObjectModelClass] = []
    pattern_signals: list[ObjectModelPatternSignal] = []

    for source_path in source_files:
        source_text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_text, filename=str(source_path))
        module_path = _module_path(source_path)
        local_class_names = _collect_local_class_names(tree, include_private)

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not include_private and node.name.startswith("_"):
                continue

            decorators = _normalize_decorators(node)
            bases = tuple(_annotation_text(base) if hasattr(base, "annotation") else _normalize_text(ast.unparse(base) if hasattr(ast, "unparse") else getattr(base, "id", "")) for base in node.bases)
            fields: list[ObjectModelField] = []
            methods: list[ObjectModelMethod] = []
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not include_private and member.name.startswith("_"):
                        continue
                    collector = _MethodBodyCollector(source_text)
                    for statement in member.body:
                        collector.visit(statement)
                    signature = _format_signature(member, f"{node.name}.{member.name}")
                    methods.append(
                        ObjectModelMethod(
                            name=member.name,
                            signature=signature,
                            decorators=_normalize_decorators(member),
                            calls=tuple(dict.fromkeys(collector.calls)),
                            mutations=tuple(dict.fromkeys(collector.mutations)),
                            returns=tuple(dict.fromkeys(collector.returns)),
                            line_start=_line_span(member)[0],
                            line_end=_line_span(member)[1],
                        )
                    )
                else:
                    field = _collect_class_field(member)
                    if field is not None:
                        if not include_private and field.name.startswith("_"):
                            continue
                        fields.append(field)

            docstring = _collect_docstring(node)
            preliminary = ObjectModelClass(
                name=node.name,
                qualified_name=f"{module_path}.{node.name}",
                module_path=module_path,
                source_file=_display_source_path(source_path),
                anchor=_anchor(source_path, node),
                bases=bases,
                decorators=decorators,
                fields=tuple(fields),
                methods=tuple(methods),
                kind="plain_class",
                role="",
                responsibility="",
                pattern_signals=(),
            )
            signals = classify_object_pattern(preliminary)
            signal_names = tuple(signal.pattern for signal in signals)
            kind = _class_kind(signal_names, node.name, tuple(methods))
            classes.append(
                ObjectModelClass(
                    name=node.name,
                    qualified_name=f"{module_path}.{node.name}",
                    module_path=module_path,
                    source_file=_display_source_path(source_path),
                    anchor=_anchor(source_path, node),
                    bases=bases,
                    decorators=decorators,
                    fields=tuple(fields),
                    methods=tuple(methods),
                    kind=kind,
                    role=_class_role(kind, node.name),
                    responsibility=_class_responsibility(kind, docstring),
                    pattern_signals=signal_names,
                )
            )
            pattern_signals.extend(signals)

    if not classes:
        raise SchemaError("no public class declarations were found in the scanned source files")

    return tuple(classes), tuple(pattern_signals)


def _collect_relationships(classes: Sequence[ObjectModelClass]) -> tuple[ObjectModelRelationship, ...]:
    """Collect structural relationships across all observed classes."""

    class_names = {model_class.name for model_class in classes}
    class_lookup = {model_class.name: model_class for model_class in classes}
    relationships: list[ObjectModelRelationship] = []
    seen: set[tuple[str, str, str, str]] = set()
    for model_class in classes:
        for relationship in _build_class_relationships(model_class, class_names, class_lookup):
            key = (
                relationship.source,
                relationship.target,
                relationship.relationship_type,
                relationship.evidence,
            )
            if key in seen:
                continue
            seen.add(key)
            relationships.append(relationship)
    return tuple(relationships)


def _class_inventory_row(model_class: ObjectModelClass) -> dict[str, Any]:
    """Build a concise class-inventory row."""

    return {
        "name": model_class.name,
        "kind": model_class.kind,
        "role": model_class.role,
        "responsibility": model_class.responsibility,
        "module_path": model_class.module_path,
        "anchor": model_class.anchor,
    }


def _relationship_inventory_row(relationship: ObjectModelRelationship) -> dict[str, Any]:
    """Build a concise relationship-inventory row."""

    return {
        "source": relationship.source,
        "target": relationship.target,
        "relationship_type": relationship.relationship_type,
        "evidence": relationship.evidence,
        "anchor": relationship.anchor,
        "confidence": relationship.confidence,
    }


def _pattern_inventory_row(pattern: ObjectModelPatternSignal) -> dict[str, Any]:
    """Build a concise pattern-inventory row."""

    return {
        "class_name": pattern.class_name,
        "pattern": pattern.pattern,
        "status": pattern.status,
        "evidence": ", ".join(pattern.evidence),
    }


def _check_inventory_row(check: ObjectModelCoherenceCheck) -> dict[str, Any]:
    """Build a concise coherence-check row."""

    return {
        "check": check.check,
        "status": check.status,
        "detail": check.detail,
        "symbols": ", ".join(check.symbols),
        "recommendation": check.recommendation,
    }


def _metric_value(value: int | float) -> int | float:
    """Normalize a numeric metric for serialization."""

    if isinstance(value, float):
        return round(value, 1)
    return value


def _build_object_model_metrics(
    classes: Sequence[ObjectModelClass],
    relationships: Sequence[ObjectModelRelationship],
    patterns: Sequence[ObjectModelPatternSignal],
    checks: Sequence[ObjectModelCoherenceCheck],
) -> dict[str, Any]:
    """Build the summary metrics for an object-model report."""

    frozen_dataclasses = sum(1 for model_class in classes if model_class.kind == "frozen_value_object")
    protocols = sum(1 for model_class in classes if model_class.kind == "protocol")
    coherence_score_check = next((check for check in checks if check.check == "coherence_score"), None)
    coherence_score = 100.0
    if coherence_score_check is not None:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)%", coherence_score_check.detail)
        if match:
            coherence_score = float(match.group(1))
    return {
        "class_count": len(classes),
        "frozen_dataclass_count": frozen_dataclasses,
        "protocol_count": protocols,
        "relationship_count": len(relationships),
        "pattern_count": len(patterns),
        "check_count": len(checks),
        "coherence_score": _metric_value(coherence_score),
    }


def _build_recommendations(checks: Sequence[ObjectModelCoherenceCheck]) -> tuple[str, ...]:
    """Build short recommendations from non-pass checks."""

    recommendations: list[str] = []
    for check in checks:
        if check.status == "pass":
            continue
        recommendation = _normalize_text(check.recommendation)
        if recommendation and recommendation not in recommendations:
            recommendations.append(recommendation)
    return tuple(recommendations)


def _build_object_model_summary(
    classes: Sequence[ObjectModelClass],
    relationships: Sequence[ObjectModelRelationship],
    source_files: Sequence[Path],
    scope: str,
) -> str:
    """Build a concise report summary."""

    class_count = len(classes)
    package_count = len({model_class.module_path.rsplit(".", 1)[0] if "." in model_class.module_path else model_class.module_path for model_class in classes})
    return (
        f"Observed {class_count} class(es) across {len(source_files)} file(s), "
        f"{len(relationships)} structural relationship(s), and {package_count} package group(s) in {scope} scope."
    )


def _build_report_data(document: ObjectModelDocument) -> dict[str, Any]:
    """Build the report data payload from an object-model document."""

    return {
        "overview": {
            "source_roots": list(document.source_roots),
            "source_files": list(document.source_files),
            "source_hash": document.source_hash,
            "scope": document.scope,
            "shape": document.shape,
            "summary": document.summary,
        },
        "metrics": {key: _metric_value(value) for key, value in document.metrics.items()},
        "diagrams": [diagram.to_dict() for diagram in document.diagrams],
        "class_inventory": {"rows": [_class_inventory_row(model_class) for model_class in document.classes]},
        "classes": [model_class.to_dict() for model_class in document.classes],
        "relationship_inventory": {"rows": [_relationship_inventory_row(relationship) for relationship in document.relationships]},
        "patterns": {"rows": [_pattern_inventory_row(pattern) for pattern in document.patterns]},
        "checks": {"rows": [_check_inventory_row(check) for check in document.checks]},
        "recommendations": {"items": list(_build_recommendations(document.checks))},
        "notes": {"items": list(document.notes)},
    }


def scan_python_object_model(
    paths: Sequence[Path],
    include_private: bool = False,
    scope: str = "repo",
) -> ObjectModelDocument:
    """Scan Python source files into a deterministic object-model document."""

    if scope not in {"module", "package", "repo"}:
        raise SchemaError(f"unsupported object-model scope: {scope}")

    source_roots = tuple(Path(path) for path in paths)
    if not source_roots:
        raise SchemaError("object-model scanning needs at least one source path")

    source_files = _collect_source_paths(source_roots)
    display_roots = _collect_source_roots(source_roots)
    source_texts = tuple((source_path, source_path.read_text(encoding="utf-8")) for source_path in source_files)
    classes, pattern_signals = _scan_classes(source_files, include_private=include_private)
    relationships = _collect_relationships(classes)

    provisional = {
        "classes": [model_class.to_dict() for model_class in classes],
        "relationships": [relationship.to_dict() for relationship in relationships],
        "patterns": [pattern.to_dict() for pattern in pattern_signals],
    }
    checks = audit_object_model_coherence(provisional)

    provisional_document = {
        "classes": [model_class.to_dict() for model_class in classes],
        "relationships": [relationship.to_dict() for relationship in relationships],
    }
    repo_diagram = ObjectModelDiagram(
        scope="repo",
        name="Repository Overview",
        language="mermaid",
        diagram=render_object_model_class_diagram(provisional_document, scope="repo"),
    )
    package_diagrams = tuple(
        ObjectModelDiagram(
            scope=str(diagram.get("scope", "package")),
            name=str(diagram.get("name", "")),
            language=str(diagram.get("language", "mermaid")),
            diagram=str(diagram.get("diagram", "")),
        )
        for diagram in render_object_model_package_diagrams({**provisional_document, "scope": scope})
    )
    diagrams = (repo_diagram, *package_diagrams)

    document = ObjectModelDocument(
        source_roots=display_roots,
        source_files=tuple(_display_source_path(path) for path in source_files),
        source_hash=_source_hash(source_texts),
        shape="object-model",
        scope=scope,
        summary=_build_object_model_summary(classes, relationships, source_files, scope),
        classes=classes,
        relationships=relationships,
        patterns=pattern_signals,
        checks=checks,
        diagrams=diagrams,
        metrics={},
        notes=(
            "The worker bee extracts the object model deterministically before any model review.",
            "Mermaid class diagrams are rendered from the JSON taxonomy, not from the source again.",
        ),
    )

    metrics = _build_object_model_metrics(classes, relationships, pattern_signals, checks)
    document = ObjectModelDocument(
        source_roots=document.source_roots,
        source_files=document.source_files,
        source_hash=document.source_hash,
        shape=document.shape,
        scope=document.scope,
        summary=document.summary,
        classes=document.classes,
        relationships=document.relationships,
        patterns=document.patterns,
        checks=document.checks,
        diagrams=document.diagrams,
        metrics=metrics,
        notes=document.notes,
    )
    return document


def build_object_model_document_schema(document: ObjectModelDocument, title: str = "") -> dict[str, Any]:
    """Build the JSON Schema contract for an object-model report."""

    resolved_title = title.strip() or f"Object Model: {document.scope}"
    report_data = _build_report_data(document)
    overview_sample = report_data["overview"]
    metrics_sample = report_data["metrics"]
    class_inventory_sample = report_data["class_inventory"]
    classes_sample = report_data["classes"]
    relationship_sample = report_data["relationship_inventory"]
    pattern_sample = report_data["patterns"]
    check_sample = report_data["checks"]
    diagram_sample = report_data["diagrams"]
    recommendations_sample = report_data["recommendations"]
    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": resolved_title,
        "description": "A contract-backed object-model report that inventories classes, relationships, patterns, checks, and Mermaid class diagrams.",
        "type": "object",
        "properties": {
            "overview": {
                "type": "object",
                "properties": {
                    "source_roots": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                    "source_files": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                    "source_hash": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "scope": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "shape": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                    "summary": {"type": "string", "x-markdown": {"kind": "paragraph"}},
                },
                "required": ["source_roots", "source_files", "source_hash", "scope", "shape", "summary"],
                "x-sample": overview_sample,
                "x-markdown": {"kind": "section", "heading": "Overview"},
            },
            "metrics": {
                "type": "object",
                "properties": {
                    "class_count": {"type": "integer", "x-markdown": {"kind": "paragraph", "label": True}},
                    "frozen_dataclass_count": {"type": "integer", "x-markdown": {"kind": "paragraph", "label": True}},
                    "protocol_count": {"type": "integer", "x-markdown": {"kind": "paragraph", "label": True}},
                    "relationship_count": {"type": "integer", "x-markdown": {"kind": "paragraph", "label": True}},
                    "pattern_count": {"type": "integer", "x-markdown": {"kind": "paragraph", "label": True}},
                    "check_count": {"type": "integer", "x-markdown": {"kind": "paragraph", "label": True}},
                    "coherence_score": {"type": "number", "x-markdown": {"kind": "paragraph", "label": True}},
                },
                "required": [
                    "class_count",
                    "frozen_dataclass_count",
                    "protocol_count",
                    "relationship_count",
                    "pattern_count",
                    "check_count",
                    "coherence_score",
                ],
                "x-sample": metrics_sample,
                "x-markdown": {"kind": "section", "heading": "Metrics"},
            },
            "diagrams": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "name": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "language": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "diagram": {"type": "string", "x-markdown": {"kind": "code", "language": "mermaid"}},
                    },
                    "required": ["scope", "name", "language", "diagram"],
                    "x-markdown": {"kind": "section"},
                },
                "x-sample": diagram_sample,
                "x-markdown": {"kind": "section", "heading": "Diagrams", "item_heading": "Diagram"},
            },
            "class_inventory": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "kind": {"type": "string"},
                                "role": {"type": "string"},
                                "responsibility": {"type": "string"},
                                "module_path": {"type": "string"},
                                "anchor": {"type": "string"},
                            },
                            "required": ["name", "kind", "role", "responsibility", "module_path", "anchor"],
                            "x-markdown": {"kind": "table"},
                        },
                        "x-markdown": {"kind": "table"},
                    }
                },
                "required": ["rows"],
                "x-sample": class_inventory_sample,
                "x-markdown": {"kind": "section", "heading": "Class Inventory"},
            },
            "classes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "x-markdown": {"kind": "heading", "level": 3}},
                        "qualified_name": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "module_path": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "source_file": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "anchor": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "kind": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "role": {"type": "string", "x-markdown": {"kind": "paragraph", "label": True}},
                        "responsibility": {"type": "string", "x-markdown": {"kind": "paragraph"}},
                        "bases": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                        "decorators": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                        "fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "annotation": {"type": "string"},
                                    "default_kind": {"type": "string"},
                                    "line_start": {"type": "integer"},
                                    "line_end": {"type": "integer"},
                                },
                                "required": ["name", "annotation", "default_kind", "line_start", "line_end"],
                                "x-markdown": {"kind": "table"},
                            },
                            "x-markdown": {"kind": "section", "heading": "Fields", "item_layout": "table"},
                        },
                        "methods": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "signature": {"type": "string", "x-markdown": {"kind": "code", "language": "python"}},
                                    "decorators": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                                    "calls": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                                    "mutations": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "section", "heading": "State Changes", "item_heading": "Mutation"}},
                                    "returns": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "section", "heading": "Returns", "item_heading": "Return"}},
                                    "line_start": {"type": "integer"},
                                    "line_end": {"type": "integer"},
                                },
                                "required": ["name", "signature", "decorators", "calls", "mutations", "returns", "line_start", "line_end"],
                                "x-markdown": {"kind": "section"},
                            },
                            "x-markdown": {"kind": "section", "heading": "Methods", "item_layout": "table"},
                        },
                        "pattern_signals": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}},
                    },
                    "required": [
                        "name",
                        "qualified_name",
                        "module_path",
                        "source_file",
                        "anchor",
                        "kind",
                        "role",
                        "responsibility",
                        "bases",
                        "decorators",
                        "fields",
                        "methods",
                        "pattern_signals",
                    ],
                    "x-markdown": {"kind": "section"},
                },
                "x-sample": classes_sample,
                "x-markdown": {"kind": "section", "heading": "Classes", "item_heading": "Class"},
            },
            "relationship_inventory": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "target": {"type": "string"},
                                "relationship_type": {"type": "string"},
                                "evidence": {"type": "string"},
                                "anchor": {"type": "string"},
                                "confidence": {"type": "string"},
                            },
                            "required": ["source", "target", "relationship_type", "evidence", "anchor", "confidence"],
                            "x-markdown": {"kind": "table"},
                        },
                        "x-markdown": {"kind": "table"},
                    }
                },
                "required": ["rows"],
                "x-sample": relationship_sample,
                "x-markdown": {"kind": "section", "heading": "Relationship Inventory"},
            },
            "patterns": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "class_name": {"type": "string"},
                                "pattern": {"type": "string"},
                                "status": {"type": "string"},
                                "evidence": {"type": "string"},
                            },
                            "required": ["class_name", "pattern", "status", "evidence"],
                            "x-markdown": {"kind": "table"},
                        },
                        "x-markdown": {"kind": "table"},
                    }
                },
                "required": ["rows"],
                "x-sample": pattern_sample,
                "x-markdown": {"kind": "section", "heading": "Pattern Signals"},
            },
            "checks": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "check": {"type": "string"},
                                "status": {"type": "string"},
                                "detail": {"type": "string"},
                                "symbols": {"type": "string"},
                                "recommendation": {"type": "string"},
                            },
                            "required": ["check", "status", "detail", "symbols", "recommendation"],
                            "x-markdown": {"kind": "table"},
                        },
                        "x-markdown": {"kind": "table"},
                    }
                },
                "required": ["rows"],
                "x-sample": check_sample,
                "x-markdown": {"kind": "section", "heading": "Coherence Checks"},
            },
            "recommendations": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}}
                },
                "required": ["items"],
                "x-sample": recommendations_sample,
                "x-markdown": {"kind": "section", "heading": "Recommendations"},
            },
            "notes": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}, "x-markdown": {"kind": "list"}}
                },
                "required": ["items"],
                "x-sample": list(document.notes),
                "x-markdown": {"kind": "section", "heading": "Notes"},
            },
        },
        "required": [
            "overview",
            "metrics",
            "diagrams",
            "class_inventory",
            "classes",
            "relationship_inventory",
            "patterns",
            "checks",
            "recommendations",
            "notes",
        ],
    }
    validate_schema_node(schema)
    return schema


def build_object_model_report_document(
    document: ObjectModelDocument,
    *,
    title: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the object-model report schema and JSON data."""

    schema = build_object_model_document_schema(document, title=title)
    data = _build_report_data(document)
    validate_instance_against_schema(schema, data)
    return schema, data


def _default_output_path(document: ObjectModelDocument) -> Path:
    """Resolve the default Markdown output path for an object-model report."""

    roots = [Path(root) for root in document.source_roots if str(root).strip()]
    if len(roots) == 1:
        root = roots[0]
        base_name = root.name if root.is_dir() else root.stem
    else:
        base_name = "-".join(root.name if root.is_dir() else root.stem for root in roots) or "object-model"
    slug = re.sub(r"[^0-9A-Za-z_-]+", "-", base_name).strip("-").lower() or "object-model"
    return Path("generated") / f"{slug}.object-model.md"


def write_object_model_document(
    document: ObjectModelDocument,
    *,
    output: str = "",
    title: str = "",
    overwrite: bool = False,
) -> ObjectModelPaths:
    """Write an object-model report to disk."""

    schema, data = build_object_model_report_document(document, title=title)
    markdown = render_markdown_document(schema, data)

    markdown_path = Path(output) if output else _default_output_path(document)
    if not markdown_path.suffix:
        markdown_path = markdown_path.with_suffix(".md")
    paths = resolve_sidecar_paths("", markdown_path)
    artifact = ContractArtifact(schema=schema, data=data, primary_text=markdown)
    write_contract_artifact(paths, artifact, overwrite=overwrite)
    return ObjectModelPaths(schema_path=paths.schema_path, data_path=paths.data_path, primary_path=paths.primary_path)


__all__ = [
    "ObjectModelClass",
    "ObjectModelCoherenceCheck",
    "ObjectModelDiagram",
    "ObjectModelField",
    "ObjectModelMethod",
    "ObjectModelPatternSignal",
    "ObjectModelPaths",
    "ObjectModelRelationship",
    "ObjectModelDocument",
    "build_object_model_document_schema",
    "build_object_model_report_document",
    "scan_python_object_model",
    "write_object_model_document",
]
