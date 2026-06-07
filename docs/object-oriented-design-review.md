# Object-Oriented Design Review

Review date: 2026-06-07

## Purpose

This document reviews how Generation Fabric currently uses object-oriented design and how that design can be elevated for maintainability, reuse, lean implementation, and reduced overlap.

The main conclusion is that this codebase is not trying to be a classical inheritance-heavy OO system. It is a contract-driven compiler pipeline with a mostly functional core, immutable value objects, and a small number of intentional polymorphism points. That is a good fit for the repository's deterministic, schema-backed goals.

The opportunity is not to add classes everywhere. The opportunity is to formalize the repeated concepts that already exist: artifact paths, sidecar writing, report generation, renderer targets, JSON-friendly serialization, and layout document access.

## Current Shape

The current package has roughly this object model:

- 40 Python modules under `generation_fabric/`.
- 284 top-level functions.
- 33 classes.
- 28 dataclasses.
- 27 frozen dataclasses.
- 1 explicit `Protocol`: `WorkerBeePlanningProvider`.
- 2 stateful AST visitors: `_FunctionFlowCollector` and `_TaxonomyFlowCollector`.
- Only a few classes carry behavior beyond serialization or protocol implementation.

That means the current design is best described as:

- Functional transformations for schema, JSON, Markdown, layout, and renderer behavior.
- Immutable dataclasses for domain records and generated artifact summaries.
- Protocol-based dependency injection for worker-bee planning providers.
- Stateful classes only where state is naturally part of traversal, especially AST scanning.

This is mostly clean. The system is lean because data transformations are easy to test, and deterministic functions are easier to reason about than stateful service objects.

## Where OO Is Working Well

### Immutable Value Objects

The best current OO usage is in frozen dataclasses that name real domain concepts:

- `LayoutZoneBounds` and `LayoutZone` in `generation_fabric/layout/ascii_sketch.py`.
- `WorkerBeeGenerationPacket` and `WorkerBeePlanStep` in `generation_fabric/worker_bee/planner.py`.
- `WorkerBeeSurface`, `WorkerBeePhase`, and `WorkerBeeMigrationStrategy` in `generation_fabric/worker_bee/strategy.py`.
- `WorkerBeeLearningCase`, `WorkerBeeLearningCaseResult`, `WorkerBeeLearningRoundResult`, and `WorkerBeeLearningReport` in `generation_fabric/worker_bee/learning.py`.
- `CodeTaxonomyCondition`, `CodeTaxonomySymbol`, `CodeTaxonomyExecutionPath`, and `CodeTaxonomyDocument` in `generation_fabric/worker_bee/taxonomy.py`.

These classes are useful because they give names, invariants, and stable boundaries to structured data without introducing unnecessary mutable state.

### Provider Boundary

`WorkerBeePlanningProvider` in `generation_fabric/worker_bee/provider.py` is the strongest explicit OO abstraction. It uses structural typing through `Protocol`, which lets the code accept future provider adapters without requiring an inheritance hierarchy.

Current flow:

- `propose_worker_bee_plan(...)` accepts a provider.
- `DeterministicWorkerBeePlanningProvider` implements the provider behavior.
- `build_provider_backed_generation_packet(...)` consumes the proposal and keeps execution deterministic.

This is exactly the kind of OO this repository should prefer: small, behavior-focused interfaces around genuine variability.

### AST Visitors

`_FunctionFlowCollector` in `generation_fabric/worker_bee/observation.py` and `_TaxonomyFlowCollector` in `generation_fabric/worker_bee/taxonomy.py` are appropriate class usages. AST traversal naturally needs accumulated state, and Python's `ast.NodeVisitor` is already an OO framework.

This is a good example of using classes where the runtime model calls for them, rather than forcing the entire codebase into class wrappers.

### CLI Is Orchestration

`generation_fabric/cli.py` owns command parsing and orchestration. Most domain behavior lives elsewhere. That keeps the CLI from becoming the domain model, which is healthy.

The file is large, but the dependency direction is mostly correct: CLI functions call core fabric functions; core modules do not depend on the CLI.

## Where The Design Starts To Repeat

### Repeated Artifact Path Classes

Several modules define nearly identical dataclasses for generated sidecar paths:

- `WorkerBeeDocumentPaths` in `generation_fabric/worker_bee/executor.py`.
- `WorkerBeeSketchPaths` in `generation_fabric/worker_bee/layout_sketch.py`.
- `CodeObservationDocumentPaths` in `generation_fabric/worker_bee/observation.py`.
- `CodeTaxonomyDocumentPaths` in `generation_fabric/worker_bee/taxonomy.py`.
- `CoherenceReportPaths` in `generation_fabric/layout/coherence.py`.
- `InventoryReportPaths` in `generation_fabric/layout/inventory.py`.
- `VisualIntentInventoryPaths` in `generation_fabric/layout/visual_inventory.py`.

The repetition is understandable because each workflow grew locally. It is now a maintenance smell because most of these classes express the same concept: a primary artifact plus schema/data sidecars.

Recommended elevation:

```python
@dataclass(frozen=True)
class SidecarPaths:
    schema_path: Path
    data_path: Path
    primary_path: Path

    @property
    def markdown_path(self) -> Path:
        return self.primary_path
```

Then keep specialized subclasses or aliases only when a workflow truly needs extra paths, such as the layout sketch bundle that also writes HTML, CSS, SVG, boxes, and coherence output.

### Repeated Sidecar Write Logic

The following workflows repeat the same steps:

1. Build a schema.
2. Build data.
3. Render or derive a primary artifact.
4. Resolve sidecar paths.
5. Check overwrite safety.
6. Write JSON sidecars.
7. Write text output.
8. Return paths and/or the report.

Examples include:

- `write_worker_bee_document(...)`.
- `write_code_observation_document(...)`.
- `write_layout_coherence_report(...)`.
- `write_layout_inventory_report(...)`.
- `write_visual_intent_inventory_report(...)`.
- `scaffold_markdown_contract(...)`.
- `scaffold_markdown_import(...)`.

Recommended elevation:

```python
@dataclass(frozen=True)
class ContractArtifact:
    schema: dict[str, Any]
    data: Any
    rendered: str


def assert_can_write(paths: Iterable[Path], overwrite: bool) -> None:
    ...


def write_contract_artifact(paths: SidecarPaths, artifact: ContractArtifact, overwrite: bool) -> None:
    ...
```

This would reduce duplicated overwrite checks and make generated artifact writing more uniform.

### Serialization Is Similar But Inconsistent

Several dataclasses implement `to_dict()` with a JSON round trip:

- `WorkerBeeGenerationPacket.to_dict()`.
- `WorkerBeeLearningReport.to_dict()`.
- `PythonFunctionObservation.to_dict()`.
- Code taxonomy dataclass serializers.

`WorkerBeePlanProposal.to_dict()` uses `asdict()` directly.

The JSON round trip is useful because it converts tuples and nested dataclasses into JSON-friendly shapes. The direct `asdict()` version may be fine today, but it creates two serialization habits.

Recommended elevation:

```python
def to_jsonable_dataclass(value: Any) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(value), ensure_ascii=False))
```

Use that helper everywhere a dataclass crosses the JSON artifact boundary. That keeps serialization behavior predictable without introducing a heavyweight base class.

### Renderer Targets Are Parallel But Not Yet Unified

The renderer modules follow a clear pattern:

- `generation_fabric/markdown/renderer.py` uses `x-markdown`.
- `generation_fabric/html/renderer.py` uses `x-html`.
- `generation_fabric/css/renderer.py` uses `x-css`.
- `generation_fabric/svg/renderer.py` uses `x-svg`.

Each module has a metadata accessor and a target-specific render function. This is clean and easy to understand.

The overlap is still small enough that a full renderer class hierarchy would be premature. But if more render targets are added, or if renderer selection becomes dynamic, introduce a protocol instead of a shared base class.

Recommended future shape:

```python
class RenderTarget(Protocol):
    name: str
    annotation_key: str

    def render_document(self, schema: dict[str, Any], data: Any) -> str:
        ...
```

Then a registry can map CLI labels or artifact types to renderers without duplicating command logic.

### Layout Documents Become Raw Dicts Too Early

`LayoutZone` and `LayoutZoneBounds` are good value objects, but `build_zone_document(...)` converts them to dictionaries. Downstream layout code then repeatedly reads raw keys such as `zone_id`, `layout_role`, and `bounds`.

That is workable, because JSON Schema validation is the real contract. But as layout governance grows, raw dict access can spread duplication and make invariants harder to enforce.

Recommended elevation:

```python
@dataclass(frozen=True)
class LayoutZoneDocument:
    page_id: str
    title: str
    zones: tuple[LayoutZone, ...]
    source_sketch: str = ""

    def to_dict(self) -> dict[str, Any]:
        ...
```

The public JSON contract can remain unchanged. The internal code can use a typed facade for zone access, grouping, and validation.

### Report Builders Are Repeating A Template

Coherence, layout inventory, and visual intent inventory all follow a similar report pattern:

- Compute domain inventory or audit data.
- Build a Markdown report schema.
- Build report data.
- Validate the report data.
- Render Markdown.
- Write schema/data/Markdown sidecars.

This suggests a useful OO abstraction:

```python
class ReportBuilder(Protocol):
    report_name: str

    def build_report(self, source: Any) -> dict[str, Any]:
        ...

    def build_document(self, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        ...
```

This should be introduced only after the sidecar writer is extracted. The writer is the lower-risk improvement; a report protocol is useful once there are enough report types to justify dynamic composition.

### CLI Command Registration Is Growing

`generation_fabric/cli.py` has many focused command functions, which is good. The parser setup is the part most likely to become difficult to maintain because every new feature extends one large function.

Recommended elevation:

- Keep command behavior as functions.
- Split parser registration by domain, such as `register_layout_commands(subparsers)` and `register_worker_bee_commands(subparsers)`.
- Add a small `CommandContext` only if repeated argument loading and output writing keeps growing.

This avoids overcorrecting into one class per command while still reducing parser sprawl.

## Recommended Object Model

The ideal shape for this codebase is:

- Value objects for durable concepts.
- Protocols for swappable behavior.
- Pure functions for deterministic transformations.
- Small writer/helper objects for repeated IO workflows.
- Stateful classes only where traversal or lifecycle state is real.

In practical terms:

```text
Schema/JSON/Markdown/Layout
  Pure transformations
  Contract validation
  Small value objects at domain boundaries

Worker Bee
  Provider protocols
  Generation packet value objects
  Deterministic executor functions

Artifacts
  Shared path objects
  Shared sidecar writer
  Shared JSON-friendly serializer

Renderers
  Functional modules today
  Protocol-backed registry only when more dynamic dispatch is needed
```

## Prioritized Elevation Plan

### 1. Add Shared Artifact Path And Write Helpers

Create `generation_fabric/core/artifacts.py` or `generation_fabric/artifacts.py` with:

- `SidecarPaths`.
- `resolve_sidecar_paths(primary_path, schema_suffix=".schema.json", data_suffix=".json")`.
- `assert_can_write(paths, overwrite)`.
- `write_schema_data_text(paths, schema, data, text, overwrite)`.

Then migrate these first:

- `write_layout_coherence_report(...)`.
- `write_layout_inventory_report(...)`.
- `write_worker_bee_document(...)`.

This should reduce duplication with very low behavior risk.

### 2. Add One Dataclass Serialization Helper

Create a shared helper for JSON-friendly dataclass serialization and use it in every `to_dict()` implementation.

This keeps the value object pattern while removing serializer drift.

### 3. Introduce A Layout Zone Document Facade

Keep the external JSON contract as-is, but add an internal `LayoutZoneDocument` value object that can:

- Build from ASCII.
- Build from dict.
- Return zones in reading order.
- Group zones by band.
- Convert back to contract JSON.

This would help `box_model`, `coherence`, `inventory`, CSS, and SVG share the same layout access rules.

### 4. Extract Parser Registration By Domain

Split `build_parser()` into registration helpers:

- `register_schema_commands`.
- `register_json_commands`.
- `register_markdown_commands`.
- `register_layout_commands`.
- `register_worker_bee_commands`.

This is not about OO by itself, but it keeps command growth maintainable and prevents `cli.py` from becoming a large overlap zone.

### 5. Add Renderer Protocol Only When Needed

Do not introduce renderer classes immediately. The current renderer functions are clear.

Add `RenderTarget` and a registry when at least one of these becomes true:

- The CLI needs to choose renderers dynamically.
- Multiple renderers need the same lifecycle.
- Renderers need shared configuration.
- More target namespaces are added beyond Markdown, HTML, CSS, and SVG.

## What To Avoid

- Do not wrap every module in a class.
- Do not create a deep inheritance hierarchy for schemas, renderers, or reports.
- Do not hide deterministic transformations behind mutable service objects.
- Do not replace simple functions with classes unless there is durable state, polymorphism, or repeated lifecycle behavior.
- Do not make JSON Schema dicts disappear entirely. The schema contract is a first-class public format, so raw dicts are still appropriate at the external boundary.

## Success Criteria

The OOP design is improving if:

- Repeated sidecar write code shrinks.
- New report types can reuse artifact writing without copy/paste.
- New providers can be plugged into worker-bee planning without changing packet execution.
- Layout code reads zones through a consistent interface.
- Renderer behavior remains deterministic and easy to test.
- The number of classes grows only when a real concept needs a name or a real variation needs a protocol.

## Summary

Generation Fabric is using object-oriented design in a restrained and mostly healthy way. The codebase does not need more OO ceremony. It needs a few sharper object boundaries around concepts that are already repeated.

The best next step is to extract shared artifact path and sidecar writing helpers, then standardize dataclass serialization. After that, a layout document facade and domain-split CLI registration would give the codebase more reuse and cleaner maintenance without sacrificing the lean functional core that currently makes the pipeline understandable.
