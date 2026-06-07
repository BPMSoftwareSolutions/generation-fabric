"""SVG rendering target for Generation Fabric.

The SVG renderer draws a zone taxonomy contract as positioned rectangles using
the parsed character bounds, dispatching on the ``x-svg`` annotation namespace.
"""

from .renderer import render_svg_document

__all__ = [
    "render_svg_document",
]
