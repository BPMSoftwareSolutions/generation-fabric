"""Worker-bee ASCII layout sketch generator for Generation Fabric.

This extends the deterministic ASCII billboard generator into a full layout
pathway: a brief is mapped to a market segment and value angle, drawn as an
aligned ASCII sketch, parsed into the governed zone taxonomy, and rendered to
every layout target (HTML, CSS, SVG) plus a coherence report. The worker bee
contributes the segment/value judgment; deterministic code draws the boxes and
writes the files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.css.renderer import render_css_document
from generation_fabric.exceptions import SchemaError
from generation_fabric.html.renderer import render_html_document
from generation_fabric.layout.ascii_sketch import build_layout_zone_schema, build_zone_document
from generation_fabric.layout.coherence import audit_layout_coherence, build_coherence_report_document
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.svg.renderer import render_svg_document

WIDTH = 62
DIVIDER = 24
INNER = WIDTH - 2
LEFT_W = DIVIDER - 1
RIGHT_W = WIDTH - DIVIDER - 2

# Segments mirror the LOC 5x5 GTM model: id, keywords, label, supporting detail.
SEGMENTS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("enterprise-engineering", ("enterprise", "engineering org", "large team", "delivery org"),
     "Enterprise engineering", "Delivery acceleration, governance, scale"),
    ("msp-consultancy", ("msp", "consultancy", "consulting", "agency", "multi-client", "many clients"),
     "MSP / consultancy", "Repeatable delivery leverage across clients"),
    ("ai-platform", ("ai platform", "platform team", "agent", "compute", "model ops", "drift"),
     "AI platform team", "Agent governance and compute discipline"),
    ("academy-training", ("academy", "training", "learning program", "workforce", "upskill"),
     "Academy / training", "Skill proof and learning evidence"),
    ("investor-partner", ("investor", "partner", "fund", "revenue motion", "market evidence"),
     "Investor / partner", "Market evidence and revenue motions"),
)

# Value angles mirror the Learning Loop Economics value levers.
VALUE_ANGLES: tuple[tuple[str, tuple[str, ...], str, str, str], ...] = (
    ("cost-avoidance", ("cost", "savings", "avoid", "budget", "spend reduction"),
     "Estimate the value of avoided repeated work", "Inputs + annual value opportunity",
     "Savings levers, assumptions, finance framing"),
    ("delivery-acceleration", ("delivery", "accelerat", "speed", "timeline", "faster", "throughput"),
     "Estimate the value of faster governed delivery", "Inputs + delivery time saved",
     "Timeline compression, learning reuse"),
    ("governance-efficiency", ("governance", "audit", "compliance", "review", "control", "auditab"),
     "Estimate the value of governed, auditable delivery", "Inputs + governance overhead saved",
     "Boundaries, evidence, review, auditability"),
    ("compute-discipline", ("compute", "model waste", "retry", "token", "inference cost"),
     "Estimate the value of disciplined compute", "Inputs + wasted compute reduced",
     "Repeated cognition, model waste, retries"),
    ("training-leverage", ("training", "academy", "skill", "learning loop", "upskill"),
     "Estimate the value of training leverage", "Inputs + skill growth modeled",
     "Learning loops, skill evidence, outcomes"),
)


@dataclass(frozen=True)
class WorkerBeeSketchPaths:
    """Describe the files produced by the worker-bee sketch pathway."""

    sketch_path: Path
    zones_path: Path
    html_path: Path
    css_path: Path
    svg_path: Path
    coherence_path: Path


@dataclass(frozen=True)
class WorkerBeeSketchBundle:
    """Hold every artifact derived from a single brief."""

    page_id: str
    segment_label: str
    value_angle_label: str
    sketch: str
    document: dict[str, Any]
    html: str
    css: str
    svg: str
    coherence_markdown: str
    report: dict[str, Any]


def _fit(text: Any, width: int) -> str:
    """Fit text into a fixed cell width without breaking the box border."""

    normalized = " ".join(str(text).split())
    if len(normalized) <= width:
        return normalized
    if width <= 3:
        return normalized[:width]
    return normalized[: width - 3].rstrip() + "..."


def _full_row(text: str) -> str:
    """Render a full-width content row."""

    return "│" + (" " + _fit(text, INNER - 1)).ljust(INNER) + "│"


def _split_row(left: str, right: str) -> str:
    """Render a two-column content row."""

    return (
        "│"
        + (" " + _fit(left, LEFT_W - 1)).ljust(LEFT_W)
        + "│"
        + (" " + _fit(right, RIGHT_W - 1)).ljust(RIGHT_W)
        + "│"
    )


def _divider(left_char: str, right_char: str, junction: str | None) -> str:
    """Render a horizontal divider, optionally with an interior junction."""

    if junction is None:
        return left_char + "─" * INNER + right_char
    return left_char + "─" * LEFT_W + junction + "─" * RIGHT_W + right_char


def _is_split(band: tuple) -> bool:
    """Return True when a band is split into two columns."""

    return band[0] == "split"


def render_box(bands: list[tuple]) -> str:
    """Render an aligned ASCII box from a list of full/split band specs."""

    lines: list[str] = [_divider("┌", "┐", "┬" if _is_split(bands[0]) else None)]
    for index, band in enumerate(bands):
        if band[0] == "full":
            lines.append(_full_row(band[1]))
        else:
            left_lines, right_lines = band[1], band[2]
            row_count = max(len(left_lines), len(right_lines))
            for row in range(row_count):
                left = left_lines[row] if row < len(left_lines) else ""
                right = right_lines[row] if row < len(right_lines) else ""
                lines.append(_split_row(left, right))

        if index < len(bands) - 1:
            above = _is_split(band)
            below = _is_split(bands[index + 1])
            if above and below:
                junction: str | None = "┼"
            elif below:
                junction = "┬"
            elif above:
                junction = "┴"
            else:
                junction = None
            lines.append(_divider("├", "┤", junction))
        else:
            lines.append(_divider("└", "┘", "┴" if _is_split(band) else None))
    return "\n".join(lines) + "\n"


def _match(brief_lower: str, table: tuple) -> tuple:
    """Pick the first table entry whose keywords appear in the brief."""

    for entry in table:
        if any(keyword in brief_lower for keyword in entry[1]):
            return entry
    return table[0]


def infer_sketch_profile(brief: str) -> tuple[tuple, tuple]:
    """Infer the (segment, value angle) profile from a brief."""

    brief_lower = brief.lower()
    return _match(brief_lower, SEGMENTS), _match(brief_lower, VALUE_ANGLES)


def build_segment_value_sketch(brief: str) -> tuple[str, str, str, str, str]:
    """Build an ASCII sketch and identity fields from a brief."""

    segment, value_angle = infer_sketch_profile(brief)
    segment_id, _segment_keywords, segment_label, segment_detail = segment
    value_id, _value_keywords, value_headline, value_simulator_detail, formula_detail = value_angle

    bands: list[tuple] = [
        ("full", f"HERO: {value_headline}"),
        ("split", [f"SEGMENT: {segment_label}", segment_detail], ["VALUE SIMULATOR", value_simulator_detail]),
        ("full", f"FORMULA + ASSUMPTIONS: {formula_detail}"),
        ("split", ["MARKET CITATIONS"], ["LOC EVIDENCE CHAIN"]),
        ("full", "LIMITATIONS + BOOK TRANSFORMATION REVIEW"),
    ]
    sketch = render_box(bands)
    page_id = f"{segment_id}.{value_id}"
    return sketch, page_id, value_headline, segment_label, value_headline


def build_worker_bee_sketch(brief: str, *, page_id: str = "", title: str = "") -> WorkerBeeSketchBundle:
    """Build every layout artifact from a single brief."""

    if not brief.strip():
        raise SchemaError("worker-bee sketch brief cannot be empty")

    sketch, inferred_page_id, inferred_title, segment_label, value_headline = build_segment_value_sketch(brief)
    resolved_page_id = page_id or inferred_page_id
    resolved_title = title or inferred_title

    document = build_zone_document(sketch, page_id=resolved_page_id, title=resolved_title)
    schema = build_layout_zone_schema()

    html = render_html_document(schema, document)
    css = render_css_document(schema, document)
    svg = render_svg_document(schema, document)

    report = audit_layout_coherence(schema, document)
    report_schema, report_data = build_coherence_report_document(report)
    coherence_markdown = render_markdown_document(report_schema, report_data)

    return WorkerBeeSketchBundle(
        page_id=document["page_id"],
        segment_label=segment_label,
        value_angle_label=value_headline,
        sketch=sketch,
        document=document,
        html=html,
        css=css,
        svg=svg,
        coherence_markdown=coherence_markdown,
        report=report,
    )


def write_worker_bee_sketch(
    brief: str,
    *,
    output_dir: str = "",
    base_name: str = "",
    page_id: str = "",
    title: str = "",
    overwrite: bool = False,
) -> tuple[WorkerBeeSketchPaths, WorkerBeeSketchBundle]:
    """Build and write the full worker-bee sketch artifact set."""

    bundle = build_worker_bee_sketch(brief, page_id=page_id, title=title)

    target_dir = Path(output_dir) if output_dir else Path("generated")
    base = base_name or bundle.page_id

    paths = WorkerBeeSketchPaths(
        sketch_path=target_dir / f"{base}.ascii.md",
        zones_path=target_dir / f"{base}.zones.json",
        html_path=target_dir / f"{base}.html",
        css_path=target_dir / f"{base}.css",
        svg_path=target_dir / f"{base}.svg",
        coherence_path=target_dir / f"{base}.coherence.md",
    )

    for target in (
        paths.sketch_path,
        paths.zones_path,
        paths.html_path,
        paths.css_path,
        paths.svg_path,
        paths.coherence_path,
    ):
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_text_file_atomic(paths.sketch_path, bundle.sketch)
    write_json_file_atomic(paths.zones_path, bundle.document)
    write_text_file_atomic(paths.html_path, bundle.html)
    write_text_file_atomic(paths.css_path, bundle.css)
    write_text_file_atomic(paths.svg_path, bundle.svg)
    write_text_file_atomic(paths.coherence_path, bundle.coherence_markdown)

    return paths, bundle
