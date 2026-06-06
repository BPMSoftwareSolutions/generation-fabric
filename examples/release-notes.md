# Release Notes

Contract-driven release notes generated from a JSON Schema.

**version**: 1.0.0

**released_on**: 2026-06-06

Contract-driven Markdown generation is now part of the generation fabric.

- Schema-defined content structure
- Deterministic Markdown rendering
- Reusable scaffolding for new documents

## Renderer

The renderer now validates data and emits Markdown from a schema contract.

- Validates the schema before rendering
- Validates the JSON instance against the schema
- Writes output atomically

## Quality

The contract ships with tests and a canonical example payload.

- Unit tests cover the scaffold and render paths
- Example files live in the repository
- The schema and sample stay in sync
