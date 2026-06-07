"""Deterministic worker-bee executor for Generation Fabric."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from generation_fabric.core.artifacts import ContractArtifact, SidecarPaths, resolve_sidecar_paths, write_contract_artifact
from generation_fabric.exceptions import SchemaError
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.schema.document import DEFAULT_SCHEMA_DRAFT
from generation_fabric.schema.validation import validate_instance_against_schema, validate_schema_node

from .planner import WorkerBeeGenerationPacket, build_generation_packet, normalize_brief, slugify_text


WorkerBeeDocumentPaths = SidecarPaths


def normalize_sketch_phrase(phrase: str) -> str:
    """Turn a sketch prompt into a clean topic label."""

    text = normalize_brief(phrase).lower()
    text = re.sub(r"^(?:an?\s+)?ascii\s+sketch(?:\s+(?:of|for))?\s+", "", text)
    text = re.sub(r"^(?:an?\s+)?(?:a\s+)?billboard(?:\s+(?:for|about|advertisement|ad|featuring|showing))?\s+", "", text)
    text = re.sub(r"\s+on\s+a\s+billboard$", "", text)
    text = re.sub(r"\s+on\s+billboard$", "", text)
    text = re.sub(r"^(?:an?\s+)?", "", text)
    cleaned = " ".join(text.split()).strip(" ,.;:-")
    if not cleaned:
        return "Concept"
    return " ".join(word.capitalize() for word in cleaned.split())


def extract_sketch_phrases(brief: str) -> tuple[str, ...]:
    """Infer sketch prompts from a natural-language brief."""

    normalized = normalize_brief(brief)
    if not normalized:
        return ()

    phrases: list[str] = []
    first_match = re.search(
        r"one for\s+(.*?)(?:,\s*another one is|,\s*another is|,\s*second is|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if first_match:
        phrases.append(first_match.group(1).strip(" ,.;:-"))

    second_match = re.search(
        r"another(?: one)?(?: is| for)?\s+(.*)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if second_match:
        candidate = second_match.group(1).strip(" ,.;:-")
        if candidate:
            phrases.append(candidate)

    if not phrases:
        parts = [part.strip(" ,.;:-") for part in re.split(r"\s+(?:and|then)\s+", normalized) if part.strip(" ,.;:-")]
        phrases.extend(parts[:2])

    deduped: list[str] = []
    for phrase in phrases:
        if phrase and phrase not in deduped:
            deduped.append(phrase)
    return tuple(deduped)


def billboard_copy_for_topic(topic: str) -> tuple[str, str]:
    """Return a headline and tagline for a billboard sketch topic."""

    lower = topic.lower()
    if any(token in lower for token in ("car", "auto", "vehicle", "salesman", "dealer")):
        return "CAR SALESMAN", "Drive away today"
    if any(token in lower for token in ("restaurant", "diner", "cafe", "food", "menu", "meal")):
        return "RESTAURANT", "Fresh flavors inside"
    if any(token in lower for token in ("coffee", "espresso", "latte")):
        return "COFFEE", "Wake up and smell the roast"
    return topic.upper()[:24], "Big ideas on display"


def fit_text(text: str, width: int) -> str:
    """Fit text into a fixed billboard width."""

    normalized = " ".join(text.split())
    if len(normalized) <= width:
        return normalized
    if width <= 3:
        return normalized[:width]
    return normalized[: width - 3].rstrip() + "..."


def build_ascii_billboard(headline: str, tagline: str) -> str:
    """Build a compact ASCII billboard sketch."""

    content_width = max(24, len(headline), len(tagline))
    headline_text = fit_text(headline, content_width)
    tagline_text = fit_text(tagline, content_width)

    top = "+" + "-" * (content_width + 2) + "+"
    empty = "|" + " " * (content_width + 2) + "|"
    return "\n".join(
        [
            "        ||",
            "        ||",
            top,
            empty,
            f"| {headline_text.center(content_width)} |",
            empty,
            f"| {tagline_text.center(content_width)} |",
            empty,
            top,
            "        ||",
            "        ||",
        ]
    )


def build_sketch_entry(phrase: str, index: int) -> dict[str, Any]:
    """Build one sketch entry from a brief fragment."""

    topic = normalize_sketch_phrase(phrase)
    headline, tagline = billboard_copy_for_topic(topic)
    return {
        "title": f"{topic} Billboard",
        "caption": f"An ASCII billboard concept for {topic.lower()}.",
        "art": build_ascii_billboard(headline, tagline),
    }


def resolve_sketch_phrases(brief: str, explicit_sketches: Sequence[str] | None = None) -> tuple[str, ...]:
    """Resolve sketch prompts from explicit input or from a brief."""

    if explicit_sketches:
        phrases = [normalize_brief(sketch) for sketch in explicit_sketches if normalize_brief(sketch)]
        return tuple(phrases)
    return extract_sketch_phrases(brief)


def build_worker_bee_document_title(
    packet: WorkerBeeGenerationPacket,
    sketches: Sequence[dict[str, Any]],
    title: str = "",
) -> str:
    """Resolve a document title for the generated markdown."""

    explicit = normalize_brief(title)
    if explicit:
        return explicit

    brief_lower = packet.brief.lower()
    if "ascii" in brief_lower or "billboard" in brief_lower:
        return "ASCII Billboard Concepts"
    if sketches:
        return "Generated Sketch Concepts"
    return "Generated Document"


def build_worker_bee_document_schema(
    packet: WorkerBeeGenerationPacket,
    sketches: Sequence[dict[str, Any]],
    title: str = "",
) -> dict[str, Any]:
    """Build the JSON Schema contract for a generated worker-bee document."""

    resolved_title = build_worker_bee_document_title(packet, sketches, title=title)
    schema = {
        "$schema": DEFAULT_SCHEMA_DRAFT,
        "title": resolved_title,
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "x-sample": packet.brief,
                "x-markdown": {"kind": "paragraph"},
            },
            "packet_id": {
                "type": "string",
                "x-sample": packet.packet_id,
                "x-markdown": {"kind": "paragraph", "label": True},
            },
            "focus": {
                "type": "string",
                "x-sample": packet.focus,
                "x-markdown": {"kind": "paragraph", "label": True},
            },
            "sketches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "x-markdown": {"kind": "heading", "level": 3},
                        },
                        "caption": {
                            "type": "string",
                            "x-markdown": {"kind": "paragraph"},
                        },
                        "art": {
                            "type": "string",
                            "x-markdown": {"kind": "code", "language": "text"},
                        },
                    },
                    "required": ["title", "caption", "art"],
                    "x-markdown": {"kind": "section"},
                },
                "x-sample": sketches,
                "x-markdown": {
                    "kind": "section",
                    "heading": "ASCII Sketches",
                },
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
                "x-sample": [
                    "The worker bee keeps the document contract-backed.",
                    "The ASCII sketches are rendered as code blocks for lossless editing.",
                ],
                "x-markdown": {"kind": "list"},
            },
        },
        "required": ["brief", "packet_id", "focus", "sketches", "notes"],
    }
    validate_schema_node(schema)
    return schema


def build_worker_bee_document_data(
    packet: WorkerBeeGenerationPacket,
    sketches: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Build the JSON content for a generated worker-bee document."""

    data = {
        "brief": packet.brief,
        "packet_id": packet.packet_id,
        "focus": packet.focus,
        "sketches": list(sketches),
        "notes": [
            "The worker bee keeps the document contract-backed.",
            "The ASCII sketches are rendered as code blocks for lossless editing.",
            f"Packet summary: {packet.brief_summary}",
        ],
    }
    return data


def build_worker_bee_document(
    brief: str,
    explicit_sketches: Sequence[str] | None = None,
    *,
    base_name: str = "",
    title: str = "",
) -> tuple[WorkerBeeGenerationPacket, dict[str, Any], dict[str, Any], str]:
    """Build the full worker-bee packet, schema, data, and rendered markdown."""

    packet = build_generation_packet(brief, base_name=base_name)
    sketch_phrases = resolve_sketch_phrases(brief, explicit_sketches=explicit_sketches)
    if not sketch_phrases:
        sketch_phrases = (packet.brief,)

    sketches = [build_sketch_entry(phrase, index) for index, phrase in enumerate(sketch_phrases, start=1)]
    schema = build_worker_bee_document_schema(packet, sketches, title=title)
    data = build_worker_bee_document_data(packet, sketches)
    validate_instance_against_schema(schema, data)
    markdown = render_markdown_document(schema, data)
    return packet, schema, data, markdown


def _resolve_output_path(output: str, packet: WorkerBeeGenerationPacket) -> Path:
    """Resolve the markdown output path for the generated document."""

    if output:
        path = Path(output)
        if not path.suffix:
            path = path.with_suffix(".md")
        return path

    base_name = packet.base_name or slugify_text(packet.brief)
    return Path("generated") / f"{base_name}.md"


def _derived_sidecar_paths(markdown_path: Path) -> WorkerBeeDocumentPaths:
    """Derive the schema and JSON sidecar paths for a markdown output."""

    resolved = resolve_sidecar_paths("", markdown_path)
    return WorkerBeeDocumentPaths(
        schema_path=resolved.schema_path,
        data_path=resolved.data_path,
        primary_path=resolved.primary_path,
    )


def write_worker_bee_document(
    brief: str,
    *,
    output: str = "",
    explicit_sketches: Sequence[str] | None = None,
    base_name: str = "",
    title: str = "",
    overwrite: bool = False,
) -> WorkerBeeDocumentPaths:
    """Write a generated worker-bee document to disk."""

    packet, schema, data, markdown = build_worker_bee_document(
        brief,
        explicit_sketches=explicit_sketches,
        base_name=base_name,
        title=title,
    )

    markdown_path = _resolve_output_path(output, packet)
    paths = _derived_sidecar_paths(markdown_path)
    artifact = ContractArtifact(schema=schema, data=data, primary_text=markdown)
    write_contract_artifact(paths, artifact, overwrite=overwrite)
    return paths
