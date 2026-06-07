# Worker Bee Migration Strategy

This document captures the first real migration step for bringing a worker-bee pattern into Generation Fabric.

The reference implementation in `C:\source\repos\bpm\internal\multi-agent-studio` is useful because it shows the pattern we want:

- structured packets define the workload
- a swarm or executor layer distributes work
- deterministic code handles file and ledger writes
- a model only contributes semantic judgment
- validation is separate from generation

Generation Fabric already has the core primitives this migration needs:

- schema creation, inference, and validation
- generic JSON CRUD and schema-driven sample generation
- deterministic Markdown rendering, import, and scaffolding
- a CLI that orchestrates those operations without mixing responsibilities

The worker bee should not replace that fabric. It should sit in front of it and turn a brief into an approved plan that the fabric can execute.

## North Star

```text
brief
-> planner
-> reviewed packet
-> deterministic fabric
-> generated schema / JSON / Markdown
-> validation
-> ledger and evidence
```

The worker bee is a planner and orchestrator, not a source of truth.

## Current Reuse Surface

The migration should reuse the existing generation layers instead of inventing new ones:

- `generation_fabric/schema/` for schema creation, validation, and inference
- `generation_fabric/json_documents/` for JSON document CRUD and sample generation
- `generation_fabric/markdown/` for render/import/scaffold behavior
- `generation_fabric/cli.py` for orchestration wiring

The new worker-bee package belongs beside those modules as the planning and execution boundary.

## New Package Shape

The first scaffold lives in `generation_fabric/worker_bee/` and defines the strategy objects that future planner/executor code can share.

The initial scaffold has three responsibilities:

1. describe the migration surfaces
2. describe the migration phases
3. keep the planner/reviewer/executor boundary explicit

The first concrete runtime-facing module is `generation_fabric/worker_bee/planner.py`, which turns a brief into a deterministic generation packet.

The next layer is `generation_fabric/worker_bee/executor.py`, which turns that packet and any sketch prompts into schema, JSON, and Markdown artifacts without hand-stitching the file contents.

The benchmark loop lives in `generation_fabric/worker_bee/learning.py`, which exercises the current fabric surface, records coverage, and tells us whether the worker bee is actually using the tools it is supposed to use.

The `worker-bee-plan` CLI command writes that packet to JSON, or prints it to stdout, so the planning contract is visible before the executor exists.

The `worker-bee-generate` CLI command executes the full brief-to-document path and writes the contract-backed Markdown output plus its sidecar schema and JSON files.

The current package does not need to be the full runtime yet. It needs to make the architecture concrete and testable.

## Migration Phases

### Phase 1: Stabilize the existing fabric

- keep the current schema, JSON, and Markdown commands stable
- keep the current contract registry stable
- keep round-trip behavior deterministic

### Phase 2: Add a planner contract

- accept a brief and target document type
- emit a structured generation plan
- keep the planner read-only
- surface the packet through `worker-bee-plan`

### Phase 3: Add an executor boundary

- take an approved plan
- call the existing fabric primitives
- write only the minimal deterministic output
- turn a brief into the generated document contract and markdown artifact

### Phase 4: Add verification and replay

- validate generated files against schema and golden output
- rerun the same packet safely
- record the result in a run ledger

### Phase 5: Add provider flexibility

- isolate model access behind a narrow adapter
- keep provider choice swappable
- avoid letting provider differences leak into the fabric contract

## Guardrails

- Do not hand-stitch generated schemas, JSON, or Markdown if the fabric can derive them.
- Do not let the planner mutate files.
- Do not let the executor invent contract shape.
- Do not treat a model response as complete until the fabric validates it.
- Do not blur planning, execution, and verification into one module.

## Success Criteria

We know the migration is working when:

- the worker-bee strategy has its own package and docs
- the planner can produce a structured packet from a brief
- the packet can be emitted from the CLI without hand-stitching
- the executor can write schema, JSON, and Markdown artifacts from that packet
- the learning loop can benchmark the current fabric capabilities and report 100% coverage when the surface is healthy
- the executor can reuse the existing fabric primitives
- the generated output is deterministic and testable
- a future provider swap does not change the file contract

## Related Files

- `generation_fabric/worker_bee/strategy.py`
- `generation_fabric/worker_bee/learning.py`
- `docs/module-map.md`
- `docs/worker-bee-learning-loop.md`
- `docs/compiler-pipeline-roadmap.md`

This is the first migration step, not the final architecture. The point is to make the worker-bee path explicit, aligned with the generation fabric, and safe to extend.
