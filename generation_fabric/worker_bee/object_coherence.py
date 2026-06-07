"""Deterministic object-model coherence checks for worker-bee observability."""

from __future__ import annotations

from typing import Any


def _document_value(document: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dataclass or a plain mapping."""

    if isinstance(document, dict):
        return document.get(key, default)
    return getattr(document, key, default)


def _value(model_object: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dataclass-like object or a mapping."""

    if isinstance(model_object, dict):
        return model_object.get(key, default)
    return getattr(model_object, key, default)


def _class_name(model_class: Any) -> str:
    """Return the observed class name."""

    return str(_value(model_class, "name", ""))


def _class_kind(model_class: Any) -> str:
    """Return the observed class kind."""

    return str(_value(model_class, "kind", "plain_class"))


def _class_fields(model_class: Any) -> tuple[Any, ...]:
    """Return the observed class fields."""

    fields = _value(model_class, "fields", ())
    return tuple(fields) if isinstance(fields, tuple) else tuple(fields or ())


def _class_methods(model_class: Any) -> tuple[Any, ...]:
    """Return the observed class methods."""

    methods = _value(model_class, "methods", ())
    return tuple(methods) if isinstance(methods, tuple) else tuple(methods or ())


def _class_pattern_names(model_class: Any) -> tuple[str, ...]:
    """Return the observed pattern names for a class."""

    patterns = _value(model_class, "pattern_signals", ())
    return tuple(str(pattern) for pattern in patterns if str(pattern).strip())


def _field_names(model_class: Any) -> tuple[str, ...]:
    """Return the observed field names for a class."""

    return tuple(
        str(_value(field, "name", ""))
        for field in _class_fields(model_class)
        if str(_value(field, "name", ""))
    )


def _method_names(model_class: Any) -> tuple[str, ...]:
    """Return the observed method names for a class."""

    return tuple(
        str(_value(method, "name", ""))
        for method in _class_methods(model_class)
        if str(_value(method, "name", ""))
    )


def _decorator_texts(model_class: Any) -> tuple[str, ...]:
    """Return normalized decorator text for a class."""

    decorators = _value(model_class, "decorators", ())
    return tuple(str(decorator) for decorator in decorators if str(decorator).strip())


def _base_names(model_class: Any) -> tuple[str, ...]:
    """Return normalized base-class text for a class."""

    bases = _value(model_class, "bases", ())
    return tuple(str(base) for base in bases if str(base).strip())


def _is_dataclass(model_class: Any) -> bool:
    """Return True when a class looks like a dataclass."""

    name = _class_name(model_class)
    decorators = " ".join(_decorator_texts(model_class)).lower()
    if "dataclass" in decorators:
        return True
    return name.endswith("Artifact") or name.endswith("Proposal") or name.endswith("Session") or name.endswith("Document")


def _is_frozen_dataclass(model_class: Any) -> bool:
    """Return True when a class looks like a frozen dataclass."""

    decorators = " ".join(_decorator_texts(model_class)).lower()
    return "frozen=true" in decorators or "frozen_dataclass" in _class_pattern_names(model_class)


def classify_object_pattern(model_class: Any) -> tuple[Any, ...]:
    """Build pattern signals for one observed class."""

    from .object_model import ObjectModelPatternSignal

    class_name = _class_name(model_class)
    lower_name = class_name.lower()
    field_names = _field_names(model_class)
    method_names = _method_names(model_class)
    bases = _base_names(model_class)
    signals: list[ObjectModelPatternSignal] = []

    if _is_frozen_dataclass(model_class):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="frozen_value_object",
                status="observed",
                evidence=("@dataclass(frozen=True)",),
            )
        )
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="value_object",
                status="observed",
                evidence=("immutable data carrier",),
            )
        )
    elif _is_dataclass(model_class):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="value_object",
                status="observed",
                evidence=("dataclass state carrier",),
            )
        )

    if any("protocol" in base.lower() for base in bases) or lower_name.endswith("protocol"):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="protocol",
                status="observed",
                evidence=tuple(base for base in bases if "protocol" in base.lower()) or ("Protocol base",),
            )
        )

    if any("nodevisitor" in base.lower() for base in bases) or "visitor" in lower_name:
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="visitor",
                status="observed",
                evidence=("ast.NodeVisitor-style traversal",),
            )
        )

    if class_name.endswith(("Error", "Exception")) or any(base.endswith(("Error", "Exception")) for base in bases):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="exception",
                status="observed",
                evidence=("exception inheritance",),
            )
        )

    if class_name.endswith("Paths") and sum(1 for name in field_names if name.endswith("_path")) >= 2:
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="artifact_paths",
                status="observed",
                evidence=tuple(field_names),
            )
        )

    if class_name.endswith(("Artifact", "Bundle")) and {"schema", "data"}.issubset(set(field_names)):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="artifact_bundle",
                status="observed",
                evidence=tuple(field_names),
            )
        )

    if "provider" in lower_name and any(name.startswith(("propose", "provide")) for name in method_names) and "protocol" not in lower_name:
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="provider",
                status="observed",
                evidence=tuple(method_names),
            )
        )

    if class_name.endswith("Session") or ("schema" in lower_name and "path" in lower_name):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="command_session",
                status="observed",
                evidence=tuple(field_names) or tuple(method_names) or ("session state",),
            )
        )

    if "renderer" in lower_name or any(name.startswith("render_") for name in method_names):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="renderer_target",
                status="observed",
                evidence=tuple(method_names) or ("render_ methods",),
            )
        )

    if any(name.startswith("build_") for name in method_names) and any(name.startswith("write_") for name in method_names):
        signals.append(
            ObjectModelPatternSignal(
                class_name=class_name,
                pattern="report_builder",
                status="observed",
                evidence=tuple(method_names),
            )
        )

    return tuple(signals)


def audit_object_model_coherence(document: Any) -> tuple[Any, ...]:
    """Audit an object model for mechanical coherence signals."""

    from .object_model import ObjectModelCoherenceCheck

    classes = tuple(_document_value(document, "classes", ()) or ())
    relationships = tuple(_document_value(document, "relationships", ()) or ())
    checks: list[ObjectModelCoherenceCheck] = []

    def add_check(check: str, status: str, detail: str, symbols: tuple[str, ...], recommendation: str) -> None:
        checks.append(
            ObjectModelCoherenceCheck(
                check=check,
                status=status,
                detail=detail,
                symbols=symbols,
                recommendation=recommendation,
            )
        )

    class_lookup = {
        str(getattr(model_class, "name", "")): model_class
        for model_class in classes
        if str(getattr(model_class, "name", ""))
    }

    value_objects = [
        model_class
        for model_class in classes
        if any(pattern in _class_pattern_names(model_class) for pattern in ("value_object", "frozen_value_object"))
    ]
    non_frozen_value_objects = [
        model_class for model_class in value_objects if _class_kind(model_class) != "frozen_value_object"
    ]
    if non_frozen_value_objects:
        add_check(
            "value_objects_are_frozen",
            "warn",
            "Some value-object signals are attached to mutable classes.",
            tuple(_class_name(model_class) for model_class in non_frozen_value_objects),
            "Prefer frozen dataclasses for pure value objects unless mutation is intentional.",
        )
    else:
        add_check(
            "value_objects_are_frozen",
            "pass",
            "Value-object signals are attached to frozen dataclasses.",
            tuple(_class_name(model_class) for model_class in value_objects),
            "Keep frozen dataclasses as the default carrier for immutable state.",
        )

    protocols = [
        model_class
        for model_class in classes
        if _class_kind(model_class) == "protocol" or any(pattern == "protocol" for pattern in _class_pattern_names(model_class))
    ]
    protocol_failures: list[str] = []
    for protocol in protocols:
        if not _class_methods(protocol):
            protocol_failures.append(_class_name(protocol))
    if protocol_failures:
        add_check(
            "protocols_are_behavioral",
            "warn",
            "One or more protocol classes do not expose behavior.",
            tuple(protocol_failures),
            "Protocols should describe behavior, not just hold fields.",
        )
    else:
        add_check(
            "protocols_are_behavioral",
            "pass",
            "Protocol classes expose method contracts and no excess state.",
            tuple(_class_name(protocol) for protocol in protocols),
            "Keep protocol surfaces narrow and behavior-centric.",
        )

    providers = [model_class for model_class in classes if any(pattern == "provider" for pattern in _class_pattern_names(model_class))]
    provider_names = []
    for provider in providers:
        public_methods = [method for method in _class_methods(provider) if not str(getattr(method, "name", "")).startswith("_")]
        if not public_methods or len(public_methods) > 2:
            provider_names.append(_class_name(provider))
    if provider_names:
        add_check(
            "provider_seams_are_narrow",
            "warn",
            "One or more provider classes expose more than a narrow planning seam.",
            tuple(provider_names),
            "Keep provider adapters focused on proposal assembly and nothing more.",
        )
    else:
        add_check(
            "provider_seams_are_narrow",
            "pass",
            "Provider seams remain narrow and deterministic.",
            tuple(_class_name(provider) for provider in providers),
            "Keep provider adapters free of execution and file-writing concerns.",
        )

    artifact_path_classes = [
        model_class for model_class in classes if any(pattern == "artifact_paths" for pattern in _class_pattern_names(model_class))
    ]
    artifact_field_shapes = {tuple(_field_names(model_class)) for model_class in artifact_path_classes}
    if len(artifact_field_shapes) <= 1:
        add_check(
            "artifact_paths_are_consistent",
            "pass",
            "Artifact-path classes share a compatible sidecar shape.",
            tuple(_class_name(model_class) for model_class in artifact_path_classes),
            "Keep schema/data/path bundles aligned and prefix-compatible.",
        )
    else:
        add_check(
            "artifact_paths_are_consistent",
            "warn",
            "Artifact-path classes vary in shape and should be reviewed for drift.",
            tuple(_class_name(model_class) for model_class in artifact_path_classes),
            "Prefer one sidecar family shape or a clearly documented superset hierarchy.",
        )

    serializer_methods: list[str] = []
    serializer_failures: list[str] = []
    for model_class in classes:
        to_dict_methods = [method for method in _class_methods(model_class) if str(getattr(method, "name", "")) == "to_dict"]
        if not to_dict_methods:
            continue
        serializer_methods.append(_class_name(model_class))
        if not any(
            "to_jsonable_dataclass" in tuple(str(call) for call in getattr(method, "calls", ()))
            for method in to_dict_methods
        ):
            serializer_failures.append(_class_name(model_class))
    if serializer_failures:
        add_check(
            "serialization_is_consistent",
            "warn",
            "Some to_dict methods do not route through the shared dataclass serializer helper.",
            tuple(serializer_failures),
            "Prefer the shared to_jsonable_dataclass helper so serialization stays consistent.",
        )
    else:
        add_check(
            "serialization_is_consistent",
            "pass",
            "Observed to_dict methods use the shared dataclass serializer helper.",
            tuple(serializer_methods),
            "Keep JSON conversion centralized in the shared serialization helper.",
        )

    if classes:
        depths: dict[str, int] = {}

        def depth_for(name: str, seen: set[str] | None = None) -> int:
            if name in depths:
                return depths[name]
            seen = seen or set()
            if name in seen:
                return 0
            seen.add(name)
            model_class = class_lookup.get(name)
            if model_class is None:
                return 0
            bases = [base for base in _base_names(model_class) if base in class_lookup]
            if not bases:
                depths[name] = 1
                return 1
            depth = 1 + max(depth_for(base, seen.copy()) for base in bases)
            depths[name] = depth
            return depth

        max_depth = max(depth_for(_class_name(model_class)) for model_class in classes)
        status = "pass" if max_depth <= 2 else "warn"
        add_check(
            "inheritance_depth_is_shallow",
            status,
            f"Maximum inheritance depth observed: {max_depth}.",
            tuple(_class_name(model_class) for model_class in classes if depth_for(_class_name(model_class)) == max_depth),
            "Prefer shallow inheritance and model variation with composition when possible.",
        )

    composed = [relationship for relationship in relationships if str(getattr(relationship, "relationship_type", "")) == "composes"]
    if composed:
        add_check(
            "composition_has_named_fields",
            "pass",
            "Composition relationships are tied to explicit fields or annotations.",
            tuple(sorted({str(getattr(relationship, "source", "")) for relationship in composed})),
            "Keep composition visible through named fields instead of hidden global state.",
        )
    else:
        add_check(
            "composition_has_named_fields",
            "pass",
            "No composition relationships were observed in the scanned scope.",
            (),
            "Use named fields whenever one object owns or aggregates another.",
        )

    cli_classes = [model_class for model_class in classes if str(getattr(model_class, "module_path", "")).endswith("cli")]
    cli_domain_classes = [model_class for model_class in cli_classes if _class_kind(model_class) not in {"command_session", "plain_class"}]
    if cli_domain_classes:
        add_check(
            "cli_does_not_own_domain_model",
            "warn",
            "The CLI module owns domain-like classes and should stay orchestration-only.",
            tuple(_class_name(model_class) for model_class in cli_domain_classes),
            "Keep command modules thin and move reusable domain logic into package modules.",
        )
    elif cli_classes:
        add_check(
            "cli_does_not_own_domain_model",
            "pass",
            "CLI-owned classes stay in a small session/orchestration role.",
            tuple(_class_name(model_class) for model_class in cli_classes),
            "Keep the CLI as a thin adapter over package modules.",
        )
    else:
        add_check(
            "cli_does_not_own_domain_model",
            "pass",
            "No CLI-owned classes were observed in the scanned scope.",
            (),
            "Keep command logic out of the domain model.",
        )

    renderer_classes = [model_class for model_class in classes if any(pattern == "renderer_target" for pattern in _class_pattern_names(model_class))]
    if len(renderer_classes) > 1:
        add_check(
            "renderer_targets_are_parallel",
            "pass",
            "Renderer targets share a parallel shape across the observed scope.",
            tuple(_class_name(model_class) for model_class in renderer_classes),
            "Keep renderer modules symmetrical so target-specific behavior stays predictable.",
        )
    else:
        add_check(
            "renderer_targets_are_parallel",
            "pass",
            "No parallel renderer surface was observed or only one target was present.",
            tuple(_class_name(model_class) for model_class in renderer_classes),
            "Add renderer targets as sibling modules instead of inflating one renderer with all concerns.",
        )

    report_builders = [model_class for model_class in classes if any(pattern == "report_builder" for pattern in _class_pattern_names(model_class))]
    if report_builders:
        add_check(
            "report_builders_share_lifecycle",
            "pass",
            "Observed report builders use the same build/validate/render/write lifecycle.",
            tuple(_class_name(model_class) for model_class in report_builders),
            "Keep report-building, rendering, and writing responsibilities separate but parallel.",
        )
    else:
        add_check(
            "report_builders_share_lifecycle",
            "pass",
            "No dedicated report-builder classes were observed in the scanned scope.",
            (),
            "Introduce report builders only when the lifecycle is shared enough to justify one.",
        )

    coherence_score = 100.0
    if checks:
        pass_count = sum(1 for check in checks if str(getattr(check, "status", "")).lower() == "pass")
        warn_count = sum(1 for check in checks if str(getattr(check, "status", "")).lower() == "warn")
        fail_count = sum(1 for check in checks if str(getattr(check, "status", "")).lower() == "fail")
        coherence_score = max(0.0, round(((pass_count + warn_count * 0.5) / len(checks)) * 100.0 - fail_count * 10.0, 1))

    add_check(
        "coherence_score",
        "pass" if coherence_score >= 70 else "warn",
        f"Coherence score estimated at {coherence_score:.1f}% across {len(checks)} checks.",
        tuple(_class_name(model_class) for model_class in classes[:5]),
        "Use the score as a directional signal, not a design verdict.",
    )

    return tuple(checks)


__all__ = [
    "audit_object_model_coherence",
    "classify_object_pattern",
]
