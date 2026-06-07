"""End-to-end web bundle orchestration for the ASCII-to-web pipeline.

Given a zone taxonomy document, this builds the component intent, the web page
contract, and every render target, then writes the full sidecar family. It keeps
the CLI thin and gives the worker bee a single entry point for producing an
observable web design object from one sketch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.css.web_renderer import render_web_css_document
from generation_fabric.exceptions import SchemaError
from generation_fabric.html.web_renderer import render_web_html_document
from generation_fabric.layout.component_intent import build_component_intent_document
from generation_fabric.layout.web_coherence import build_web_coherence_report_document, audit_web_coherence
from generation_fabric.layout.web_contract import build_web_page_contract
from generation_fabric.markdown.renderer import render_markdown_document
from generation_fabric.svg.web_renderer import render_web_svg_document


@dataclass(frozen=True)
class WebBundlePaths:
    """Describe the files produced by the web bundle writer."""

    components_path: Path
    contract_path: Path
    html_path: Path
    css_path: Path
    svg_path: Path
    coherence_path: Path


@dataclass(frozen=True)
class WebBundle:
    """Hold every artifact derived from one zone taxonomy document."""

    page_id: str
    components: dict[str, Any]
    contract: dict[str, Any]
    html: str
    css: str
    svg: str
    coherence_report: dict[str, Any]
    coherence_markdown: str


def build_web_bundle(zones_document: dict[str, Any]) -> WebBundle:
    """Build the component intent, contract, render targets, and coherence report."""

    components = build_component_intent_document(zones_document)
    contract = build_web_page_contract(zones_document, components)
    html = render_web_html_document(contract)
    css = render_web_css_document(contract)
    svg = render_web_svg_document(contract)
    report = audit_web_coherence(contract)
    report_schema, report_data = build_web_coherence_report_document(report)
    coherence_markdown = render_markdown_document(report_schema, report_data)
    return WebBundle(
        page_id=str(contract.get("page_id", "page")),
        components=components,
        contract=contract,
        html=html,
        css=css,
        svg=svg,
        coherence_report=report,
        coherence_markdown=coherence_markdown,
    )


def write_web_bundle(
    zones_document: dict[str, Any],
    *,
    output_dir: str = "",
    base_name: str = "",
    overwrite: bool = False,
) -> tuple[WebBundlePaths, WebBundle]:
    """Build and write the full web bundle for a zone taxonomy document."""

    bundle = build_web_bundle(zones_document)
    target_dir = Path(output_dir) if output_dir else Path("generated")
    base = base_name or bundle.page_id

    paths = WebBundlePaths(
        components_path=target_dir / f"{base}.components.json",
        contract_path=target_dir / f"{base}.web.json",
        html_path=target_dir / f"{base}.html",
        css_path=target_dir / f"{base}.css",
        svg_path=target_dir / f"{base}.svg",
        coherence_path=target_dir / f"{base}.web-coherence.md",
    )

    for target in (
        paths.components_path,
        paths.contract_path,
        paths.html_path,
        paths.css_path,
        paths.svg_path,
        paths.coherence_path,
    ):
        if target.exists() and not overwrite:
            raise SchemaError(f"refusing to overwrite existing file: {target}")

    write_json_file_atomic(paths.components_path, bundle.components)
    write_json_file_atomic(paths.contract_path, bundle.contract)
    write_text_file_atomic(paths.html_path, bundle.html)
    write_text_file_atomic(paths.css_path, bundle.css)
    write_text_file_atomic(paths.svg_path, bundle.svg)
    write_text_file_atomic(paths.coherence_path, bundle.coherence_markdown)
    return paths, bundle
