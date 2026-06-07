"""Semantic HTML rendering targets for Generation Fabric."""

from .markdown_page import render_markdown_html_document
from .observability_page import render_observability_html_document, write_observability_html_document
from .renderer import render_html_body, render_html_document

__all__ = [
    "render_markdown_html_document",
    "render_observability_html_document",
    "render_html_body",
    "render_html_document",
    "write_observability_html_document",
]
