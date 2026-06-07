# ASCII-First Governance Layer

This repository treats ASCII layout sketches as first-class design inputs.
The sketch is not decoration. It is the start of the contract pipeline.

## Why ASCII Comes First

ASCII is the easiest shape to capture, review, diff, and regenerate.
That makes it a good source of truth for layout governance because the
structure is visible before any HTML, CSS, or SVG is produced.

The governing principle is simple:

`ASCII sketch -> zone taxonomy -> box model -> renders -> coherence report`

That pipeline keeps the responsibilities separate while still allowing the
artifacts to stay aligned.

## The Contract Surface

The layout path is contract-driven just like the Markdown path.

The important files are:

- `generation_fabric/layout/ascii_sketch.py`: parses the ASCII sketch into a zone taxonomy.
- `generation_fabric/layout/box_model.py`: derives the nested box model from the zone taxonomy.
- `generation_fabric/layout/coherence.py`: audits the sketch, the derived renders, and the box model.
- `generation_fabric/layout/inventory.py`: compares multiple zone taxonomies and reports structural reuse.
- `generation_fabric/layout/visual_inventory.py`: records sketch lineage and visual coherence for the inventory of evolution acceleration.

The worker bee uses these deterministic layers so it can observe, reason about, and regenerate layouts without hand-stitching the downstream artifacts.

## Visual Intent Inventory

The visual-intent inventory is the bridge between page intent and generated assets.
Each inventory item records the lineage needed to keep the artifact set coherent.

At minimum, each row tracks:

- whether an ASCII sketch is required
- the sketch path
- the sketch type
- the sketch status
- the zone taxonomy path
- the box model path
- the visual coherence status

That gives us a compact inventory of the work that has already been governed and the work that still needs attention.

## What The Fabric Produces

For a single sketch brief, the fabric can produce:

- `.ascii.md`
- `.zones.json`
- `.boxes.json`
- `.html`
- `.css`
- `.svg`
- `.coherence.md`

For a set of related pages, the fabric can also produce:

- a segment reuse inventory
- a visual-intent inventory

Those reports are derived artifacts, so they stay in sync with the same deterministic inputs.

## Why This Matters

The point of the layer is coherence:

- the sketch explains the intended structure
- the zone taxonomy anchors the semantic regions
- the box model records layout hierarchy
- the renders project the same contract into HTML, CSS, and SVG
- the inventories track reuse, drift, and sketch lineage

That is what lets the worker bee operate as a smart front door without giving up determinism underneath.

