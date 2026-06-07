# Open-Source AI Harness For UI/UX Exploration

Review date: 2026-06-07

## Purpose

This document investigates how Generation Fabric can implement an open-source AI harness for UI/UX exploration. The goal is to create a governed loop that can explore interface variants, render them in a browser, collect evidence, run accessibility and visual checks, and promote only coherent UI surfaces.

The harness should not replace the existing contract pipeline. It should wrap it:

```text
brief / ASCII / web contract
-> generated UI variants
-> deterministic HTML/CSS/SVG render
-> browser execution
-> DOM, screenshot, trace, accessibility, and coherence evidence
-> contract-level repair or human review
-> promotion gate
```

## Current Local Fit

Generation Fabric already has the right source-of-truth layer for a UI/UX harness:

- `generation_fabric/layout/ascii_sketch.py` parses ASCII sketches into layout zones.
- `generation_fabric/layout/component_intent.py` extracts component intent such as forms, data grids, charts, gauges, and widgets.
- `generation_fabric/layout/web_contract.py` combines zones, boxes, and component intent into a web page contract.
- `generation_fabric/html/web_renderer.py` renders component-aware semantic HTML.
- `generation_fabric/css/web_renderer.py` renders layout and component CSS.
- `generation_fabric/svg/web_renderer.py` renders a component-aware SVG blueprint.
- `generation_fabric/layout/web_coherence.py` audits component coherence across the contract and render targets.
- `generation_fabric/layout/web_repair.py` already has a deterministic contract repair cycle.
- `generation_fabric/layout/web_bundle.py` writes the full ASCII-to-web sidecar family.
- `tests/test_web_pipeline.py` proves the operations dashboard can reach 100 percent web coherence.

The existing CLI already exposes the key contract pipeline:

```powershell
python json_schema_crud.py ascii-web --source-file examples/operations-dashboard.ascii.md --page-id operations-dashboard --output-dir generated/ui --overwrite
python json_schema_crud.py layout-web-coherence --contract-file examples/operations-dashboard.web.json --output generated/ui/operations-dashboard.web-coherence.md --overwrite
python json_schema_crud.py layout-web-repair --contract-file examples/operations-dashboard.web.json --output generated/ui/operations-dashboard.repaired.web.json --overwrite
```

That means the new work is not "invent UI generation." The new work is to observe, score, compare, and govern generated UI variants in a browser.

## Key Gap

The current pipeline can prove static contract coherence, but it does not yet prove browser-level UX quality.

Missing capabilities:

- Browser execution of generated HTML/CSS.
- Screenshot capture across desktop, tablet, and mobile viewports.
- Visual regression or visual stability scoring.
- Accessibility scan results from the rendered DOM.
- Trace artifacts for step-by-step UI exploration.
- Interaction tests for forms, filters, data grids, tabs, modals, and widgets.
- AI-assisted exploration that proposes variants and learns from evidence.
- Promotion gates that distinguish experimental sketches from durable UI surfaces.

## Open-Source Landscape

The best path is a native Generation Fabric harness that uses open-source tools by role.

| Tool | License / posture | Best role in the harness | Fit |
| --- | --- | --- | --- |
| Playwright | Apache-2.0; cross-browser automation for Chromium, Firefox, and WebKit | Deterministic browser runner, DOM checks, screenshots, traces, visual comparisons | Strong default foundation |
| axe-core / @axe-core/playwright | MPL 2.0; open-source accessibility engine | Accessibility scans on generated HTML pages | Strong default foundation |
| Browser Use | MIT; Python AI browser automation, local or self-hosted | Optional AI explorer that can navigate and inspect rendered pages | Good Python-first fit |
| Stagehand | MIT; AI browser automation with `act`, `extract`, `observe`, and `agent` primitives | Optional AI browser explorer, especially if a TypeScript Playwright runner is added | Good optional fit |
| Storybook | Open-source UI workshop for components and pages in isolation | Optional component exploration and documentation surface | Useful after UI components become reusable assets |
| LangGraph | MIT; stateful agent orchestration with human-in-the-loop controls | Optional orchestration layer for multi-step exploration and review loops | Useful only after the simple loop proves value |
| OpenHands | MIT core; open-source coding agent platform and SDK | Optional external agent harness or sandbox reference | Not needed for the first implementation |

The recommendation is not to adopt a broad autonomous coding platform first. Start with Playwright plus axe-core, then add an AI exploration adapter around the browser evidence loop.

## Research Signal

Recent UI generation research points in the same direction:

- VISTA frames web-app generation as a combined structural, behavioral, and visual problem. It explicitly separates visual fidelity from functional correctness, which supports a harness that scores DOM, behavior, and screenshots separately.
- VisRefiner shows the value of render-compare-revise loops for screenshot-to-code generation. Generation Fabric can apply that same principle without training a model: render the contract, compare browser evidence, repair the contract, and rerender.

The strategic lesson is simple: UI/UX generation needs a feedback harness, not a one-shot prompt.

## North Star

The harness should turn UI exploration into an observable, contract-backed object:

```text
UI intent
-> variants
-> web contracts
-> rendered pages
-> browser evidence
-> UX score
-> repair proposal
-> promoted contract
```

A generated UI surface is promotable only when it can explain:

- what contract produced it
- what variant it belongs to
- what browser viewports were checked
- what accessibility violations remain
- what interaction paths were exercised
- what screenshots and traces were captured
- what coherence checks passed
- what human or automated gate approved it

## Proposed Harness Contract

Add a `ui_exploration_contract` that references existing web contracts instead of duplicating them.

Example:

```json
{
  "kind": "ui_exploration_contract",
  "version": "0.1.0",
  "surface_key": "operations-dashboard",
  "source_contract": "examples/operations-dashboard.web.json",
  "authority": "preview_only",
  "variant_set": {
    "variant_count": 3,
    "strategy": "contract_variation",
    "source": "worker_bee"
  },
  "viewports": [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "tablet", "width": 900, "height": 1100},
    {"name": "mobile", "width": 390, "height": 844}
  ],
  "checks": {
    "contract_coherence": true,
    "dom_traceability": true,
    "accessibility": true,
    "screenshots": true,
    "visual_regression": false,
    "interaction_paths": ["load", "focus_form", "submit_form"]
  },
  "promotion": {
    "required_score": 90,
    "human_review_required": true,
    "unknown_policy": "fail_closed"
  }
}
```

## Proposed Directory Shape

Keep the current Python core and add a small harness boundary.

```text
generation_fabric/
  ui_harness/
    __init__.py
    contract.py
    evidence.py
    scoring.py
    promotion.py
    report.py
    variants.py
    ai_explorer.py

tools/
  ui-harness/
    package.json
    playwright.config.ts
    tests/
      generated-surface.spec.ts
    src/
      runSurface.ts
      axeScan.ts
      captureEvidence.ts

generated/
  ui-harness/
    operations-dashboard/
      operations-dashboard.ui-harness.json
      operations-dashboard.evidence.json
      operations-dashboard.a11y.json
      operations-dashboard.dom.json
      operations-dashboard.score.json
      operations-dashboard.exploration.md
      screenshots/
      traces/
```

Why this split works:

- Python remains the contract and artifact owner.
- Node/TypeScript stays confined to the browser automation layer.
- Playwright and axe-core can be updated independently from Generation Fabric internals.
- The harness can run locally or in CI without changing the web contract model.

## Harness Flow

### 1. Plan

Input can be a brief, ASCII sketch, or existing `.web.json` contract.

The planner creates a UI exploration contract:

```text
surface key
source contract
variant plan
viewports
interaction paths
checks
promotion rules
```

### 2. Generate Variants

Variants should be generated at the contract layer first:

```text
base.web.json
-> variant-a.web.json
-> variant-b.web.json
-> variant-c.web.json
```

Each variant then renders deterministic HTML, CSS, and SVG.

Variant changes should be limited to governed fields:

- component layout
- component ordering
- labels and headings
- variant tokens
- density
- chart/gauge presentation
- form grouping
- responsive behavior

Avoid AI-generated freeform HTML as the durable source. If an AI agent suggests markup, translate the suggestion back into the contract.

### 3. Serve

The harness should serve generated HTML/CSS from a local static server:

```text
http://127.0.0.1:<port>/operations-dashboard.html
```

The server should be local-only and ephemeral.

### 4. Observe

Playwright captures deterministic evidence:

- DOM snapshot
- accessibility tree summary
- screenshots per viewport
- console errors
- network errors
- trace zip
- interaction result log
- element inventory keyed by `data-zone-id` and `data-component-id`

### 5. Score

The score should be decomposed, not a single vague "looks good" number.

Recommended score dimensions:

| Dimension | Evidence | Example gate |
| --- | --- | --- |
| Contract coherence | `.web-coherence.md` / `.web-coherence.json` | No failed checks |
| DOM traceability | Playwright DOM scan | Every component ID appears |
| Accessibility | axe-core JSON | No critical or serious violations |
| Responsive layout | screenshots and DOM bounds | No horizontal overflow at required viewports |
| Interaction behavior | Playwright action log | Required paths pass |
| Visual stability | screenshot comparison | Diff under configured threshold |
| Console health | browser console log | No uncaught errors |

### 6. Repair

The first repair loop should remain deterministic:

```text
evidence -> repair proposal -> web contract patch -> rerender -> reobserve
```

AI can propose repairs, but the system should apply only validated contract edits.

Safe early repairs:

- add missing accessible labels
- add missing gauge min/max defaults
- demote unsupported components to containers
- rename duplicate component IDs
- add missing data-grid columns only when source evidence names them
- add responsive stacking metadata

Unsafe repairs that should require human review:

- changing information architecture
- adding new actions
- changing authority or promotion posture
- inventing data sources
- adding external dependencies
- changing production-bound behavior

### 7. Promote

Promotion should create a record:

```text
variant id
source contract hash
evidence hash
score
remaining warnings
reviewer
promotion posture
```

Promotion states:

- `draft`
- `exploration`
- `lab_ready`
- `production_candidate`
- `promoted`
- `rejected`

## CLI Strategy

Add commands that mirror the existing deterministic style.

```powershell
python json_schema_crud.py ui-harness-plan --contract-file examples/operations-dashboard.web.json --output generated/ui-harness/operations-dashboard.ui-harness.json

python json_schema_crud.py ui-harness-run --harness-file generated/ui-harness/operations-dashboard.ui-harness.json --output-dir generated/ui-harness/operations-dashboard --overwrite

python json_schema_crud.py ui-harness-score --evidence-file generated/ui-harness/operations-dashboard/operations-dashboard.evidence.json --output generated/ui-harness/operations-dashboard/operations-dashboard.score.json --overwrite

python json_schema_crud.py ui-harness-report --score-file generated/ui-harness/operations-dashboard/operations-dashboard.score.json --output generated/ui-harness/operations-dashboard/operations-dashboard.exploration.md --overwrite
```

Optional later:

```powershell
python json_schema_crud.py ui-harness-explore --brief "Explore a cleaner operations dashboard" --variants 5 --output-dir generated/ui-harness/ops-exploration --provider local

python json_schema_crud.py ui-harness-promote --score-file generated/ui-harness/ops-exploration/best.score.json --target examples/operations-dashboard.web.json
```

## AI Explorer Role

AI belongs in exploration and review, not in unchecked promotion.

Recommended roles:

- Variant designer: proposes alternate ASCII sketches or contract variants.
- Browser observer: inspects the rendered page and names mismatches.
- UX reviewer: summarizes evidence and suggests contract-level repairs.
- Repair proposer: emits a JSON Patch against the web contract.
- Promotion guard: checks whether the evidence satisfies promotion policy.

The AI explorer should receive:

- the web contract
- the component inventory
- the coherence report
- screenshots
- DOM evidence
- accessibility results
- explicit allowed and blocked edit fields

The AI explorer should never receive:

- secrets
- browser credentials
- external production URLs
- authority to write promoted artifacts without a gate

## Browser Use vs Stagehand

Both Browser Use and Stagehand are plausible optional AI browser layers.

Choose Browser Use first if:

- the harness stays Python-first
- we want local or self-hosted browser automation
- we want to integrate with the existing worker-bee provider boundary
- we want a quick AI browser explorer around generated static pages

Choose Stagehand first if:

- the Playwright runner becomes TypeScript-first
- we want explicit `act`, `extract`, `observe`, and `agent` browser primitives
- we want a bridge between deterministic Playwright code and natural-language browser steps

Either way, Playwright remains the deterministic evidence layer. Browser Use or Stagehand should not become the source of truth.

## Storybook Role

Storybook should be optional in the first release.

Use it when Generation Fabric starts producing reusable component families, not just standalone static pages. At that point, Storybook can become the exploratory component workshop:

```text
component intent contract
-> generated component fixture
-> story
-> interaction test
-> accessibility test
-> visual snapshot
```

For the first milestone, a static local harness around generated HTML is leaner.

## LangGraph Role

Do not add LangGraph for the first harness pass unless the control flow becomes hard to follow.

The initial loop can be simple Python orchestration:

```text
plan -> render -> run browser -> score -> report
```

LangGraph becomes useful when the system needs:

- multiple agent roles
- persistent state across explorations
- human-in-the-loop approval nodes
- branching repair loops
- retry policies and resumability

Until then, a small deterministic orchestrator is easier to maintain.

## Governance Rules

The harness should fail closed.

Required guardrails:

- Run against local generated files by default.
- Use `127.0.0.1` only unless an allowlist explicitly permits another host.
- Never use real credentials in exploration mode.
- Treat browser actions as preview-only.
- Store all evidence as sidecars.
- Hash source contracts and evidence files.
- Never promote if contract coherence fails.
- Never promote if critical accessibility issues remain.
- Never promote if required component traceability is missing.
- Never let an AI agent invent authority, data sources, or production actions.

## Implementation Phases

### Phase 1: Static Browser Evidence

Add the minimum browser harness around existing web contracts.

Deliverables:

- `ui_exploration_contract` schema and JSON builder.
- `ui-harness-plan` CLI command.
- local static server helper.
- Playwright runner under `tools/ui-harness`.
- screenshots for desktop, tablet, and mobile.
- DOM traceability evidence.
- console and network error capture.
- Markdown exploration report.

Success criteria:

- `examples/operations-dashboard.web.json` can be rendered, served, opened, screenshotted, and reported.
- Evidence records every `data-component-id`.
- Generated report links to screenshots and trace files.

### Phase 2: Accessibility And Responsive Gates

Add axe-core and responsive layout checks.

Deliverables:

- axe-core Playwright scan.
- `operations-dashboard.a11y.json`.
- severity-based accessibility score.
- horizontal overflow check.
- viewport component bounds summary.

Success criteria:

- Critical and serious accessibility violations fail promotion.
- The report names exact selectors and component IDs where possible.

### Phase 3: Visual Stability

Add screenshot baselines and visual comparison thresholds.

Deliverables:

- screenshot baseline directory.
- visual diff report.
- masked dynamic regions config.
- deterministic screenshot CSS if needed.

Success criteria:

- The same generated contract produces stable screenshots in the same environment.
- Intentional contract changes produce explainable visual diffs.

### Phase 4: Interaction Paths

Add generated interaction tests from component intent.

Deliverables:

- form focus path.
- form submit path.
- data-grid empty state check.
- tab/modal/drawer checks when those component types exist.
- action event inventory.

Success criteria:

- Components with declared actions are exercised or explicitly marked manual.

### Phase 5: AI-Assisted Variant Exploration

Add AI-generated variants, but keep promotion governed.

Deliverables:

- variant contract generator.
- AI explorer adapter for Browser Use or Stagehand.
- evidence-aware variant ranking.
- JSON Patch repair proposals.

Success criteria:

- The harness can generate several contract variants and rank them without promoting automatically.

### Phase 6: Promotion Workflow

Add durable promotion records.

Deliverables:

- promotion ledger.
- promoted contract hash.
- evidence hash.
- reviewer field.
- remaining warnings.
- promotion posture.

Success criteria:

- A reviewer can trace a promoted UI surface back through its contract, evidence, and score.

## First Milestone

Use the committed operations dashboard as the baseline.

```powershell
python json_schema_crud.py ascii-web --source-file examples/operations-dashboard.ascii.md --page-id operations-dashboard --output-dir generated/ui-harness/operations-dashboard --overwrite
python json_schema_crud.py ui-harness-plan --contract-file generated/ui-harness/operations-dashboard/operations-dashboard.web.json --output generated/ui-harness/operations-dashboard/operations-dashboard.ui-harness.json --overwrite
python json_schema_crud.py ui-harness-run --harness-file generated/ui-harness/operations-dashboard/operations-dashboard.ui-harness.json --output-dir generated/ui-harness/operations-dashboard --overwrite
python json_schema_crud.py ui-harness-report --evidence-file generated/ui-harness/operations-dashboard/operations-dashboard.evidence.json --output generated/ui-harness/operations-dashboard/operations-dashboard.exploration.md --overwrite
```

Expected artifacts:

```text
operations-dashboard.ui-harness.json
operations-dashboard.evidence.json
operations-dashboard.dom.json
operations-dashboard.a11y.json
operations-dashboard.score.json
operations-dashboard.exploration.md
screenshots/desktop.png
screenshots/tablet.png
screenshots/mobile.png
traces/load.trace.zip
```

## Testing Strategy

Python tests:

- build a valid UI exploration contract from a web contract
- reject missing source contracts
- compute a score from fixture evidence
- render a Markdown exploration report
- enforce promotion fail-closed rules

Node/Playwright tests:

- load generated HTML from a local server
- confirm all component IDs are present in the DOM
- capture screenshots across required viewports
- run axe-core and write JSON output
- fail on console errors
- save a trace on failure

Golden example:

- `examples/operations-dashboard.web.json`
- generated harness evidence fixture
- generated exploration report

## Risks

| Risk | Mitigation |
| --- | --- |
| Browser automation adds Node dependency complexity | Keep the Node runner isolated under `tools/ui-harness` |
| AI explorer overreaches | AI can propose only contract patches, never direct promotion |
| Visual snapshots become flaky | Lock viewport, fonts, environment, and screenshot CSS |
| Accessibility results are noisy | Gate only critical/serious first and keep manual review notes |
| Harness becomes a second source of truth | Store evidence as derived sidecars; web contract remains source |
| Open-source tool churn | Adapter boundary per tool; Playwright is the stable core |

## Recommendation

Implement the harness in this order:

1. Playwright browser evidence.
2. axe-core accessibility evidence.
3. Score and report generation.
4. Deterministic repair from evidence.
5. AI-assisted variant exploration through Browser Use or Stagehand.
6. Optional LangGraph orchestration after the simple loop proves its value.
7. Optional Storybook component workshop when UI components become reusable products.

The core phrase to protect is:

```text
UI is operational evidence, not just visual output.
```

Generation Fabric already owns the contract layer. The open-source AI harness should make that contract visible, testable, explorable, and promotable.

## Sources

- [Playwright GitHub](https://github.com/microsoft/playwright)
- [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots)
- [Playwright trace viewer](https://playwright.dev/docs/trace-viewer)
- [axe-core by Deque](https://www.deque.com/axe/axe-core/)
- [Storybook GitHub](https://github.com/storybookjs/storybook)
- [Browser Use open-source docs](https://docs.browser-use.com/open-source/introduction)
- [Browser Use GitHub](https://github.com/browser-use/browser-use)
- [Stagehand website](https://www.stagehand.dev/)
- [Stagehand GitHub](https://github.com/browserbase/stagehand)
- [LangGraph overview](https://www.langchain.com/langgraph)
- [OpenHands GitHub](https://github.com/OpenHands/OpenHands)
- [VISTA: An End-to-End Benchmark for Visual Spec-to-Web-App Coding Agents](https://arxiv.org/abs/2605.26144)
- [VisRefiner: Learning from Visual Differences for Screenshot-to-Code Generation](https://arxiv.org/abs/2602.05998)

