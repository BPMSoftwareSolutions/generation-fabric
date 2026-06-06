# Compiler Pipeline Roadmap

## Why This Exists

We are turning the generation fabric into a small compiler pipeline:

`JSON Schema -> validate -> JSON content -> render -> Markdown`

The goal is to keep the responsibilities separate while still allowing them to cooperate:

- Schema modules define the contract.
- JSON modules manage the structured content that satisfies the contract.
- Markdown modules render deterministic documents from the contract plus content.
- Scaffold modules create ready-to-use examples that show how the system scales.

## What We Already Have

The current repository already contains the important proof points:

- `json_schema_crud.py` is now a thin compatibility wrapper over the package CLI.
- `generation_fabric/cli.py` orchestrates the command surface.
- `generation_fabric/schema/document.py`, `generation_fabric/schema/inference.py`, and `generation_fabric/schema/validation.py` hold schema-specific behavior.
- `generation_fabric/json_documents/crud.py` holds generic JSON tree mutation behavior.
- `generation_fabric/markdown/renderer.py` and `generation_fabric/markdown/contracts.py` hold Markdown generation and scaffolding.
- `examples/release-notes.schema.json` defines a contract-driven Markdown document.
- `examples/release-notes.json` is the matching structured content.
- `examples/release-notes.md` is the generated Markdown output.
- `tests/test_json_schema_crud.py` covers schema CRUD, inference, validation, combinators, Markdown generation, and the scaffold flow.

That means the core ideas are already proven. The next step is to split the code into modules without changing the behavior.

## Target Module Layout

### `core`

Shared infrastructure:

- `generation_fabric/core/io.py`
- `generation_fabric/core/pointer.py`

### `json_documents`

Generic JSON document editing:

- `generation_fabric/json_documents/crud.py`

### `schema`

Schema-specific behavior:

- `generation_fabric/schema/document.py`
- `generation_fabric/schema/inference.py`
- `generation_fabric/schema/validation.py`

### `markdown`

Markdown generation and contract scaffolding:

- `generation_fabric/markdown/renderer.py`
- `generation_fabric/markdown/contracts.py`

### `cli`

Thin orchestration only:

- `generation_fabric/cli.py`
- `json_schema_crud.py` as a wrapper for compatibility

## Implementation Phases

### Phase 0: Freeze the Current Behavior

Lock the existing behavior with tests before moving code around.

Acceptance criteria:

- current CLI commands still work
- existing examples still render the same Markdown
- the test suite stays green

### Phase 1: Extract Shared Core Helpers

Move the reusable plumbing into a small core module.

Implemented split:

- `generation_fabric/core/io.py`
- `generation_fabric/core/pointer.py`

Acceptance criteria:

- schema and markdown modules can both use the same pointer and IO helpers
- no behavior changes

### Phase 2: Extract the Schema Module

Move schema-specific operations into a dedicated package.

Includes:

- schema creation
- schema CRUD operations
- schema validation
- combinator helpers

Acceptance criteria:

- schema commands still behave exactly the same
- schema unit tests pass unchanged

### Phase 3: Extract the JSON Content Module

Move content-oriented JSON logic into its own package.

Includes:

- JSON instance loading
- schema-based validation of instances
- schema inference from sample JSON

Acceptance criteria:

- `infer` still produces the same schema shapes
- `validate` still rejects invalid instances

### Phase 4: Extract the Markdown Module

Move rendering logic into a dedicated Markdown module.

Includes:

- Markdown rendering from JSON content
- schema metadata interpretation
- tables, lists, headings, code blocks, and nested sections

Acceptance criteria:

- `markdown` still renders the release-notes example exactly
- golden Markdown tests pass

### Phase 5: Add Contract Scaffolds

Keep the contract templates as first-class artifacts.

Includes:

- registry-backed contract kinds
- `markdown-contract` scaffolding
- example schema + sample JSON + generated Markdown
- canonical patterns that can be copied for new document types

Acceptance criteria:

- a new contract can be scaffolded in one command
- examples demonstrate the full pipeline end to end

### Phase 6: Add Document-Model Editing Later

Only do this if we need editable Markdown as a structured document model.

This is where we would introduce a richer Markdown AST or document model, so edits are made against structure instead of raw text.

### Phase 7: Import Legacy Markdown

Add a Markdown importer that turns existing `.md` files into a schema plus JSON contract.

Includes:

- legacy Markdown parsing for common block types
- generated schema and sample JSON
- optional round-trip rendering for verification

Acceptance criteria:

- Markdown can round-trip through a structured model if needed
- editing stays deterministic and validation-friendly

## Real Examples That Show Scale

### 1. Release Notes

This is the current canonical example.

Shape:

- title and release metadata
- summary paragraph
- highlight list
- nested sections with their own headings and bullets

Why it matters:

- shows headings, lists, and nested repetition
- demonstrates that the renderer can handle a realistic business document

### 2. API Changelog

Good next example for scale.

Shape:

- version metadata
- breaking changes table
- per-endpoint sections
- callout blocks for migration notes

Why it matters:

- proves the same pipeline can handle highly structured technical docs
- introduces more table-heavy and nested content

### 3. Incident Report

Good example for operational content.

Shape:

- incident summary
- timeline
- action items
- owners and follow-up tables

Why it matters:

- shows how the same contract approach works for operations and support
- demonstrates that the JSON source can later come from a database or incident system

## Testing Strategy

### Unit Tests

Test the pure functions in each module:

- pointer parsing
- atomic writes
- schema validation
- Markdown rendering helpers
- contract scaffolding helpers

### Golden Tests

Keep committed example files and assert the renderer produces exactly the same Markdown.

This is the most important guardrail for deterministic generation.

### Integration Tests

Exercise the CLI end to end:

- create a schema
- validate a JSON instance
- scaffold a contract
- render Markdown
- verify the output files

### Negative Tests

Add tests for:

- invalid JSON
- invalid JSON Pointer values
- schema violations
- missing required fields
- bad scaffold parameters

## Practical Refactor Order

If we want to do this in short order, the best order is:

1. Extract shared core helpers.
2. Extract schema validation and CRUD.
3. Extract JSON content validation and inference.
4. Extract Markdown rendering.
5. Keep the CLI thin.
6. Expand examples one document type at a time.

That sequence minimizes churn and preserves the current working behavior while we peel the system apart.

## Success Criteria

We know the refactor is done when:

- each module has one clear responsibility
- the CLI is thin and declarative
- the Markdown output is fully deterministic
- examples are committed as real artifacts
- tests prove the schema, content, and Markdown layers work together
