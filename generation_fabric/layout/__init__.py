"""Layout taxonomy for Generation Fabric.

This package turns ASCII layout sketches into a governed zone taxonomy that the
fabric can validate and render into semantic markup. It is the ASCII-first
counterpart to the Markdown contract layers: a sketch becomes the first
authority-bearing design artifact before any HTML/CSS exists.
"""

from .ascii_sketch import (
    LayoutZone,
    LayoutZoneBounds,
    build_layout_zone_schema,
    build_zone_document,
    parse_ascii_sketch,
)

__all__ = [
    "LayoutZone",
    "LayoutZoneBounds",
    "build_layout_zone_schema",
    "build_zone_document",
    "parse_ascii_sketch",
]
