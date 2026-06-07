"""Standalone observability HTML projection for worker-bee reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from generation_fabric.core.io import load_json_file, write_text_file_atomic
from generation_fabric.exceptions import SchemaError
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

from generation_fabric.worker_bee.observation_playback import build_execution_playback_tracks

from .markdown_page import render_markdown_html_document


def _normalize_text(value: Any) -> str:
    """Return a stable human-readable string."""

    return " ".join(str(value).split()).strip()


def _render_playback_panel(playback_data: dict[str, Any]) -> str:
    """Render the execution playback sidebar."""

    tracks = playback_data.get("tracks", [])
    track_count = int(playback_data.get("track_count", len(tracks)) or len(tracks))
    step_count = int(playback_data.get("step_count", 0) or 0)

    return "\n".join(
        [
            '    <div class="panel-header">',
            '      <p class="eyebrow">Execution Playback</p>',
            '      <h1 id="active-execution-title">Loading playback...</h1>',
            '      <p id="active-execution-meta" class="panel-summary">Mermaid diagrams and execution steps will appear here.</p>',
            "    </div>",
            '    <div class="playback-toolbar" role="group" aria-label="Playback controls">',
            '      <button type="button" data-action="previous">Previous</button>',
            '      <button type="button" data-action="play">Play</button>',
            '      <button type="button" data-action="pause">Pause</button>',
            '      <button type="button" data-action="next">Next</button>',
            '      <button type="button" data-action="reset">Reset</button>',
            '      <label class="speed-control">',
            "        Speed",
            '        <select id="playback-speed">',
            '          <option value="0.5">0.5x</option>',
            '          <option value="1" selected>1x</option>',
            '          <option value="1.5">1.5x</option>',
            '          <option value="2">2x</option>',
            "        </select>",
            "      </label>",
            "    </div>",
            '    <section class="active-step-panel">',
            "      <h2>Active Step</h2>",
            '      <dl class="step-details">',
            '        <div><dt>Type</dt><dd id="active-step-type">—</dd></div>',
            '        <div><dt>Label</dt><dd id="active-step-label">—</dd></div>',
            '        <div><dt>Source</dt><dd id="active-step-source">—</dd></div>',
            '        <div><dt>Target</dt><dd id="active-step-target">—</dd></div>',
            '        <div><dt>Message</dt><dd id="active-step-message">—</dd></div>',
            '        <div><dt>Anchor</dt><dd id="active-step-anchor">—</dd></div>',
            '        <div><dt>Duration</dt><dd id="active-step-duration">—</dd></div>',
            "      </dl>",
            "    </section>",
            '    <section class="execution-list-section">',
            f'      <h2>Executions <span class="section-count">({track_count})</span></h2>',
            '      <div class="execution-list" id="execution-list" data-track-count="{}">'.format(track_count),
            "      </div>",
            "    </section>",
            '    <section class="step-list-section">',
            f'      <h2>Steps <span class="section-count">({step_count})</span></h2>',
            '      <ol class="step-list" id="step-list" data-step-count="{}">'.format(step_count),
            "      </ol>",
            "    </section>",
        ]
    )


def render_observability_html_document(
    schema: dict[str, Any],
    data: dict[str, Any],
    markdown: str,
    *,
    title: str = "",
) -> str:
    """Render the observability Markdown report as a standalone HTML page."""

    if not isinstance(schema, dict):
        raise SchemaError("observability HTML rendering needs a schema")
    if not isinstance(data, dict):
        raise SchemaError("observability HTML rendering needs JSON data")

    validate_schema_node(schema)
    validate_instance_against_schema(schema, data)

    tracks = build_execution_playback_tracks(data)
    playback_tracks = [track.to_dict() for track in tracks]
    step_count = sum(len(track.steps) for track in tracks)
    playback_data = {
        "title": _normalize_text(title or schema.get("title") or data.get("overview", {}).get("summary") or "Observability"),
        "track_count": len(playback_tracks),
        "step_count": step_count,
        "tracks": playback_tracks,
    }
    observability_data = {
        "title": playback_data["title"],
        "playback": playback_data,
        "panel_html": _render_playback_panel(playback_data),
    }
    return render_markdown_html_document(
        markdown,
        title=playback_data["title"],
        observability_data=observability_data,
    )


def write_observability_html_document(
    markdown_path: Path | str,
    data_path: Path | str,
    schema_path: Path | str,
    *,
    output: str = "",
    overwrite: bool = False,
) -> Path:
    """Write an observability HTML projection to disk."""

    markdown_path = Path(markdown_path)
    data_path = Path(data_path)
    schema_path = Path(schema_path)

    if not markdown_path.exists():
        raise SchemaError(f"markdown file does not exist: {markdown_path}")
    if not data_path.exists():
        raise SchemaError(f"JSON data file does not exist: {data_path}")
    if not schema_path.exists():
        raise SchemaError(f"schema file does not exist: {schema_path}")

    markdown = markdown_path.read_text(encoding="utf-8")
    data = load_json_file(data_path)
    schema = load_json_file(schema_path)
    html = render_observability_html_document(schema, data, markdown, title=str(schema.get("title", "")))

    output_path = Path(output) if output else markdown_path.with_suffix(".html")
    if not output_path.suffix:
        output_path = output_path.with_suffix(".html")
    if output_path.exists() and not overwrite:
        raise SchemaError(f"refusing to overwrite existing file: {output_path}")

    write_text_file_atomic(output_path, html)
    return output_path


__all__ = ["render_observability_html_document", "write_observability_html_document"]
