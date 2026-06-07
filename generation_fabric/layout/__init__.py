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
    find_zone_list,
    parse_ascii_sketch,
)
from .box_model import build_box_model_document, build_box_model_schema, leaf_boxes

# Note: the coherence audit and the reuse inventory live in
# generation_fabric.layout.coherence / .inventory but are not re-exported here.
# They depend on the css/svg render targets, which depend on this package;
# importing them eagerly would create a circular import. Import them directly
# from their submodules instead.

__all__ = [
    "LayoutZone",
    "LayoutZoneBounds",
    "build_box_model_document",
    "build_box_model_schema",
    "build_layout_zone_schema",
    "build_zone_document",
    "find_zone_list",
    "leaf_boxes",
    "parse_ascii_sketch",
]
