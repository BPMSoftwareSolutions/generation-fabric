# ASCII-To-Web Implementation Strategy

Review date: 2026-06-07

## Purpose

This document defines an implementation strategy for converting ASCII sketches into contract-driven HTML, CSS, and SVG outputs. The goal is to let Generation Fabric accept lightweight ASCII wireframes for web pages, forms, containers, grids, data grids, charts, gauges, gadgets, widgets, and other interface capabilities, then transform those sketches into coherent render artifacts.

The intended result is not just "ASCII to markup." The intended result is a first-class web design contract:

```text
ASCII sketch
-> zone taxonomy
-> component intent taxonomy
-> box model
-> web page contract
-> HTML/CSS/SVG render targets
-> coherence report
```

## Current Foundation

Generation Fabric already has a useful layout pipeline:

- `generation_fabric/layout/ascii_sketch.py` parses an ASCII sketch into layout zones.
- `generation_fabric/layout/box_model.py` derives a flat page and surface model from those zones.
- `generation_fabric/html/renderer.py` renders semantic HTML from `x-html` contract data.
- `generation_fabric/css/renderer.py` renders CSS from `x-css` contract data.
- `generation_fabric/svg/renderer.py` renders SVG wireframes from `x-svg` contract data.
- `generation_fabric/layout/coherence.py` audits whether the zones, box model, HTML, CSS, and SVG stay aligned.
- `generation_fabric/worker_bee/layout_sketch.py` can generate sketch artifacts and sidecars such as `.ascii.md`, `.zones.json`, `.boxes.json`, `.html`, `.css`, `.svg`, and `.coherence.md`.

This gives us a strong starting point. The current implementation understands page bands, columns, layout roles, zone labels, and target annotations. What it does not yet fully understand is component intent: whether a zone is a form, data grid, chart, gauge, search widget, filter panel, card stack, metric tile, modal, or navigation surface.

## Design Goal

The next elevation is to make ASCII sketches express web component intent without making the sketches difficult to write. ASCII remains the fast visual input. A normalized JSON contract becomes the durable source of truth. HTML, CSS, and SVG remain derived outputs.

The design should preserve these principles:

- ASCII is a sketch language, not the final contract.
- The component contract is the source of truth for rendering.
- HTML, CSS, and SVG are deterministic projections of the same contract.
- Unknown or ambiguous components should produce warnings, not silent hallucinated UI.
- Every rendered component should retain traceability back to its ASCII zone and source line evidence.
- Coherence checks should verify structure, layout ownership, accessibility, data bindings, and visual representation.

## Proposed Pipeline

```text
+------------------+
| ASCII sketch     |
+--------+---------+
         |
         v
+------------------+
| Zone taxonomy    |
| zones + bounds   |
+--------+---------+
         |
         v
+--------------------------+
| Component intent layer   |
| forms, grids, charts,    |
| gauges, widgets          |
+--------+-----------------+
         |
         v
+--------------------------+
| Web page contract        |
| zones, boxes, components,|
| data, targets, a11y      |
+--------+-----------------+
         |
         +--------------------+
         |                    |
         v                    v
+------------------+  +------------------+
| HTML renderer    |  | SVG renderer     |
+--------+---------+  +--------+---------+
         |                    |
         v                    v
+------------------+  +------------------+
| CSS renderer     |  | SVG blueprint    |
+--------+---------+  +--------+---------+
         |                    |
         +---------+----------+
                   v
          +------------------+
          | Coherence audit  |
          +------------------+
```

## ASCII Sketch Dialect

The ASCII dialect should remain compact, but it needs conventions for component hints and data intent.

Example:

```text
+----------------------------------------------------------+
| OPERATIONS CONSOLE [page]                                |
| h1: Operations Console                                   |
+--------------------------+-------------------------------+
| FILTERS [form]           | DELIVERY HEALTH [gauge]       |
| fields: date,status,team | value: delivery_health        |
| action: apply_filters    | min: 0 max: 100               |
+--------------------------+-------------------------------+
| RUNS [data_grid]                                         |
| data: runs[]                                             |
| columns: id,status,owner,duration,started_at             |
| action: open_run                                         |
+--------------------------+-------------------------------+
| TREND [chart_line]       | INCIDENTS [chart_bar]         |
| x: day y: success_rate   | x: severity y: count          |
+--------------------------+-------------------------------+
```

Recommended notation:

- `LABEL [component_type]` declares the component intent for a zone.
- `key: value` declares structured component metadata.
- `fields: name,email,status` declares form controls.
- `columns: id,name,status` declares table or data grid columns.
- `data: runs[]` declares a collection binding.
- `value: delivery_health` declares a metric or gauge binding.
- `x: day y: success_rate` declares chart axes.
- `action: submit` or `action: open_run` declares user actions.
- `variant: primary`, `variant: compact`, or `variant: danger` declares styling intent.

The parser should continue to work for plain labels. If a sketch has no component hints, the system can map zones to generic sections, cards, or containers.

## Component Intent Taxonomy

Add a component intent layer after zone parsing and before rendering. A good first module name would be:

```text
generation_fabric/layout/component_intent.py
```

The core contract can use these shapes:

```text
ComponentIntentDocument
ComponentIntent
ComponentField
ComponentColumn
ComponentAction
ComponentDataBinding
ComponentVisualization
ComponentState
ComponentRelationship
```

Suggested `ComponentIntent` fields:

```json
{
  "component_id": "component-runs",
  "zone_id": "zone-runs",
  "component_type": "data_grid",
  "label": "Runs",
  "role": "region",
  "variant": "dense",
  "data": {
    "source": "runs[]",
    "item_name": "run"
  },
  "fields": [],
  "columns": [
    {"name": "id", "label": "ID", "type": "text"},
    {"name": "status", "label": "Status", "type": "status"},
    {"name": "owner", "label": "Owner", "type": "text"},
    {"name": "duration", "label": "Duration", "type": "duration"}
  ],
  "actions": [
    {"name": "open_run", "label": "Open run", "target": "run_detail"}
  ],
  "states": ["empty", "loading", "error", "ready"],
  "accessibility": {
    "aria_label": "Runs data grid"
  },
  "confidence": 0.94,
  "evidence": {
    "source": "ascii",
    "lines": [7, 8, 9, 10]
  }
}
```

Recommended component families:

- Layout: `page`, `region`, `container`, `stack`, `grid`, `card`, `toolbar`, `sidebar`, `header`, `footer`, `modal`, `drawer`, `tabs`.
- Forms: `form`, `fieldset`, `text_input`, `select`, `checkbox`, `radio`, `date_picker`, `button`, `search`.
- Data: `table`, `data_grid`, `list`, `detail_panel`, `metric_tile`, `metrics_strip`.
- Visualization: `chart_bar`, `chart_line`, `chart_pie`, `sparkline`, `gauge`, `progress`, `kpi`.
- Widgets: `filter_panel`, `upload`, `pagination`, `notification`, `timeline`, `map`, `media`, `code_block`.

## Web Page Contract

The web contract should combine layout, component, data, accessibility, and target metadata. It can extend the current zone taxonomy rather than replacing it.

Example:

```json
{
  "kind": "web_page_contract",
  "version": "0.1.0",
  "source_sketch": {
    "format": "ascii",
    "hash": "..."
  },
  "zones": [],
  "boxes": [],
  "components": [],
  "data_contracts": [],
  "render_targets": {
    "html": {"enabled": true, "annotation": "x-html"},
    "css": {"enabled": true, "annotation": "x-css"},
    "svg": {"enabled": true, "annotation": "x-svg"}
  },
  "coherence": {
    "required_checks": [
      "zone_component_coverage",
      "html_component_traceability",
      "css_zone_ownership",
      "svg_component_representation",
      "a11y_labels",
      "data_binding_resolution"
    ]
  }
}
```

Recommended annotations:

- `x-web` for shared web-page metadata.
- `x-component` for component intent.
- `x-html` for semantic HTML rendering decisions.
- `x-css` for token, class, layout, and responsive decisions.
- `x-svg` for blueprint and wireframe representation decisions.
- `x-data` for collections, records, measures, and field bindings.
- `x-a11y` for labels, landmarks, table captions, form labels, and live regions.

## HTML Rendering Strategy

The HTML renderer should render semantic markup from component intent:

- `page`, `header`, `footer`, `sidebar`, and `region` map to landmarks where appropriate.
- `form` maps to `<form>` with labeled controls and an action contract.
- `data_grid` maps to a table-like structure first, with progressive enhancement for richer grids later.
- `chart_*` maps to a semantic figure with a stable placeholder and data attributes.
- `gauge`, `kpi`, and `metric_tile` map to readable metric components with accessible labels.
- `tabs`, `modal`, and `drawer` map to accessible shell markup with state hooks.

Every rendered root component should include traceability attributes:

```html
<section data-zone-id="zone-runs" data-component-id="component-runs" data-component-type="data_grid">
```

The initial target should be static, valid, accessible HTML. Interactivity can be layered later through a JavaScript behavior contract.

## CSS Rendering Strategy

The CSS renderer should continue to own layout through generated classes and `[data-zone-id]` selectors, but it should also add component classes derived from the component contract.

CSS responsibilities:

- Preserve zone bounds and responsive behavior from the box model.
- Define reusable component classes such as `.gf-form`, `.gf-data-grid`, `.gf-chart`, `.gf-gauge`, and `.gf-widget`.
- Use design tokens for colors, spacing, type, borders, shadows, and focus states.
- Avoid inline styles in HTML.
- Provide component states such as loading, empty, error, selected, disabled, and active.
- Keep generated CSS deterministic from the contract.

The CSS contract should explicitly separate:

- Layout rules: page, rows, columns, grid placement.
- Component rules: form controls, tables, cards, charts, gauges.
- State rules: loading, empty, error, focus, active.
- Responsive rules: breakpoints and stacking behavior.

## SVG Rendering Strategy

The SVG renderer should produce a component-aware blueprint, not just boxes. It should remain lightweight and deterministic.

SVG responsibilities:

- Draw each layout zone using its ASCII-derived bounds.
- Draw component glyphs or simplified visual primitives.
- Represent forms with labels, input rectangles, selects, checkboxes, and buttons.
- Represent data grids with headers, rows, columns, and pagination zones.
- Represent charts with axes and schematic bars, lines, pies, or sparklines.
- Represent gauges with arcs, ticks, and a value indicator.
- Preserve `data-zone-id`, `data-component-id`, and `data-component-type` attributes.
- Add a title and description for accessibility.

The SVG should be useful as an architecture and design artifact even before the HTML is interactive.

## Coherence Checks

Extend `generation_fabric/layout/coherence.py` with component-aware checks.

Recommended checks:

- Every component references an existing zone.
- Every non-decorative zone has either a component or an explicit `container` classification.
- Component IDs are unique.
- Component type is supported by the renderer registry.
- Component bounds map to a box-model surface.
- Forms have fields, labels, names, and actions.
- Data grids have columns and a data source.
- Charts have a chart type, measure, and either axes or category/value bindings.
- Gauges have value, minimum, and maximum bindings.
- HTML preserves component IDs and zone IDs.
- CSS owns component classes and zone selectors.
- SVG draws every component with traceable attributes.
- Accessibility labels exist for forms, charts, gauges, and data grids.
- Reading order follows the zone order unless explicitly overridden.
- Unknown component hints are reported with remediation text.

## CLI And Artifact Strategy

Keep the current layout commands and add web-specific commands.

Proposed commands:

```text
ascii-zones --source-file sketch.ascii.md --output sketch.zones.json
ascii-components --source-file sketch.ascii.md --zones-file sketch.zones.json --output sketch.components.json
ascii-web --source-file sketch.ascii.md --output-dir generated/page
layout-web-html --contract-file page.web.json --output page.html
layout-web-css --contract-file page.web.json --output page.css
layout-web-svg --contract-file page.web.json --output page.svg
layout-web-coherence --contract-file page.web.json --output page.coherence.md
```

Recommended artifact family:

```text
page.ascii.md
page.zones.json
page.components.json
page.boxes.json
page.web.json
page.html
page.css
page.svg
page.coherence.md
```

This matches the existing sidecar style while adding a richer web contract.

## Worker Bee Integration

The worker bee should gain an ASCII-to-web capability that can generate, observe, and refine component intent.

Recommended worker bee responsibilities:

- Generate ASCII sketches from briefs using the supported dialect.
- Parse the sketch into zones.
- Extract component intent from labels and metadata lines.
- Produce a normalized web page contract.
- Render HTML, CSS, and SVG from the same contract.
- Run coherence checks across all artifacts.
- Report unresolved ambiguity as explicit design warnings.
- Store all sidecars so future agents can inspect the same object model.

This turns the ASCII sketch into an observable design object, rather than a one-off rendering prompt.

## Implementation Phases

### Phase 1: Component Intent Model

Add the component intent dataclasses and JSON schema. Implement deterministic extraction from existing zones and source lines. Start with plain component hints such as `[form]`, `[data_grid]`, `[chart_line]`, and `[gauge]`.

Deliverables:

- `ComponentIntentDocument`
- `ComponentIntent`
- parser for bracketed component hints
- extraction of `fields`, `columns`, `data`, `value`, `x`, `y`, `min`, `max`, and `action`
- `.components.json` sidecar

### Phase 2: Web Contract Builder

Add a contract builder that combines ASCII source, zones, boxes, components, and render target annotations.

Deliverables:

- `page.web.json`
- target annotations for `x-html`, `x-css`, `x-svg`, `x-data`, and `x-a11y`
- stable IDs for zones and components
- contract artifact writes through the existing artifact helper pattern

### Phase 3: Component-Aware HTML

Extend the HTML renderer to support component families.

Deliverables:

- semantic form rendering
- table-first data grid rendering
- figure-based chart placeholders
- accessible gauge and metric rendering
- traceability attributes on every component root

### Phase 4: Component-Aware CSS

Extend the CSS renderer with component classes and state classes.

Deliverables:

- component class registry
- generated styles for forms, grids, cards, charts, gauges, and widgets
- responsive behavior by component family
- no inline rendering dependencies

### Phase 5: Component-Aware SVG

Extend the SVG renderer from zone boxes to component blueprints.

Deliverables:

- form control wireframes
- data grid row and column wireframes
- chart schematics
- gauge schematics
- component labels and traceability attributes

### Phase 6: Web Coherence Audit

Add checks that validate component structure and rendering consistency.

Deliverables:

- component coverage checks
- renderer support checks
- data binding checks
- accessibility checks
- SVG representation checks
- remediation guidance in `.coherence.md`

### Phase 7: CLI And Worker Bee Path

Expose the pipeline through command-line entry points and worker bee orchestration.

Deliverables:

- `ascii-components`
- `ascii-web`
- `layout-web-html`
- `layout-web-css`
- `layout-web-svg`
- `layout-web-coherence`
- worker bee artifact bundle generation

### Phase 8: Learning Loop

Let future worker bees compare generated artifacts against the coherence report and repair only the contract layer before re-rendering.

Deliverables:

- repair prompts based on coherence failures
- preserved source evidence for every component
- regenerated sidecars from the repaired contract
- tests for before/after coherence improvement

## Testing Strategy

Recommended tests:

- Parse a plain ASCII layout and confirm generic container components are inferred.
- Parse component hints for forms, data grids, charts, gauges, and widgets.
- Verify `fields`, `columns`, `data`, `value`, `min`, `max`, `x`, `y`, and `action` metadata.
- Render semantic HTML with stable `data-zone-id` and `data-component-id` attributes.
- Render CSS with zone ownership and component class ownership.
- Render SVG with one visual representation per component.
- Verify coherence catches missing form labels, missing data grid columns, missing gauge ranges, and unsupported component types.
- Verify CLI commands write the complete artifact family.
- Add a golden example for an operations dashboard with filters, metrics, a data grid, and charts.

## First Milestone

The best first milestone is a deterministic operations dashboard:

```text
+----------------------------------------------------------+
| OPERATIONS DASHBOARD [page]                              |
+--------------------------+-------------------------------+
| FILTERS [form]           | DELIVERY HEALTH [gauge]       |
| fields: date,status,team | value: delivery_health        |
| action: apply_filters    | min: 0 max: 100               |
+--------------------------+-------------------------------+
| RUNS [data_grid]                                         |
| data: runs[]                                             |
| columns: id,status,owner,duration                        |
+--------------------------+-------------------------------+
| SUCCESS TREND [chart_line]                               |
| x: day y: success_rate                                   |
+----------------------------------------------------------+
```

Success criteria:

- The sketch produces zones, boxes, components, and a web contract.
- HTML renders a real form, readable gauge, data grid, and chart placeholder.
- CSS owns the layout and component states.
- SVG renders a coherent blueprint of the same components.
- The coherence report passes all required checks or names exact remediations.

## Key Decisions

- Start with static HTML/CSS/SVG. Add behavior and JavaScript contracts later.
- Treat SVG as a blueprint renderer, not a production chart engine.
- Render unknown components as generic containers with warnings.
- Keep the ASCII language small and predictable.
- Make the JSON web contract the stable interface for worker bees and future generators.
- Use contract annotations to prevent drift between HTML, CSS, SVG, and observability.

