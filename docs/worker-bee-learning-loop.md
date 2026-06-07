# Worker Bee Learning Loop

This repository uses the term "learning loop" as a benchmark and feedback loop, not as hidden model fine-tuning.

The purpose is to make the worker bee a power user of the existing Generation Fabric surface.

## What The Loop Does

- exercises the current schema, JSON, and Markdown capabilities
- runs the worker-bee planner and executor against real briefs
- verifies the generated artifacts through the same deterministic fabric that the rest of the repo uses
- reports coverage, lessons, and round-level results

## Why It Exists

The worker bee should not guess at the fabric. It should prove that it can drive the fabric reliably.

That means the learning loop is a benchmark:

1. take a capability catalog
2. run a deterministic case for each capability
3. validate the result
4. report what passed, what failed, and what needs another pass

## Current Coverage

The default learning catalog exercises:

- schema CRUD and validation
- schema inference
- generic JSON CRUD
- schema-driven JSON sample generation
- `oneOf` and `anyOf`
- Markdown rendering
- Markdown contract scaffolding
- legacy Markdown import
- the interactive schema shell
- worker-bee packet planning
- worker-bee document generation

## CLI Entry Point

Use the benchmark command from the repository root:

```powershell
python json_schema_crud.py worker-bee-learn --rounds 3 --output reports/worker-bee-learning.json
```

The command emits a JSON report that includes:

- requested and completed rounds
- coverage percentage
- the capability catalog
- per-case results
- lessons learned from the run
- artifact roots that point to the generated learning outputs

## Design Rule

The loop should stay deterministic and contract-backed.

It can measure the worker bee. It should not replace the fabric, and it should not become a second source of truth for document generation.
