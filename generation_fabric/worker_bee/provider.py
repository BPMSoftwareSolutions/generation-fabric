"""Provider-backed worker-bee planning helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from generation_fabric.core.serialization import to_jsonable_dataclass
from generation_fabric.exceptions import SchemaError

from .planner import build_generation_packet, infer_focus, normalize_brief, slugify_text, summarize_brief
from .prompts import build_worker_bee_planning_prompt


@dataclass(frozen=True)
class WorkerBeePlanProposal:
    """Describe a provider-backed planning proposal."""

    provider_name: str
    brief: str
    brief_summary: str
    base_name: str
    focus: str
    prompt: str
    rationale: str
    recommendations: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proposal into JSON-friendly data."""

        return to_jsonable_dataclass(self)


class WorkerBeePlanningProvider(Protocol):
    """Protocol for a provider that proposes a worker-bee plan."""

    provider_name: str

    def propose(self, brief: str, base_name: str = "", focus: str = "") -> WorkerBeePlanProposal:
        """Return a planning proposal for a brief."""


@dataclass(frozen=True)
class DeterministicWorkerBeePlanningProvider:
    """Deterministic provider used until a real model adapter is plugged in."""

    provider_name: str = "local-deterministic"

    def propose(self, brief: str, base_name: str = "", focus: str = "") -> WorkerBeePlanProposal:
        """Return a deterministic planning proposal for a brief."""

        normalized_brief = normalize_brief(brief)
        if not normalized_brief:
            raise SchemaError("worker-bee brief cannot be empty")

        resolved_base_name = slugify_text(base_name) if base_name else slugify_text(normalized_brief)
        resolved_focus = normalize_brief(focus).lower() if focus else infer_focus(normalized_brief)
        prompt = build_worker_bee_planning_prompt(normalized_brief, base_name=resolved_base_name, focus=resolved_focus)
        rationale = (
            "A deterministic local provider preserves the contract boundary while keeping the "
            "planner seam ready for a future Gemini or other model adapter."
        )
        recommendations = (
            "reuse the existing fabric primitives",
            "validate the proposal before execution",
            "keep generated output contract-backed",
        )
        metadata = {
            "provider_kind": "local",
            "provider_mode": "deterministic",
            "brief_length": len(normalized_brief),
        }
        return WorkerBeePlanProposal(
            provider_name=self.provider_name,
            brief=normalized_brief,
            brief_summary=summarize_brief(normalized_brief),
            base_name=resolved_base_name,
            focus=resolved_focus,
            prompt=prompt,
            rationale=rationale,
            recommendations=recommendations,
            metadata=metadata,
        )


def propose_worker_bee_plan(
    brief: str,
    provider: WorkerBeePlanningProvider | None = None,
    *,
    base_name: str = "",
    focus: str = "",
) -> WorkerBeePlanProposal:
    """Produce a provider-backed planning proposal."""

    active_provider = provider or DeterministicWorkerBeePlanningProvider()
    return active_provider.propose(brief, base_name=base_name, focus=focus)


def build_provider_backed_generation_packet(
    brief: str,
    provider: WorkerBeePlanningProvider | None = None,
    *,
    base_name: str = "",
    focus: str = "",
):
    """Build a generation packet by first passing through a provider proposal."""

    proposal = propose_worker_bee_plan(brief, provider=provider, base_name=base_name, focus=focus)
    packet = build_generation_packet(brief, base_name=proposal.base_name, focus=proposal.focus)
    packet.metadata["planner_mode"] = "provider-backed"
    packet.metadata["provider"] = proposal.to_dict()
    return packet


__all__ = [
    "DeterministicWorkerBeePlanningProvider",
    "WorkerBeePlanProposal",
    "WorkerBeePlanningProvider",
    "build_provider_backed_generation_packet",
    "propose_worker_bee_plan",
]
