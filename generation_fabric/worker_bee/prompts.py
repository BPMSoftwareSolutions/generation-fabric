"""Prompt helpers for worker-bee planning."""

from __future__ import annotations

from .strategy import build_default_worker_bee_strategy


def build_worker_bee_planning_prompt(brief: str, base_name: str = "", focus: str = "") -> str:
    """Build a provider-facing prompt for planning a generation packet."""

    strategy = build_default_worker_bee_strategy()
    lines = [
        "You are the worker-bee planner for Generation Fabric.",
        f"North star: {strategy.north_star}",
        "",
        "Constraints:",
        f"- planner/reviewer boundary: {strategy.planner_reviewer_boundary}",
        "- planner proposes only; executor writes files",
        "- output must stay contract-backed and deterministic",
        "",
        "Brief:",
        brief.strip(),
    ]
    if base_name.strip():
        lines.extend(["", f"Base name hint: {base_name.strip()}"])
    if focus.strip():
        lines.extend(["", f"Focus hint: {focus.strip()}"])
    lines.extend(
        [
            "",
            "Return a concise planning proposal with a recommended base name, focus, and reasons.",
        ]
    )
    return "\n".join(lines).strip() + "\n"

