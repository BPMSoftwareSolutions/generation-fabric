"""Playback extraction for worker-bee observability reports."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from generation_fabric.core.serialization import to_jsonable_dataclass


@dataclass(frozen=True)
class ExecutionPlaybackStep:
    """Describe one execution-step interaction for playback."""

    execution_id: str
    step_index: int
    step_type: str
    label: str
    source: str
    target: str
    message: str
    source_anchor: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the step into JSON-friendly data."""

        return to_jsonable_dataclass(self)


@dataclass(frozen=True)
class ExecutionPlaybackTrack:
    """Describe one playback track for an observed execution."""

    execution_id: str
    title: str
    diagram_index: int
    participants: tuple[str, ...]
    steps: tuple[ExecutionPlaybackStep, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the playback track into JSON-friendly data."""

        return to_jsonable_dataclass(self)


def _normalize_text(value: Any) -> str:
    """Return a stable human-readable string."""

    return " ".join(str(value).split()).strip()


def _slugify(value: Any) -> str:
    """Build a stable identifier fragment."""

    text = _normalize_text(value).lower()
    text = re.sub(r"[^0-9a-z]+", "-", text)
    return text.strip("-") or "execution"


def _unique_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    """Return values without duplicates while preserving first-seen order."""

    seen: dict[str, None] = {}
    for value in values:
        value = _normalize_text(value)
        if not value:
            continue
        seen.setdefault(value, None)
    return tuple(seen.keys())


def _step_duration(step_type: str) -> int:
    """Return a small deterministic duration per step type."""

    return {
        "call": 900,
        "data": 850,
        "mutation": 1000,
        "branch": 700,
        "return": 800,
        "idle": 500,
    }.get(step_type, 600)


def _build_step(
    execution_id: str,
    step_index: int,
    step_type: str,
    label: str,
    source: str,
    target: str,
    message: str,
    source_anchor: str,
) -> ExecutionPlaybackStep:
    """Build one playback step with a stable duration."""

    return ExecutionPlaybackStep(
        execution_id=execution_id,
        step_index=step_index,
        step_type=step_type,
        label=_normalize_text(label),
        source=_normalize_text(source),
        target=_normalize_text(target),
        message=_normalize_text(message),
        source_anchor=_normalize_text(source_anchor),
        duration_ms=_step_duration(step_type),
    )


def _first_non_empty(values: Iterable[Any], fallback: str = "") -> str:
    """Return the first non-empty normalized string from a sequence."""

    for value in values:
        text = _normalize_text(value)
        if text:
            return text
    return fallback


def _coerce_step_record(record: dict[str, Any], execution_id: str) -> ExecutionPlaybackStep:
    """Coerce a playback step record into a dataclass."""

    return ExecutionPlaybackStep(
        execution_id=_normalize_text(record.get("execution_id", execution_id)) or execution_id,
        step_index=int(record.get("step_index", 0) or 0),
        step_type=_normalize_text(record.get("step_type", "idle")) or "idle",
        label=_normalize_text(record.get("label", "")),
        source=_normalize_text(record.get("source", "")),
        target=_normalize_text(record.get("target", "")),
        message=_normalize_text(record.get("message", "")),
        source_anchor=_normalize_text(record.get("source_anchor", "")),
        duration_ms=int(record.get("duration_ms", 0) or 0) or _step_duration(_normalize_text(record.get("step_type", "idle")) or "idle"),
    )


def _coerce_track_record(record: dict[str, Any], index: int) -> ExecutionPlaybackTrack:
    """Coerce a playback track record into a dataclass."""

    execution_id = _normalize_text(record.get("execution_id", "")) or f"execution-{index}"
    steps = tuple(
        _coerce_step_record(step, execution_id)
        for step in record.get("steps", [])
        if isinstance(step, dict)
    )
    participants = _unique_preserve_order(record.get("participants", []))
    title = _normalize_text(record.get("title", "")) or execution_id
    diagram_index = int(record.get("diagram_index", index) or index)
    return ExecutionPlaybackTrack(
        execution_id=execution_id,
        title=title,
        diagram_index=diagram_index,
        participants=participants,
        steps=steps,
    )


def _derive_execution_steps(execution: dict[str, Any], index: int, execution_id: str, title: str) -> tuple[ExecutionPlaybackStep, ...]:
    """Derive playback steps from an observed execution record."""

    source_anchor = _normalize_text(execution.get("anchor", ""))
    flow_steps = tuple(_normalize_text(step) for step in execution.get("flow_steps", []) if _normalize_text(step))
    returns = tuple(_normalize_text(value) for value in execution.get("returns", []) if _normalize_text(value))
    participants = _unique_preserve_order(execution.get("participants", []))

    steps: list[ExecutionPlaybackStep] = []
    step_index = 1
    steps.append(_build_step(execution_id, step_index, "call", "invoke", "Caller", title, "invoke", source_anchor))
    step_index += 1

    saw_interaction = False
    saw_idle_marker = False
    pending_final_return = _first_non_empty(returns, "return")

    for flow_step in flow_steps:
        if flow_step.startswith("invoke "):
            continue
        if flow_step.startswith("owner "):
            saw_idle_marker = True
            continue
        if flow_step.startswith("trigger "):
            target = _normalize_text(flow_step.removeprefix("trigger "))
            if not target:
                continue
            saw_interaction = True
            steps.append(_build_step(execution_id, step_index, "call", "trigger", title, target, "trigger", source_anchor))
            step_index += 1
            steps.append(_build_step(execution_id, step_index, "return", "return", target, title, "return", source_anchor))
            step_index += 1
            continue
        if flow_step.startswith("data "):
            payload = _normalize_text(flow_step.removeprefix("data "))
            if ": " in payload:
                target, message = payload.split(": ", 1)
            else:
                target, message = payload, ""
            target = _normalize_text(target)
            if not target:
                continue
            saw_interaction = True
            steps.append(_build_step(execution_id, step_index, "data", "data", title, target, message or "data", source_anchor))
            step_index += 1
            steps.append(_build_step(execution_id, step_index, "return", "return", target, title, "return", source_anchor))
            step_index += 1
            continue
        if flow_step.startswith("mutation "):
            saw_interaction = True
            mutation = _normalize_text(flow_step.removeprefix("mutation "))
            steps.append(_build_step(execution_id, step_index, "mutation", "mutation", title, title, mutation or "mutation", source_anchor))
            step_index += 1
            continue
        if flow_step.startswith("branch: "):
            saw_interaction = True
            branch = _normalize_text(flow_step.removeprefix("branch: "))
            steps.append(_build_step(execution_id, step_index, "branch", "branch", title, title, branch or "branch", source_anchor))
            step_index += 1
            continue
        if flow_step.startswith("return "):
            pending_final_return = _normalize_text(flow_step.removeprefix("return ")) or pending_final_return
            continue

    if saw_idle_marker and not saw_interaction:
        steps.append(_build_step(execution_id, step_index, "idle", "idle", title, title, "no helper calls observed", source_anchor))
        step_index += 1

    steps.append(_build_step(execution_id, step_index, "return", "return", title, "Caller", pending_final_return or "return", source_anchor))
    return tuple(steps)


def _track_from_execution(execution: dict[str, Any], index: int, used_ids: set[str]) -> ExecutionPlaybackTrack:
    """Build one playback track from an observation execution record."""

    name = _normalize_text(execution.get("role") or execution.get("name") or f"Execution {index}")
    execution_id = _slugify(name)
    if execution_id in used_ids:
        execution_id = f"{execution_id}-{index}"
    used_ids.add(execution_id)

    title = _normalize_text(execution.get("role") or execution.get("name") or execution_id)
    participants = _unique_preserve_order(("Caller", title, *execution.get("participants", [])))
    steps = _derive_execution_steps(execution, index, execution_id, title)
    return ExecutionPlaybackTrack(
        execution_id=execution_id,
        title=title,
        diagram_index=index,
        participants=participants,
        steps=steps,
    )


def build_execution_playback_tracks(observation_data: dict[str, Any]) -> tuple[ExecutionPlaybackTrack, ...]:
    """Build deterministic playback tracks from observation JSON."""

    if not isinstance(observation_data, dict):
        return ()

    playback = observation_data.get("playback")
    if isinstance(playback, dict):
        tracks = playback.get("tracks")
        if isinstance(tracks, list) and tracks:
            return tuple(_coerce_track_record(track, index) for index, track in enumerate(tracks, start=1) if isinstance(track, dict))

    executions = observation_data.get("executions", [])
    if not isinstance(executions, list):
        return ()

    used_ids: set[str] = set()
    tracks: list[ExecutionPlaybackTrack] = []
    for index, execution in enumerate(executions, start=1):
        if not isinstance(execution, dict):
            continue
        tracks.append(_track_from_execution(execution, index, used_ids))
    return tuple(tracks)


__all__ = [
    "ExecutionPlaybackStep",
    "ExecutionPlaybackTrack",
    "build_execution_playback_tracks",
]
