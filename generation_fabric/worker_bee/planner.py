"""Deterministic worker-bee packet planner for Generation Fabric."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from typing import Any

from generation_fabric.exceptions import SchemaError

from .strategy import WorkerBeeMigrationStrategy, build_default_worker_bee_strategy

PACKET_TYPE = "generation-fabric.worker-bee.packet"
PACKET_VERSION = "1"
DEFAULT_ARTIFACT_PIPELINE = ("schema", "json", "markdown")
DEFAULT_ROUTING_NOTES = (
    "planner emits packet JSON only",
    "executor must reuse the existing fabric primitives",
    "verification closes the loop before publish",
)
DEFAULT_VERIFICATION_STEPS = (
    "validate the generated schema",
    "generate a JSON sample from the schema",
    "render Markdown from the schema and JSON",
    "compare the rendered output against a golden file when one exists",
)


@dataclass(frozen=True)
class WorkerBeePlanStep:
    """Describe one deterministic step in the worker-bee plan."""

    order: int
    name: str
    purpose: str
    artifact: str


@dataclass(frozen=True)
class WorkerBeeGenerationPacket:
    """Describe a worker-bee packet that can drive the generation fabric."""

    packet_type: str
    packet_version: str
    packet_id: str
    brief: str
    brief_summary: str
    base_name: str
    focus: str
    artifact_pipeline: tuple[str, ...]
    strategy: WorkerBeeMigrationStrategy
    plan_steps: tuple[WorkerBeePlanStep, ...]
    guardrails: tuple[str, ...]
    verification: tuple[str, ...]
    routing_notes: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the packet into a JSON-friendly structure."""

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


def normalize_brief(brief: str) -> str:
    """Normalize whitespace so the packet stays deterministic."""

    return " ".join(brief.split()).strip()


def summarize_brief(brief: str, limit: int = 160) -> str:
    """Create a short summary of the brief for packet metadata."""

    normalized = normalize_brief(brief)
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def slugify_text(text: str) -> str:
    """Convert arbitrary text into a stable lowercase slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "worker-bee"


def infer_focus(brief: str) -> str:
    """Infer the dominant fabric surface from the brief."""

    normalized = normalize_brief(brief).lower()
    scores = {"markdown": 0, "schema": 0, "json": 0}

    for token in ("markdown", "readme", "docs", "documentation", "document", "diagram", "workflow"):
        if token in normalized:
            scores["markdown"] += 1

    for token in ("schema", "contract", "contract-backed", "shape", "structure", "validation"):
        if token in normalized:
            scores["schema"] += 1

    for token in ("json", "payload", "sample", "instance", "data"):
        if token in normalized:
            scores["json"] += 1

    best_score = max(scores.values())
    if best_score == 0:
        return "markdown"

    for focus in ("markdown", "schema", "json"):
        if scores[focus] == best_score:
            return focus

    return "markdown"


def explain_focus(brief: str, focus: str) -> str:
    """Explain why the packet resolved to a particular focus."""

    normalized = normalize_brief(brief).lower()
    if focus == "markdown":
        if any(token in normalized for token in ("markdown", "readme", "docs", "documentation", "document")):
            return "brief references markdown-oriented documentation"
        return "no stronger surface signal was present, so markdown is the default"
    if focus == "schema":
        return "brief references schema, contract, or validation language"
    if focus == "json":
        return "brief references JSON, payload, or sample-data language"
    return "focus was supplied explicitly"


def build_plan_steps(focus: str) -> tuple[WorkerBeePlanStep, ...]:
    """Build the deterministic plan steps that every packet follows."""

    focus_label = focus or "markdown"
    return (
        WorkerBeePlanStep(
            order=1,
            name="capture_brief",
            purpose="preserve the request as an immutable planning input",
            artifact="brief",
        ),
        WorkerBeePlanStep(
            order=2,
            name="resolve_focus",
            purpose=f"select the primary fabric surface for the {focus_label} request",
            artifact=focus_label,
        ),
        WorkerBeePlanStep(
            order=3,
            name="derive_contract",
            purpose="shape the JSON Schema contract that governs the document",
            artifact="schema",
        ),
        WorkerBeePlanStep(
            order=4,
            name="derive_json",
            purpose="prepare the JSON sample that drives deterministic rendering",
            artifact="json",
        ),
        WorkerBeePlanStep(
            order=5,
            name="render_markdown",
            purpose="render the Markdown artifact from the schema and JSON contract",
            artifact="markdown",
        ),
        WorkerBeePlanStep(
            order=6,
            name="validate_round_trip",
            purpose="prove the packet is coherent before any publish step",
            artifact="verification",
        ),
    )


def collect_guardrails(strategy: WorkerBeeMigrationStrategy) -> tuple[str, ...]:
    """Flatten the strategy guardrails into a packet-level guardrail list."""

    ordered_guardrails: list[str] = [
        "planner_proposes_only",
        "planner_does_not_write_files",
        "generated_output_must_remain_contract_backed",
        "do_not_hand_stitch_generated_output",
    ]
    for phase in strategy.phases:
        ordered_guardrails.extend(phase.guardrails)

    deduped: dict[str, None] = {}
    for guardrail in ordered_guardrails:
        deduped.setdefault(guardrail, None)
    return tuple(deduped.keys())


def build_generation_packet(brief: str, base_name: str = "", focus: str = "") -> WorkerBeeGenerationPacket:
    """Build a deterministic worker-bee packet from a natural-language brief."""

    normalized_brief = normalize_brief(brief)
    if not normalized_brief:
        raise SchemaError("worker-bee brief cannot be empty")

    resolved_focus = normalize_brief(focus).lower() if focus else infer_focus(normalized_brief)
    if resolved_focus not in {"markdown", "schema", "json"}:
        raise SchemaError(f"unsupported worker-bee focus: {resolved_focus}")

    strategy = build_default_worker_bee_strategy()
    resolved_base_name = slugify_text(base_name) if base_name else slugify_text(normalized_brief)
    digest_source = "|".join((normalized_brief, resolved_base_name, resolved_focus, strategy.north_star))
    packet_id = f"wb-{resolved_base_name}-{sha256(digest_source.encode('utf-8')).hexdigest()[:12]}"

    metadata = {
        "source": "generation_fabric.worker_bee.planner",
        "brief_length": len(normalized_brief),
        "focus_reason": explain_focus(normalized_brief, resolved_focus),
        "base_name_source": "override" if base_name else "inferred",
        "strategy_north_star": strategy.north_star,
        "planner_reviewer_boundary": strategy.planner_reviewer_boundary,
    }

    return WorkerBeeGenerationPacket(
        packet_type=PACKET_TYPE,
        packet_version=PACKET_VERSION,
        packet_id=packet_id,
        brief=normalized_brief,
        brief_summary=summarize_brief(normalized_brief),
        base_name=resolved_base_name,
        focus=resolved_focus,
        artifact_pipeline=DEFAULT_ARTIFACT_PIPELINE,
        strategy=strategy,
        plan_steps=build_plan_steps(resolved_focus),
        guardrails=collect_guardrails(strategy),
        verification=DEFAULT_VERIFICATION_STEPS,
        routing_notes=DEFAULT_ROUTING_NOTES,
        metadata=metadata,
    )
