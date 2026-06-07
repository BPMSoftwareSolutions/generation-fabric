# Worker-Bee Object Model — Producer Design Review & Next Steps

Analysis date: 2026-06-07

This document analyzes where the object-model observability thread stands and how
to take it to the next level. It was started while the **upstream producer**
(`worker_bee/object_model.py`) was missing; that producer landed during the
review, so this is now a design review of the working producer plus a concrete
hardening plan — not a build-from-scratch spec.

---

## 1. Where we are

### The whole thread is now wired and the suite is green (78 tests)

The object-model capability — observe the OO architecture (classes, dataclasses,
protocols, inheritance, composition, patterns) and render it as a Mermaid
`classDiagram` + architecture report, the OO sibling of the execution-flow
`sequenceDiagram` observation — is now end-to-end:

| Piece | File | Status |
|---|---|---|
| Producer (scan + classify + relate + report) | `worker_bee/object_model.py` (1461 ln) | ✅ built, working |
| Diagram renderer (consumer) | `worker_bee/object_diagram.py` | ✅ built |
| Coherence audit (consumer) | `worker_bee/object_coherence.py` | ✅ built |
| CLI command | `worker-bee-object-model` | ✅ wired |
| Package exports | `worker_bee/__init__.py` | ✅ resolves |
| Strategy / spec | [worker-bee-object-model-observability-strategy.md](worker-bee-object-model-observability-strategy.md) | ✅ |

Running it on the spec's own fixture is clean and produces a contract-backed
report:

```text
python json_schema_crud.py worker-bee-object-model \
    --source-file generation_fabric/worker_bee/provider.py
→ 3 classes, 3 relationships, 7 patterns, 11 coherence checks, 95% score
```

The picture changed *during this review*: it began with the producer missing (so
`worker_bee` would not even import), and the producer landed mid-analysis — which
is why this is a design review rather than a build spec.

### The extraction quality is genuinely strong

On `provider.py` (the spec's own example), the producer correctly observes:

- **kinds**: `WorkerBeePlanProposal` → `frozen_value_object`,
  `WorkerBeePlanningProvider` → `protocol`,
  `DeterministicWorkerBeePlanningProvider` → `provider`.
- **relationships**: `implements_protocol` (evidence: "structural method parity"),
  `instantiates` (constructor call), `serializes` (shared dataclass helper) —
  each with anchor + confidence.
- **patterns**: 7 signals; **coherence**: 11 checks at a 95% score, with a real
  recommendation flagged (`value_objects_are_frozen` warn).

That is exactly the architecture-as-data the strategy doc set out to build. The
data layer is in good shape.

---

## 2. The gap is now report quality + tests, not the scanner

The producer's JSON is solid; the **rendered Markdown report has four concrete
defects**, all in the presentation layer. None require touching the AST scan.

### Bug 1 — the Mermaid `classDiagram` omits every field and method

The diagrams render only the class name + stereotype; the strategy doc's example
shows `+provider_name` and `+propose(brief, …)` inside the block.

**Root cause (confirmed):** the producer feeds the diagram renderer
`model_class.to_dict()` **dicts**. `object_diagram.py` was updated so the
*list* accessors (`_class_fields`, `_class_methods`, `_class_name`) use the
dict-aware `_value()` helper — but inside `_class_block` the *per-member* reads
still use raw `getattr`:

```python
# _class_block / _field_annotation / _method_signature
name = _normalize_text(getattr(field, "name", ""))      # field is a dict → ""  → skipped
annotation = _normalize_text(getattr(field, "annotation", ""))
signature = _normalize_text(getattr(method, "signature", ""))
```

On a dict, `getattr(field, "name", "")` returns `""`, so every member is dropped.

**Fix:** route those member reads through the existing dict-aware `_value()`
accessor (`_value(field, "name")`, `_value(field, "annotation")`,
`_value(method, "signature")`, `_value(method, "name")`). One small, local change
in `object_diagram.py`; no producer change. (Add a regression test that asserts
`+propose(` appears in the rendered diagram.)

### Bug 2 — per-class `fields` render as N one-row tables

Each field becomes its own table with a repeated header instead of one table with
N rows. The `class_inventory` block gets this right (`{rows: array, kind: table}`)
but the per-class `fields`/`methods` arrays in `build_object_model_document_schema`
mark the *item* as `kind: table` and the *array* as `kind: section`, so the
renderer emits one table per item.

**Fix:** make the `fields` array itself `x-markdown: {kind: "table"}` (drop the
per-item table), matching the `class_inventory.rows` shape that already renders
correctly.

### Bug 3 — method `line_start` / `line_end` / `returns` leak as bare blocks

Inside the per-method `section`, untagged scalar properties fall through to the
default paragraph renderer, so the report shows loose `29` / `32` lines and stray
return expressions.

**Fix:** give those properties explicit `x-markdown` (label paragraphs, or fold
`line_start`/`line_end` into the method `anchor`), or render methods as a single
table per class instead of a section-per-method.

### Bug 4 — Overview prints the source path twice

`source_roots` and `source_files` are the same single path for a one-file scan and
render as two identical bullet lists.

**Fix:** label them distinctly (`Roots:` vs `Files:`) or omit `source_files` when
it equals the roots.

---

## 3. Missing safety net: tests + a committed golden

The producer has **no dedicated tests and no committed golden example**, so the 78
green tests don't actually exercise it (they only confirm the package imports).
This is the highest-priority gap — a 1461-line module with zero coverage.

Recommended:

1. `tests/test_worker_bee_object_model.py`:
   - `scan_python_object_model([provider.py], scope="module")` → assert 3 classes,
     the three kinds, the `implements_protocol` edge, score == 95.0.
   - **determinism**: scan twice → identical `to_dict()`.
   - `build_object_model_report_document(document)` validates and the rendered
     Markdown contains a non-empty `classDiagram` with `+propose(` (guards Bug 1).
   - CLI `worker-bee-object-model` writes the three sidecars and refuses overwrite.
2. A committed golden trio under `examples/` (scan `worker_bee/provider.py` — small,
   stable, and the canonical Protocol+provider+value-object fixture). Add a
   `scripts/generate_object_model_example.py` so the golden is reproducible, exactly
   like `scripts/generate_segment_examples.py`.
3. Pin the golden **only after** Bugs 1–4 are fixed, so the committed artifact is
   the clean version.

---

## 4. Producer design notes (for future evolution)

The producer is well-shaped: one public `scan_python_object_model` composed of
single-responsibility stages (`_scan_classes` → `_collect_relationships` →
`classify_object_pattern` → `audit_object_model_coherence` → diagram render →
metrics). Keep that separation. Two structural suggestions:

- **Promote shared AST helpers.** `object_model.py` re-implements `_anchor`,
  `_line_span`, `_module_path`, `_source_hash`, `_format_signature`,
  `_resolve_call_name`, etc. that already exist in `taxonomy.py`. Lift the common
  set into `worker_bee/_ast_common.py` so there is one definition of "anchor" and
  "signature" across taxonomy, observation, and the object model. This is the DRY
  cleanup the OO design review would flag.
- **Pick one consumer calling convention.** The producer feeds the consumers
  `to_dict()` dicts; the consumers are duck-typed for both dicts and dataclasses.
  Bug 1 is exactly the failure mode of that ambiguity. Decide that consumers
  always receive **dicts**, make every accessor go through `_value()`, and add a
  test — or pass dataclasses and drop the dict branch. Consistency kills this class
  of bug.

---

## 5. How to take it to the next level

1. **Fix Bugs 1–4, then lock a golden + tests** (sections 2–3). This converts the
   working prototype into a trustworthy, regression-guarded surface.
2. **Feed the learning loop.** Add an `object-model` capability case to
   `worker_bee/learning.py` so coverage tracks this surface like every other target.
3. **Repo-scale architecture report.** `scope="repo"` over `generation_fabric/` →
   one overview diagram + per-package diagrams + a cross-package relationship table.
   This is the artifact that makes the whole fabric self-describing.
4. **Architecture drift gate.** `source_hash` is already captured; add a `--check`
   mode that fails when the committed object-model JSON no longer matches the
   source — OO coherence as a CI gate, mirroring the layout coherence audit.
5. **Tie into the visual-intent inventory.** An object-model document is itself a
   meaningful inventory item; giving each package an architecture diagram closes
   the doctrine "no meaningful inventory without visual intent" for code as well as
   pages.
6. **Document the command.** Add `worker-bee-object-model` to the README **contract
   source** (`examples/readme.json` + `readme.schema.json`) and re-render — the
   README is a derived artifact — and add the new modules to `docs/module-map.md`.

---

## 6. Immediate next steps (in order)

1. Fix Bug 1 in `object_diagram.py` (route member reads through `_value()`).
2. Fix Bugs 2–4 in `build_object_model_document_schema` / `_build_report_data`.
3. Add `tests/test_worker_bee_object_model.py` + a reproducible golden example.
4. Document the command (README contract source + `module-map.md`), re-render.
5. Run `python -m unittest discover -s tests -v` → confirm green, then commit.
