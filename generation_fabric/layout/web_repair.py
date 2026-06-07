"""Deterministic repair loop for the ASCII-to-web pipeline.

This is the contract-layer learning loop from the strategy: instead of
re-rendering blindly, it repairs only the web page contract using safe,
deterministic fixes, then re-audits to show measurable coherence improvement.
Repairs never invent semantic UI; they backfill accessible labels, apply sane
gauge defaults (flagged), demote unsupported types, and de-duplicate ids.
"""

from __future__ import annotations

import copy
from typing import Any

from generation_fabric.exceptions import SchemaError
from generation_fabric.layout.component_intent import SUPPORTED_COMPONENT_TYPES
from generation_fabric.layout.web_coherence import audit_web_coherence
from generation_fabric.layout.web_contract import build_web_page_contract_schema
from generation_fabric.schema.validation import validate_instance_against_schema

GAUGE_DEFAULTS = {"min": "0", "max": "100"}


def _humanize(identifier: str) -> str:
    words = [word for word in identifier.replace("_", " ").replace("-", " ").split() if word]
    return " ".join(word.capitalize() for word in words) if words else identifier


def repair_web_contract(contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply deterministic contract repairs and return (repaired, repairs)."""

    if not isinstance(contract, dict):
        raise SchemaError("web contract repair needs a web page contract")

    repaired = copy.deepcopy(contract)
    repairs: list[str] = []
    seen_ids: dict[str, int] = {}

    for component in repaired.get("components", []) or []:
        component_id = str(component.get("component_id", "") or "component")
        component_type = str(component.get("component_type", "container"))
        label = str(component.get("label", "")) or _humanize(component.get("zone_id", "component"))

        # 1. De-duplicate component ids deterministically.
        if component_id in seen_ids:
            seen_ids[component_id] += 1
            new_id = f"{component_id}-{seen_ids[component_id]}"
            repairs.append(f"renamed duplicate component id '{component_id}' to '{new_id}'")
            component["component_id"] = new_id
        else:
            seen_ids[component_id] = 1

        # 2. Demote unsupported types to a safe container.
        if component_type not in SUPPORTED_COMPONENT_TYPES and component_type != "container":
            repairs.append(f"demoted unsupported component '{component['component_id']}' ({component_type}) to container")
            component["component_type"] = "container"
            component_type = "container"

        # 3. Backfill an accessible label.
        accessibility = component.setdefault("accessibility", {})
        if not accessibility.get("aria_label"):
            accessibility["aria_label"] = label
            repairs.append(f"added aria label to '{component['component_id']}'")

        # 4. Apply sane, flagged gauge defaults (never invents the measured value).
        if component_type in {"gauge", "progress"}:
            measures = component.setdefault("measures", {})
            for key, default in GAUGE_DEFAULTS.items():
                if not measures.get(key):
                    measures[key] = default
                    repairs.append(f"defaulted gauge '{component['component_id']}' {key} to {default}")

    if repairs:
        warnings = repaired.setdefault("warnings", [])
        warnings.append(f"contract repaired: {len(repairs)} deterministic fix(es) applied")

    validate_instance_against_schema(build_web_page_contract_schema(), repaired)
    return repaired, repairs


def run_web_repair_cycle(contract: dict[str, Any]) -> dict[str, Any]:
    """Audit, repair, and re-audit a web contract; report the coherence delta."""

    before = audit_web_coherence(contract)
    repaired, repairs = repair_web_contract(contract)
    after = audit_web_coherence(repaired)

    return {
        "page_id": str(contract.get("page_id", "")),
        "repairs": repairs,
        "before_score": before["score"],
        "after_score": after["score"],
        "improved": after["score"] >= before["score"] and (after["score"] > before["score"] or not repairs),
        "before_passed": before["passed"],
        "after_passed": after["passed"],
        "contract": repaired,
    }
