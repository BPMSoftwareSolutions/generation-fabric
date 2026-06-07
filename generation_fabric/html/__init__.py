"""Semantic HTML rendering target for Generation Fabric.

The HTML renderer mirrors the Markdown renderer: it walks a JSON Schema contract
plus matching data and emits a derived artifact, dispatching on the ``x-html``
annotation namespace.
"""

from .renderer import render_html_body, render_html_document

__all__ = [
    "render_html_body",
    "render_html_document",
]
