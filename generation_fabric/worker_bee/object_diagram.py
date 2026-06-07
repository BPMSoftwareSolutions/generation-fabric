"""Mermaid class-diagram rendering for worker-bee object-model reports."""

from __future__ import annotations

from collections import OrderedDict
import re
from typing import Any


def _document_value(document: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dataclass or a mapping."""

    if isinstance(document, dict):
        return document.get(key, default)
    return getattr(document, key, default)


def _value(model_object: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dataclass-like object or a mapping."""

    if isinstance(model_object, dict):
        return model_object.get(key, default)
    return getattr(model_object, key, default)


def _normalize_text(value: Any) -> str:
    """Render stable diagram text."""

    return " ".join(str(value).split()).strip()


def _sanitize_alias(value: str) -> str:
    """Build a Mermaid-safe alias from text."""

    alias = re.sub(r"[^0-9A-Za-z_]+", "_", value.replace(".", "_").replace("-", "_"))
    alias = re.sub(r"_+", "_", alias).strip("_")
    return alias or "Participant"


def _class_name(model_class: Any) -> str:
    """Return the observed class name."""

    return str(_value(model_class, "name", ""))


def _class_kind(model_class: Any) -> str:
    """Return the observed class kind."""

    return str(_value(model_class, "kind", "plain_class"))


def _module_path(model_class: Any) -> str:
    """Return the observed module path."""

    return str(_value(model_class, "module_path", ""))


def _class_fields(model_class: Any) -> tuple[Any, ...]:
    """Return class fields in declaration order."""

    fields = _value(model_class, "fields", ())
    return tuple(fields) if isinstance(fields, tuple) else tuple(fields or ())


def _class_methods(model_class: Any) -> tuple[Any, ...]:
    """Return class methods in declaration order."""

    methods = _value(model_class, "methods", ())
    return tuple(methods) if isinstance(methods, tuple) else tuple(methods or ())


def _field_annotation(field: Any) -> str:
    """Return the readable field annotation."""

    return _normalize_text(_value(field, "annotation", ""))


def _method_signature(method: Any) -> str:
    """Return a Mermaid-friendly method signature."""

    signature = _normalize_text(_value(method, "signature", ""))
    if signature.startswith("async def "):
        signature = signature.removeprefix("async def ").strip()
    elif signature.startswith("def "):
        signature = signature.removeprefix("def ").strip()
    return signature or _normalize_text(_value(method, "name", ""))


def _class_stereotypes(model_class: Any) -> tuple[str, ...]:
    """Return Mermaid stereotypes for a class."""

    kind = _class_kind(model_class)
    stereotypes: list[str] = []
    if kind == "protocol":
        stereotypes.append("<<Protocol>>")
    elif kind == "visitor":
        stereotypes.append("<<Visitor>>")
    elif kind == "exception":
        stereotypes.append("<<Exception>>")
    elif kind == "artifact_paths":
        stereotypes.append("<<ArtifactPaths>>")
    elif kind == "artifact_bundle":
        stereotypes.append("<<ArtifactBundle>>")
    elif kind == "provider":
        stereotypes.append("<<Provider>>")
    elif kind == "command_session":
        stereotypes.append("<<CommandSession>>")
    elif kind == "report_builder":
        stereotypes.append("<<ReportBuilder>>")
    elif kind == "renderer_target":
        stereotypes.append("<<RendererTarget>>")
    elif kind == "frozen_value_object":
        stereotypes.append("<<frozen dataclass>>")
    elif kind == "value_object":
        stereotypes.append("<<ValueObject>>")
    return tuple(stereotypes)


def _class_block(model_class: Any) -> list[str]:
    """Render one Mermaid class block."""

    alias = _sanitize_alias(_class_name(model_class))
    lines = [f"    class {alias} {{"]
    for stereotype in _class_stereotypes(model_class):
        lines.append(f"        {stereotype}")
    for field in _class_fields(model_class):
        name = _normalize_text(getattr(field, "name", ""))
        annotation = _field_annotation(field)
        if not name:
            continue
        if annotation:
            lines.append(f"        +{name}: {annotation}")
        else:
            lines.append(f"        +{name}")
    for method in _class_methods(model_class):
        name = _normalize_text(getattr(method, "name", ""))
        if not name:
            continue
        lines.append(f"        +{_method_signature(method)}")
    lines.append("    }")
    lines.append(f"    %% {alias}: {_normalize_text(_value(model_class, 'anchor', ''))}")
    return lines


def _relationship_priority(relationship_type: str) -> int:
    """Return a stable styling priority for a relationship type."""

    order = {
        "inherits": 0,
        "implements_protocol": 1,
        "composes": 2,
        "instantiates": 3,
        "returns": 4,
        "accepts": 5,
        "uses_renderer": 6,
        "writes_artifact": 7,
        "serializes": 8,
    }
    return order.get(relationship_type, 99)


def _relationship_style(relationship_type: str) -> str:
    """Return the Mermaid edge style for a relationship."""

    if relationship_type == "inherits":
        return "<|--"
    if relationship_type == "implements_protocol":
        return "<|.."
    if relationship_type == "composes":
        return "*--"
    return "..>"


def _relationship_label(relationship_types: tuple[str, ...]) -> str:
    """Return a concise edge label for one or more relationship types."""

    unique = []
    for relationship_type in relationship_types:
        if relationship_type not in unique:
            unique.append(relationship_type)
    if not unique:
        return ""
    return " / ".join(unique)


def _render_class_diagram_from_records(class_records: tuple[Any, ...], relationship_records: tuple[Any, ...]) -> str:
    """Render a Mermaid class diagram from normalized records."""

    lines = ["classDiagram"]
    if not class_records:
        lines.append("    class EmptyModel {")
        lines.append("        <<empty>>")
        lines.append("    }")
        return "\n".join(lines)

    class_names = {_class_name(model_class) for model_class in class_records}
    aliases = {_class_name(model_class): _sanitize_alias(_class_name(model_class)) for model_class in class_records}

    for model_class in class_records:
        lines.extend(_class_block(model_class))

    edge_groups: OrderedDict[tuple[str, str], list[Any]] = OrderedDict()
    for relationship in relationship_records:
        source = _normalize_text(_value(relationship, "source", ""))
        target = _normalize_text(_value(relationship, "target", ""))
        relationship_type = _normalize_text(_value(relationship, "relationship_type", ""))
        if not source or not target or source not in class_names or target not in class_names:
            continue
        edge_groups.setdefault((source, target), []).append(relationship)

    for (source, target), edges in edge_groups.items():
        ordered_types = sorted(
            (
                _normalize_text(getattr(edge, "relationship_type", ""))
                for edge in edges
                if _normalize_text(getattr(edge, "relationship_type", ""))
            ),
            key=_relationship_priority,
        )
        if not ordered_types:
            continue
        chosen_type = ordered_types[0]
        style = _relationship_style(chosen_type)
        label = _relationship_label(tuple(ordered_types))
        if chosen_type == "inherits":
            left = aliases.get(target, _sanitize_alias(target))
            right = aliases.get(source, _sanitize_alias(source))
        else:
            left = aliases.get(source, _sanitize_alias(source))
            right = aliases.get(target, _sanitize_alias(target))
        edge = f"    {left} {style} {right}"
        if label:
            edge = f"{edge} : {label}"
        lines.append(edge)

    return "\n".join(lines)


def render_object_model_class_diagram(document: dict[str, Any], scope: str = "repo") -> str:
    """Render a Mermaid class diagram from an object-model JSON document."""

    diagrams = document.get("diagrams", []) if isinstance(document, dict) else []
    if scope != "repo" and isinstance(diagrams, list):
        for diagram in diagrams:
            if isinstance(diagram, dict) and _normalize_text(diagram.get("scope", "")) == scope:
                return _normalize_text(diagram.get("diagram", ""))

    classes = tuple(document.get("classes", [])) if isinstance(document, dict) else ()
    relationships = tuple(document.get("relationships", [])) if isinstance(document, dict) else ()
    return _render_class_diagram_from_records(classes, relationships)


def render_object_model_package_diagrams(document: dict[str, Any]) -> tuple[dict[str, str], ...]:
    """Render one Mermaid class diagram per observed package."""

    classes = tuple(document.get("classes", [])) if isinstance(document, dict) else ()
    relationships = tuple(document.get("relationships", [])) if isinstance(document, dict) else ()
    scope = _normalize_text(document.get("scope", "package")) if isinstance(document, dict) else "package"
    packages: OrderedDict[str, list[Any]] = OrderedDict()
    for model_class in classes:
        module_path = _module_path(model_class)
        if scope == "module":
            package_name = module_path or _class_name(model_class)
        else:
            package_name = module_path.rsplit(".", 1)[0] if "." in module_path else module_path
        package_name = package_name or module_path or _class_name(model_class)
        packages.setdefault(package_name, []).append(model_class)

    package_diagrams: list[dict[str, str]] = []
    for package_name, package_classes in packages.items():
        package_class_names = {_class_name(model_class) for model_class in package_classes}
        package_relationships = tuple(
            relationship
            for relationship in relationships
            if _normalize_text(_value(relationship, "source", "")) in package_class_names
            and _normalize_text(_value(relationship, "target", "")) in package_class_names
        )
        package_diagrams.append(
            {
                "scope": scope if scope in {"module", "package"} else "package",
                "name": package_name,
                "language": "mermaid",
                "diagram": _render_class_diagram_from_records(tuple(package_classes), package_relationships),
            }
        )

    return tuple(package_diagrams)


__all__ = [
    "render_object_model_class_diagram",
    "render_object_model_package_diagrams",
]
