"""CSS rendering target for Generation Fabric.

The CSS renderer projects a zone taxonomy contract into box-model ownership
rules, dispatching on the ``x-css`` annotation namespace.
"""

from .renderer import render_css_document

__all__ = [
    "render_css_document",
]
