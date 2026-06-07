"""Worker-bee learning loop for exercising Generation Fabric capabilities."""

from __future__ import annotations

from argparse import Namespace
from collections import OrderedDict
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Callable, Iterable
from unittest.mock import patch

from generation_fabric.core.serialization import to_jsonable_dataclass
from generation_fabric.core.io import load_json_file, write_json_file_atomic, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.json_documents.crud import create_node, delete_node, read_node, update_node
from generation_fabric.json_documents.sample import build_json_sample_from_root
from generation_fabric.markdown.contracts import scaffold_markdown_contract
from generation_fabric.markdown.importer import scaffold_markdown_import
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT, attach_combinator, new_schema
from generation_fabric.schema.inference import build_inferred_schema
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

from .executor import build_worker_bee_document, write_worker_bee_document
from .observation import collect_python_function_observations, write_code_observation_document
from .planner import build_generation_packet
from .provider import build_provider_backed_generation_packet, propose_worker_bee_plan
from .object_model import scan_python_object_model, write_object_model_document
from .taxonomy import write_code_taxonomy_document

DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES: tuple[str, ...] = (
    "new",
    "read",
    "create",
    "update",
    "delete",
    "validate",
    "infer",
    "json-read",
    "json-create",
    "json-update",
    "json-delete",
    "json-sample",
    "oneof",
    "anyof",
    "markdown",
    "markdown-contract",
    "markdown-import",
    "interactive",
    "worker-bee-plan",
    "worker-bee-propose",
    "worker-bee-taxonomy",
    "worker-bee-observe",
    "worker-bee-observe-html",
    "worker-bee-object-model",
    "worker-bee-generate",
)

__all__ = [
    "DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES",
    "WorkerBeeLearningCase",
    "WorkerBeeLearningCaseResult",
    "WorkerBeeLearningRoundResult",
    "WorkerBeeLearningReport",
    "build_default_worker_bee_learning_cases",
    "run_worker_bee_learning_loop",
]


@dataclass(frozen=True)
class WorkerBeeLearningCase:
    """Describe one benchmark case in the learning loop."""

    name: str
    capabilities: tuple[str, ...]
    description: str
    exercise: Callable[[Path], "WorkerBeeLearningCaseResult"]


@dataclass(frozen=True)
class WorkerBeeLearningCaseResult:
    """Describe the outcome of one benchmark case."""

    name: str
    capabilities: tuple[str, ...]
    passed: bool
    details: str
    lessons: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerBeeLearningRoundResult:
    """Describe one pass through the learning loop."""

    round_number: int
    artifact_root: str
    case_results: tuple[WorkerBeeLearningCaseResult, ...]
    covered_capabilities: tuple[str, ...]
    coverage_percent: float
    passed: bool


@dataclass(frozen=True)
class WorkerBeeLearningReport:
    """Summarize the worker-bee learning loop."""

    rounds_requested: int
    rounds_run: int
    capabilities: tuple[str, ...]
    rounds: tuple[WorkerBeeLearningRoundResult, ...]
    coverage_percent: float
    passed: bool
    summary: str
    lessons: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report into JSON-friendly data."""

        return to_jsonable_dataclass(self)


def _repo_root() -> Path:
    """Return the repository root."""

    return Path(__file__).resolve().parents[2]


def _unique_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    """Return values without duplicates while preserving their first-seen order."""

    ordered: "OrderedDict[str, None]" = OrderedDict()
    for value in values:
        ordered.setdefault(value, None)
    return tuple(ordered.keys())


def _round_result(
    round_number: int,
    artifact_root: Path,
    case_results: tuple[WorkerBeeLearningCaseResult, ...],
    capabilities: tuple[str, ...],
) -> WorkerBeeLearningRoundResult:
    """Build a round summary from case results."""

    covered = _unique_preserve_order(
        capability
        for result in case_results
        if result.passed
        for capability in result.capabilities
    )
    coverage_percent = (len(covered) / len(capabilities) * 100.0) if capabilities else 100.0
    passed = len(covered) == len(capabilities) and all(result.passed for result in case_results)
    return WorkerBeeLearningRoundResult(
        round_number=round_number,
        artifact_root=str(artifact_root),
        case_results=case_results,
        covered_capabilities=covered,
        coverage_percent=coverage_percent,
        passed=passed,
    )


def _result_from_exception(
    case: WorkerBeeLearningCase,
    exc: Exception,
) -> WorkerBeeLearningCaseResult:
    """Convert a case exception into a failed case result."""

    return WorkerBeeLearningCaseResult(
        name=case.name,
        capabilities=case.capabilities,
        passed=False,
        details=f"{case.description}: {exc}",
        lessons=(f"Fix {case.name} before marking the loop complete.",),
    )


def _run_case(case: WorkerBeeLearningCase, root: Path) -> WorkerBeeLearningCaseResult:
    """Run one benchmark case and normalize unexpected failures."""

    try:
        return case.exercise(root)
    except Exception as exc:  # pragma: no cover - defensive harness
        return _result_from_exception(case, exc)


def _schema_lifecycle_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise schema creation, CRUD, and validation."""

    schema_path = root / "learning-schema.schema.json"
    schema = new_schema(schema_path, "Learning Schema", overwrite=True)
    schema = create_node(schema, "/properties/name", {"type": "string"})
    schema = create_node(schema, "/properties/nickname", {"type": "string"})
    schema = update_node(schema, "/properties/name", {"type": "string", "description": "Primary name"})
    write_json_file_atomic(schema_path, schema)

    loaded = read_node(load_json_file(schema_path), "/properties/name")
    if not isinstance(loaded, dict) or loaded.get("type") != "string":
        raise SchemaError("schema lifecycle read-back failed")

    schema = delete_node(load_json_file(schema_path), "/properties/nickname")
    write_json_file_atomic(schema_path, schema)
    validate_schema_node(schema)
    validate_instance_against_schema(schema, {"name": "Ada"})

    return WorkerBeeLearningCaseResult(
        name="schema_lifecycle",
        capabilities=("new", "read", "create", "update", "delete", "validate"),
        passed=True,
        details="schema CRUD and validation all succeeded",
        lessons=(
            "Schema documents can be created, inspected, mutated, deleted, and validated through the fabric.",
        ),
        artifacts=(str(schema_path),),
    )


def _schema_inference_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise schema inference from sample JSON."""

    sample_path = root / "sample.json"
    sample = [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ]
    write_json_file_atomic(sample_path, sample)

    schema = build_inferred_schema(sample, "Users", "Learning inference case", DEFAULT_SCHEMA_DRAFT)
    validate_schema_node(schema)
    validate_instance_against_schema(schema, sample)

    return WorkerBeeLearningCaseResult(
        name="schema_inference",
        capabilities=("infer",),
        passed=True,
        details="sample JSON produced a valid inferred schema",
        lessons=("Sample JSON can be converted into a contract-backed schema without hand-stitching.",),
        artifacts=(str(sample_path),),
    )


def _json_document_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise generic JSON document CRUD."""

    document_path = root / "document.json"
    document = {"user": {"name": "Ada"}, "items": [1, 2]}
    write_json_file_atomic(document_path, document)

    document = load_json_file(document_path)
    if read_node(document, "/user/name") != "Ada":
        raise SchemaError("JSON read did not return the expected value")

    document = create_node(document, "/user/email", "ada@example.com")
    document = update_node(document, "/items/0", 10)
    document = delete_node(document, "/user/name")
    write_json_file_atomic(document_path, document)

    expected = {"user": {"email": "ada@example.com"}, "items": [10, 2]}
    if document != expected:
        raise SchemaError("JSON CRUD did not produce the expected document")

    return WorkerBeeLearningCaseResult(
        name="json_document_crud",
        capabilities=("json-read", "json-create", "json-update", "json-delete"),
        passed=True,
        details="generic JSON CRUD completed successfully",
        lessons=("JSON documents can be edited atomically with the same pointer semantics as schemas.",),
        artifacts=(str(document_path),),
    )


def _json_sample_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise schema-driven JSON sample generation."""

    repo_root = _repo_root()
    schema_path = repo_root / "examples" / "workflow-showcase.schema.json"
    expected_path = repo_root / "examples" / "workflow-showcase.json"
    generated_path = root / "workflow-showcase.json"

    schema = load_json_file(schema_path)
    sample = build_json_sample_from_root(schema)
    write_json_file_atomic(generated_path, sample)

    expected = load_json_file(expected_path)
    if sample != expected:
        raise SchemaError("schema-driven JSON sample did not match the canonical example")

    return WorkerBeeLearningCaseResult(
        name="json_sample_generation",
        capabilities=("json-sample",),
        passed=True,
        details="schema-driven JSON sample generation matched the canonical example",
        lessons=("The sample generator can derive stable JSON from schema metadata.",),
        artifacts=(str(generated_path),),
    )


def _combinator_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise oneOf and anyOf combinator attachment."""

    schema_path = root / "combinators.schema.json"
    schema = new_schema(schema_path, "Combinators", overwrite=True)
    schema = create_node(schema, "/properties/contact_oneof", {})
    schema = attach_combinator(
        schema,
        "/properties/contact_oneof",
        "oneOf",
        [{"type": "string"}, {"type": "null"}],
    )
    schema = create_node(schema, "/properties/contact_anyof", {})
    schema = attach_combinator(
        schema,
        "/properties/contact_anyof",
        "anyOf",
        [{"type": "string"}, {"type": "number"}],
    )
    write_json_file_atomic(schema_path, schema)
    validate_schema_node(schema)
    validate_instance_against_schema(schema, {"contact_oneof": "Ada", "contact_anyof": "Ada"})

    return WorkerBeeLearningCaseResult(
        name="schema_combinators",
        capabilities=("oneof", "anyof"),
        passed=True,
        details="oneOf and anyOf were attached and validated successfully",
        lessons=("Combinators remain first-class schema mutations in the fabric.",),
        artifacts=(str(schema_path),),
    )


def _markdown_render_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise deterministic Markdown rendering."""

    repo_root = _repo_root()
    schema_path = repo_root / "examples" / "release-notes.schema.json"
    data_path = repo_root / "examples" / "release-notes.json"
    expected_path = repo_root / "examples" / "release-notes.md"
    output_path = root / "release-notes.md"

    schema = load_json_file(schema_path)
    data = load_json_file(data_path)
    rendered = render_markdown_document(schema, data)
    write_text_file_atomic(output_path, rendered)

    expected = expected_path.read_text(encoding="utf-8")
    if rendered != expected:
        raise SchemaError("rendered Markdown did not match the canonical release-notes example")

    return WorkerBeeLearningCaseResult(
        name="markdown_rendering",
        capabilities=("markdown",),
        passed=True,
        details="Markdown rendering matched the canonical example",
        lessons=("The renderer can deterministically project schema-backed JSON into Markdown.",),
        artifacts=(str(output_path),),
    )


def _markdown_contract_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise markdown contract scaffolding."""

    scaffold_dir = root / "contract"
    _, _, schema_path, data_path, markdown_path = scaffold_markdown_contract(
        str(scaffold_dir),
        kind="docs-showcase",
        with_markdown=True,
        overwrite=True,
    )

    repo_root = _repo_root()
    expected_path = repo_root / "examples" / "docs-showcase.md"
    generated = Path(markdown_path).read_text(encoding="utf-8")
    expected = expected_path.read_text(encoding="utf-8")
    if generated != expected:
        raise SchemaError("markdown contract scaffolding did not match the canonical showcase")

    return WorkerBeeLearningCaseResult(
        name="markdown_contract_scaffold",
        capabilities=("markdown-contract",),
        passed=True,
        details="markdown contract scaffolding produced the canonical showcase",
        lessons=("Contract scaffolding can rehydrate canonical Markdown examples on demand.",),
        artifacts=(str(schema_path), str(data_path), str(markdown_path)),
    )


def _markdown_import_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise legacy Markdown import."""

    source_path = root / "import-demo.md"
    source_text = (
        "# Import Demo\n\n"
        "This document exercises the import path.\n\n"
        "- Alpha\n"
        "- Beta\n\n"
        "```text\n"
        "+-----+\n"
        "| A   |\n"
        "+-----+\n"
        "```\n"
    )
    source_path.write_text(source_text, encoding="utf-8")

    target_dir = root / "imported"
    _, _, schema_path, data_path, markdown_path = scaffold_markdown_import(
        str(source_path),
        str(target_dir),
        with_markdown=True,
        overwrite=True,
    )

    generated = Path(markdown_path).read_text(encoding="utf-8")
    if generated != source_text:
        raise SchemaError("imported Markdown did not round-trip exactly for the demo document")

    return WorkerBeeLearningCaseResult(
        name="markdown_import",
        capabilities=("markdown-import",),
        passed=True,
        details="legacy Markdown was imported and rendered back losslessly",
        lessons=("Legacy Markdown can be converted into schema and JSON without hand-stitching.",),
        artifacts=(str(schema_path), str(data_path), str(markdown_path)),
    )


def _interactive_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise the interactive shell."""

    from generation_fabric.cli import interactive_command

    schema_path = root / "interactive.schema.json"
    stdout = StringIO()
    stderr = StringIO()
    with patch(
        "builtins.input",
        side_effect=[
            f"new {schema_path} Shell",
            'create /properties/flag {"type":"boolean"}',
            "validate",
            "exit",
        ],
    ), redirect_stdout(stdout), redirect_stderr(stderr):
        code = interactive_command(Namespace(file=""))

    if code != 0:
        raise SchemaError(f"interactive shell returned a non-zero exit code: {code}")

    schema = load_json_file(schema_path)
    if schema.get("properties", {}).get("flag", {}).get("type") != "boolean":
        raise SchemaError("interactive shell did not create the expected schema property")

    return WorkerBeeLearningCaseResult(
        name="interactive_shell",
        capabilities=("interactive",),
        passed=True,
        details="interactive shell created and validated a schema successfully",
        lessons=("The shell remains a quick-edit front door for schema experiments.",),
        artifacts=(str(schema_path),),
    )


def _worker_bee_plan_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise worker-bee packet planning."""

    packet = build_generation_packet("Create a README for the generation fabric")
    packet_dict = packet.to_dict()
    if packet_dict["focus"] != "markdown":
        raise SchemaError("worker-bee plan did not resolve markdown focus")

    packet_path = root / "readme.packet.json"
    write_json_file_atomic(packet_path, packet_dict)

    return WorkerBeeLearningCaseResult(
        name="worker_bee_plan",
        capabilities=("worker-bee-plan",),
        passed=True,
        details="worker-bee packet planning succeeded",
        lessons=("Briefs can be converted into a deterministic generation packet.",),
        artifacts=(str(packet_path),),
    )


def _worker_bee_provider_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise provider-backed planning before packet creation."""

    brief = "Create a schema-backed markdown status page with a portable planning seam."
    proposal = propose_worker_bee_plan(brief)
    packet = build_provider_backed_generation_packet(brief)

    if proposal.provider_name != "local-deterministic":
        raise SchemaError("provider-backed planning did not use the expected local provider")
    if packet.metadata.get("planner_mode") != "provider-backed":
        raise SchemaError("provider-backed planning did not annotate the packet metadata")
    if packet.metadata.get("provider", {}).get("provider_name") != proposal.provider_name:
        raise SchemaError("provider-backed packet metadata does not match the proposal")

    proposal_path = root / "provider-proposal.json"
    packet_path = root / "provider-packet.json"
    write_json_file_atomic(proposal_path, proposal.to_dict())
    write_json_file_atomic(packet_path, packet.to_dict())

    return WorkerBeeLearningCaseResult(
        name="worker_bee_provider_planning",
        capabilities=("worker-bee-propose",),
        passed=True,
        details="provider-backed planning produced a proposal and packet successfully",
        lessons=("The planner seam can be backed by a provider without changing the downstream fabric contract.",),
        artifacts=(str(proposal_path), str(packet_path)),
    )


def _worker_bee_observation_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise code observation and sequence-diagram rendering."""

    repo_root = _repo_root()
    source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"
    markdown_path = root / "planner-observation.md"

    observations = collect_python_function_observations(source_path)
    paths = write_code_observation_document(
        str(source_path),
        output=str(markdown_path),
        overwrite=True,
    )
    markdown = Path(paths.markdown_path).read_text(encoding="utf-8")
    schema = load_json_file(paths.schema_path)
    data = load_json_file(paths.data_path)

    if not observations:
        raise SchemaError("code observation did not capture any execution paths")
    if data.get("overview", {}).get("shape") != "sequence-diagram":
        raise SchemaError("code observation did not preserve the requested shape")
    if "sequenceDiagram" not in markdown or "Code Inventory" not in markdown:
        raise SchemaError("code observation did not render a Mermaid sequence diagram")
    if schema.get("title") != "Code Observation: planner":
        raise SchemaError("code observation did not build the expected contract title")

    return WorkerBeeLearningCaseResult(
        name="worker_bee_code_observation",
        capabilities=("worker-bee-observe", "worker-bee-taxonomy"),
        passed=True,
        details="code observation produced a contract-backed sequence diagram document",
        lessons=("The worker bee can observe Python execution paths and turn them into Mermaid-backed Markdown.",),
        artifacts=(str(paths.schema_path), str(paths.data_path), str(paths.markdown_path)),
    )


def _worker_bee_observability_html_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise observability HTML projection from a generated observation report."""

    from generation_fabric.html.observability_page import write_observability_html_document

    repo_root = _repo_root()
    source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"
    markdown_path = root / "planner-observation.md"

    paths = write_code_observation_document(
        str(source_path),
        output=str(markdown_path),
        overwrite=True,
    )
    html_path = write_observability_html_document(
        paths.markdown_path,
        paths.data_path,
        paths.schema_path,
        output=str(Path(paths.markdown_path).with_suffix(".html")),
        overwrite=True,
    )

    html = Path(html_path).read_text(encoding="utf-8")
    if "<!DOCTYPE html>" not in html or "observability-playback-data" not in html:
        raise SchemaError("observability HTML projection did not render a standalone HTML page")
    if "execution-panel" not in html or "mermaid" not in html:
        raise SchemaError("observability HTML projection did not include playback controls or Mermaid containers")

    return WorkerBeeLearningCaseResult(
        name="worker_bee_observability_html",
        capabilities=("worker-bee-observe-html",),
        passed=True,
        details="observability HTML projection rendered a standalone playback page",
        lessons=("The Markdown report can now project into an interactive HTML observability surface.",),
        artifacts=(str(paths.schema_path), str(paths.data_path), str(paths.markdown_path), str(html_path)),
    )


def _worker_bee_object_model_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise object-model scanning and class-diagram rendering."""

    repo_root = _repo_root()
    source_path = repo_root / "generation_fabric" / "worker_bee" / "provider.py"
    markdown_path = root / "provider.object-model.md"

    document = scan_python_object_model([source_path], scope="module")
    paths = write_object_model_document(
        document,
        output=str(markdown_path),
        title="Object Model: provider",
        overwrite=True,
    )
    markdown = Path(paths.markdown_path).read_text(encoding="utf-8")
    schema = load_json_file(paths.schema_path)
    data = load_json_file(paths.data_path)

    if not document.classes:
        raise SchemaError("object-model scan did not capture any classes")
    if not data.get("class_inventory"):
        raise SchemaError("object-model report did not build a class inventory")
    if not data.get("relationship_inventory"):
        raise SchemaError("object-model report did not build a relationship inventory")
    if "classDiagram" not in markdown or "Coherence Checks" not in markdown:
        raise SchemaError("object-model report did not render a Mermaid class diagram")
    if schema.get("title") != "Object Model: provider":
        raise SchemaError("object-model report did not build the expected contract title")

    return WorkerBeeLearningCaseResult(
        name="worker_bee_object_model",
        capabilities=("worker-bee-object-model",),
        passed=True,
        details="object-model scanning produced a contract-backed class diagram report",
        lessons=("The worker bee can observe object structure and render a class diagram from the taxonomy.",),
        artifacts=(str(paths.schema_path), str(paths.data_path), str(paths.markdown_path)),
    )


def _worker_bee_taxonomy_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise deterministic taxonomy extraction for a Python source file."""

    repo_root = _repo_root()
    source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"
    taxonomy_path = root / "planner-taxonomy.json"

    paths = write_code_taxonomy_document(
        str(source_path),
        output=str(taxonomy_path),
        overwrite=True,
    )
    taxonomy = load_json_file(paths.data_path)

    if taxonomy.get("shape") != "code-taxonomy":
        raise SchemaError("code taxonomy did not preserve the expected shape")
    if taxonomy.get("module_path") != "generation_fabric.worker_bee.planner":
        raise SchemaError("code taxonomy did not capture the expected module path")
    if not str(taxonomy.get("source_hash", "")).startswith("sha256:"):
        raise SchemaError("code taxonomy did not capture a stable source hash")
    if not any(symbol.get("name") == "build_generation_packet" for symbol in taxonomy.get("symbols", [])):
        raise SchemaError("code taxonomy did not capture the expected planner symbol")
    if not any(path.get("conditions") for path in taxonomy.get("execution_paths", [])):
        raise SchemaError("code taxonomy did not capture any conditions")

    return WorkerBeeLearningCaseResult(
        name="worker_bee_taxonomy",
        capabilities=("worker-bee-taxonomy",),
        passed=True,
        details="deterministic taxonomy extraction succeeded",
        lessons=("The worker bee can precompute a reusable taxonomy before any review pass.",),
        artifacts=(str(paths.schema_path), str(paths.data_path)),
    )


def _worker_bee_generate_case(root: Path) -> WorkerBeeLearningCaseResult:
    """Exercise worker-bee document generation."""

    brief = (
        "Generate me a markdown file that has two ASCII sketches, "
        "one for an ASCII sketch of a billboard for a car salesman, "
        "another one is an ASCII sketch for a restaurant advertisement on a billboard"
    )
    markdown_path = root / "billboards.md"
    paths = write_worker_bee_document(brief, output=str(markdown_path), overwrite=True)
    markdown = Path(paths.markdown_path).read_text(encoding="utf-8")

    if "CAR SALESMAN" not in markdown or "RESTAURANT" not in markdown:
        raise SchemaError("worker-bee document generation did not produce the expected billboard content")

    packet, schema, data, rendered = build_worker_bee_document(brief)
    if schema.get("title") != "ASCII Billboard Concepts" or len(data.get("sketches", [])) != 2:
        raise SchemaError("worker-bee document generation did not build the expected contract")
    if rendered != markdown:
        raise SchemaError("written Markdown did not match the in-memory render")

    return WorkerBeeLearningCaseResult(
        name="worker_bee_generate",
        capabilities=("worker-bee-generate",),
        passed=True,
        details="worker-bee document generation produced contract-backed Markdown output",
        lessons=("The worker bee can now write schema, JSON, and Markdown artifacts in one pass.",),
        artifacts=(str(paths.schema_path), str(paths.data_path), str(paths.markdown_path)),
    )


def build_default_worker_bee_learning_cases() -> tuple[WorkerBeeLearningCase, ...]:
    """Build the default learning catalog for the worker bee."""

    return (
        WorkerBeeLearningCase(
            name="schema_lifecycle",
            capabilities=("new", "read", "create", "update", "delete", "validate"),
            description="Exercise the schema CRUD surface and validation boundary",
            exercise=_schema_lifecycle_case,
        ),
        WorkerBeeLearningCase(
            name="schema_inference",
            capabilities=("infer",),
            description="Infer a schema from sample JSON",
            exercise=_schema_inference_case,
        ),
        WorkerBeeLearningCase(
            name="json_document_crud",
            capabilities=("json-read", "json-create", "json-update", "json-delete"),
            description="Exercise the generic JSON document CRUD surface",
            exercise=_json_document_case,
        ),
        WorkerBeeLearningCase(
            name="json_sample_generation",
            capabilities=("json-sample",),
            description="Generate a JSON sample from schema metadata",
            exercise=_json_sample_case,
        ),
        WorkerBeeLearningCase(
            name="schema_combinators",
            capabilities=("oneof", "anyof"),
            description="Attach and validate schema combinators",
            exercise=_combinator_case,
        ),
        WorkerBeeLearningCase(
            name="markdown_rendering",
            capabilities=("markdown",),
            description="Render canonical Markdown from a schema and JSON contract",
            exercise=_markdown_render_case,
        ),
        WorkerBeeLearningCase(
            name="markdown_contract_scaffold",
            capabilities=("markdown-contract",),
            description="Scaffold a canonical markdown contract",
            exercise=_markdown_contract_case,
        ),
        WorkerBeeLearningCase(
            name="markdown_import",
            capabilities=("markdown-import",),
            description="Import a legacy Markdown document and render it back",
            exercise=_markdown_import_case,
        ),
        WorkerBeeLearningCase(
            name="interactive_shell",
            capabilities=("interactive",),
            description="Exercise the interactive shell front door",
            exercise=_interactive_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_plan",
            capabilities=("worker-bee-plan",),
            description="Build a deterministic worker-bee planning packet",
            exercise=_worker_bee_plan_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_provider_planning",
            capabilities=("worker-bee-propose",),
            description="Build a provider-backed worker-bee planning proposal and packet",
            exercise=_worker_bee_provider_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_taxonomy",
            capabilities=("worker-bee-taxonomy",),
            description="Extract a deterministic taxonomy from a Python source file",
            exercise=_worker_bee_taxonomy_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_code_observation",
            capabilities=("worker-bee-observe",),
            description="Observe a Python file and render sequence diagrams",
            exercise=_worker_bee_observation_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_observability_html",
            capabilities=("worker-bee-observe-html",),
            description="Project an observation report into standalone HTML",
            exercise=_worker_bee_observability_html_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_object_model",
            capabilities=("worker-bee-object-model",),
            description="Observe Python classes and render an object-model class diagram",
            exercise=_worker_bee_object_model_case,
        ),
        WorkerBeeLearningCase(
            name="worker_bee_generate",
            capabilities=("worker-bee-generate",),
            description="Generate schema, JSON, and Markdown from a brief",
            exercise=_worker_bee_generate_case,
        ),
    )


def run_worker_bee_learning_loop(rounds: int = 1) -> WorkerBeeLearningReport:
    """Run the worker-bee capability learning loop."""

    if rounds < 1:
        raise SchemaError("rounds must be at least 1")

    capabilities = DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES
    cases = build_default_worker_bee_learning_cases()
    round_results: list[WorkerBeeLearningRoundResult] = []

    for round_number in range(1, rounds + 1):
        root = Path(mkdtemp(prefix="generation-fabric-worker-bee-"))
        case_results = tuple(_run_case(case, root) for case in cases)
        round_result = _round_result(round_number, root, case_results, capabilities)
        round_results.append(round_result)
        if round_result.passed:
            break

    final_round = round_results[-1]
    lessons = _unique_preserve_order(
        lesson
        for round_result in round_results
        for case_result in round_result.case_results
        for lesson in case_result.lessons
    )
    summary = (
        f"worker bee learned {len(final_round.covered_capabilities)} of {len(capabilities)} capabilities "
        f"across {len(round_results)} round(s)"
    )

    return WorkerBeeLearningReport(
        rounds_requested=rounds,
        rounds_run=len(round_results),
        capabilities=capabilities,
        rounds=tuple(round_results),
        coverage_percent=final_round.coverage_percent,
        passed=final_round.passed,
        summary=summary,
        lessons=lessons,
        metadata={
            "source": "generation_fabric.worker_bee.learning",
            "default_case_count": len(cases),
            "artifact_roots": [round_result.artifact_root for round_result in round_results],
        },
    )
