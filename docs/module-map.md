# Module Map

This repository is organized so the file names tell the implementation story.

## Root Entry

- `json_schema_crud.py`: compatibility wrapper that forwards to the package CLI.

## Package Layout

- `generation_fabric/cli.py`: command parsing and orchestration only.
- `generation_fabric/exceptions.py`: shared exception types.

## Reference Docs

- `docs/compiler-pipeline-roadmap.md`: implementation roadmap for the compiler-style pipeline.
- `docs/unsupported-markdown-features.md`: manual reference for Markdown features that are not yet modeled by the fabric.
- `docs/ascii-first-governance-layer.md`: contract-first ASCII governance note for the sketch, box-model, and inventory pipeline.
- `docs/worker-bee-learning-loop.md`: benchmark-style learning loop for exercising the worker-bee surface against the fabric.
- `docs/worker-bee-code-observation.md`: sequence-diagram shape guidance for observing Python execution paths.
- `docs/worker-bee-code-observation-taxonomy.md`: richer taxonomy and anchor model for architectural code review and forecasted execution flow.
- `docs/worker-bee-migration-strategy.md`: migration strategy for adding a planner/executor worker-bee boundary on top of the fabric.

## Core

- `generation_fabric/core/artifacts.py`: shared sidecar path models and artifact writers for schema, JSON, and rendered outputs.
- `generation_fabric/core/io.py`: atomic JSON/text IO and JSON loading helpers.
- `generation_fabric/core/pointer.py`: JSON Pointer parsing and traversal helpers.
- `generation_fabric/core/serialization.py`: shared JSON-friendly dataclass serialization helper.

## JSON Documents

- `generation_fabric/json_documents/crud.py`: generic JSON tree read/create/update/delete operations.
- `generation_fabric/json_documents/sample.py`: schema-driven JSON sample generation helpers.

## Schema

- `generation_fabric/schema/document.py`: schema creation and combinator attachment.
- `generation_fabric/schema/inference.py`: schema inference from sample JSON.
- `generation_fabric/schema/validation.py`: schema and instance validation.

## Worker Bee

- `generation_fabric/worker_bee/strategy.py`: migration strategy scaffold that describes the worker-bee planner, executor, and verification phases.
- `generation_fabric/worker_bee/planner.py`: deterministic packet builder that turns a brief into a worker-bee generation packet.
- `generation_fabric/worker_bee/prompts.py`: prompt helpers that prepare a provider-facing worker-bee planning prompt.
- `generation_fabric/worker_bee/provider.py`: provider-backed planning proposal helpers and the deterministic local provider adapter.
- `generation_fabric/worker_bee/taxonomy.py`: deterministic source-file scan that extracts the reusable code taxonomy before observation or review.
- `generation_fabric/worker_bee/observation.py`: code-observation helpers that turn Python execution paths into Mermaid sequence-diagram Markdown.
- `generation_fabric/worker_bee/observation_playback.py`: deterministic playback-step extraction for observability HTML.
- `generation_fabric/worker_bee/object_coherence.py`: deterministic object-oriented coherence checks and design-pattern classification for the worker-bee observability layer.
- `generation_fabric/worker_bee/object_diagram.py`: deterministic Mermaid class-diagram rendering from the object-model taxonomy.
- `generation_fabric/worker_bee/object_model.py`: deterministic object-model scan and contract-backed report builder for Python source files.
- `generation_fabric/worker_bee/executor.py`: deterministic executor that turns a packet and sketch prompts into schema, JSON, and Markdown artifacts.
- `generation_fabric/worker_bee/learning.py`: benchmark-style learning loop that exercises the current fabric capabilities and reports coverage.
- `generation_fabric/worker_bee/layout_sketch.py`: maps a brief to a segment and value angle, draws an ASCII layout sketch, and writes the sketch, zone taxonomy, box model, rendered targets, and coherence report.

## Markdown

- `generation_fabric/markdown/renderer.py`: deterministic Markdown rendering from schema plus JSON data.
- `generation_fabric/markdown/registry.py`: registry of supported Markdown contract kinds and their canonical assets.
- `generation_fabric/markdown/contracts.py`: loads canonical Markdown contract assets and scaffolds example files.
- `generation_fabric/markdown/importer.py`: imports legacy Markdown into a schema plus JSON contract.

## Layout

- `generation_fabric/layout/ascii_sketch.py`: parses an ASCII layout sketch into a governed zone taxonomy document and owns the canonical zone contract with `x-html`, `x-css`, and `x-svg` annotations.
- `generation_fabric/layout/box_model.py`: derives the nested box model from a zone taxonomy so the hierarchy stays contract-backed.
- `generation_fabric/layout/coherence.py`: deterministic coherence audit that checks a zone taxonomy and its renders, then emits a Markdown report through the Markdown renderer.
- `generation_fabric/layout/inventory.py`: compares multiple zone taxonomies and writes a layout reuse inventory report.
- `generation_fabric/layout/visual_inventory.py`: records sketch lineage and visual coherence for the inventory of evolution acceleration.
- `generation_fabric/layout/component_intent.py`: extracts component intent (forms, data grids, charts, gauges, widgets) from the ASCII component dialect.
- `generation_fabric/layout/web_contract.py`: folds zones, boxes, and component intent into one normalized web page contract.
- `generation_fabric/layout/web_coherence.py`: component-aware coherence audit that checks the contract and its HTML/CSS/SVG projections.
- `generation_fabric/layout/web_repair.py`: deterministic web-contract repair loop that backfills safe defaults and reports the coherence delta.
- `generation_fabric/layout/web_bundle.py`: end-to-end web bundle orchestration that writes the full contract and render-target sidecar family.

## HTML

- `generation_fabric/html/renderer.py`: deterministic semantic HTML rendering from a schema contract using the `x-html` annotation namespace.
- `generation_fabric/html/markdown_page.py`: Markdown-to-HTML projection that preserves fenced Mermaid blocks and wraps contract reports in a standalone HTML page.
- `generation_fabric/html/observability_page.py`: worker-bee observability wrapper that binds Markdown, JSON sidecars, and playback controls into one HTML projection.
- `generation_fabric/html/web_renderer.py`: component-aware semantic HTML rendering (forms, tables, charts, gauges) from a web page contract.

## CSS

- `generation_fabric/css/renderer.py`: deterministic box-model CSS rendering that projects each zone into an ownership rule using the `x-css` annotation namespace.
- `generation_fabric/css/web_renderer.py`: component-aware CSS rendering that projects the `assets/web_components.json` stylesheet contract plus contract-derived grid placement.

## SVG

- `generation_fabric/svg/renderer.py`: deterministic SVG rendering that draws each zone from its parsed bounds using the `x-svg` annotation namespace.
- `generation_fabric/svg/web_renderer.py`: component-aware SVG blueprint rendering that draws a schematic glyph per component family.

## Example Assets

- `examples/release-notes.schema.json`: canonical schema contract.
- `examples/release-notes.json`: canonical source data.
- `examples/release-notes.md`: canonical rendered Markdown output.
- `examples/docs-showcase.schema.json`: canonical documentation showcase schema.
- `examples/docs-showcase.json`: canonical documentation showcase source data.
- `examples/docs-showcase.md`: canonical rendered documentation showcase output.
- `examples/readme.schema.json`: canonical README contract schema.
- `examples/readme.json`: canonical README source data.
- `examples/readme.md`: canonical rendered README output.
- `examples/workflow-showcase.schema.json`: canonical workflow showcase schema.
- `examples/workflow-showcase.json`: canonical workflow showcase source data.
- `examples/workflow-showcase.md`: canonical rendered workflow showcase output.
- `examples/table-showcase.schema.json`: canonical table showcase schema.
- `examples/table-showcase.json`: canonical table showcase source data.
- `examples/table-showcase.md`: canonical rendered table showcase output.
- `examples/raw-sections-showcase.schema.json`: canonical raw-sections showcase schema.
- `examples/raw-sections-showcase.json`: canonical raw-sections showcase source data.
- `examples/raw-sections-showcase.md`: canonical rendered raw-sections showcase output.
- `examples/value-simulator.ascii.md`: canonical ASCII layout sketch input.
- `examples/value-simulator.zones.json`: canonical zone taxonomy parsed from the sketch.
- `examples/value-simulator.boxes.json`: canonical nested box model derived from the zone taxonomy.
- `examples/value-simulator.html`: canonical semantic HTML rendered from the zone taxonomy.
- `examples/value-simulator.css`: canonical box-model CSS rendered from the zone taxonomy.
- `examples/value-simulator.svg`: canonical SVG drawing rendered from the zone taxonomy.
- `examples/value-simulator.coherence.md`: canonical coherence report rendered from the zone taxonomy.
- `examples/operations-dashboard.ascii.md`: canonical ASCII-to-web sketch using the component dialect.
- `examples/operations-dashboard.components.json`: canonical component intent extracted from the sketch.
- `examples/operations-dashboard.web.json`: canonical web page contract combining zones, boxes, and components.
- `examples/operations-dashboard.html`: canonical component-aware HTML rendered from the web contract.
- `examples/operations-dashboard.css`: canonical component-aware CSS rendered from the web contract.
- `examples/operations-dashboard.svg`: canonical component-aware SVG blueprint rendered from the web contract.
- `examples/operations-dashboard.web-coherence.md`: canonical web coherence report rendered from the web contract.
- `examples/segment-inventory.schema.json`: canonical layout reuse inventory schema.
- `examples/segment-inventory.json`: canonical layout reuse inventory data.
- `examples/segment-inventory.md`: canonical layout reuse inventory across the segment examples.
- `examples/visual-intent-inventory.schema.json`: canonical visual-intent inventory schema.
- `examples/visual-intent-inventory.json`: canonical visual-intent inventory data.
- `examples/visual-intent-inventory.md`: canonical visual-intent inventory for sketch lineage and coherence.
- `examples/layout-zone.schema.json`: canonical zone taxonomy contract with `x-html`, `x-css`, and `x-svg` annotations.

## Scripts

- `scripts/generate_table_showcase.py`: portable Python generator for the table showcase example.
- `scripts/generate_raw_sections_showcase.py`: portable Python generator for the raw sections showcase example.
- `scripts/generate_segment_examples.py`: portable Python generator for the segment layouts, box models, and both inventory reports.

## Tests

- `tests/test_json_schema_crud.py`: CLI-level and end-to-end coverage for schema, inference, scaffolding, and Markdown generation.
- `tests/test_worker_bee_strategy.py`: coverage for the worker-bee migration strategy scaffold.
- `tests/test_worker_bee_planner.py`: coverage for the worker-bee packet planner and CLI command.
- `tests/test_worker_bee_executor.py`: coverage for the worker-bee executor and document generation command.
- `tests/test_worker_bee_object_model.py`: coverage for object-model scanning, report rendering, and the `worker-bee-object-model` command.
- `tests/test_observation_playback.py`: coverage for deterministic worker-bee playback track extraction.
- `tests/test_observability_html.py`: coverage for the observability HTML sidecar and the `worker-bee-observe-html` command.
- `tests/test_layout_ascii.py`: coverage for ASCII sketch parsing, the zone taxonomy contract, HTML rendering, and the `ascii-zones`/`layout-html` commands.
- `tests/test_layout_box_model.py`: coverage for box-model derivation and the `layout-boxes` command.
- `tests/test_layout_inventory.py`: coverage for layout reuse inventory reporting and the `layout-inventory` command.
- `tests/test_layout_targets.py`: coverage for CSS and SVG rendering, the coherence audit, and the `layout-css`/`layout-svg`/`layout-coherence` commands.
- `tests/test_layout_visual_inventory.py`: coverage for visual-intent inventory reporting and the generated example report.
- `tests/test_worker_bee_sketch.py`: coverage for brief-to-sketch profiling, the full sketch bundle, and the `worker-bee-sketch` command.
