# Module Map

This repository is organized so the file names tell the implementation story.

## Root Entry

- `json_schema_crud.py`: compatibility wrapper that forwards to the package CLI.

## Package Layout

- `generation_fabric/cli.py`: command parsing and orchestration only.
- `generation_fabric/exceptions.py`: shared exception types.

## Core

- `generation_fabric/core/io.py`: atomic JSON/text IO and JSON loading helpers.
- `generation_fabric/core/pointer.py`: JSON Pointer parsing and traversal helpers.

## JSON Documents

- `generation_fabric/json_documents/crud.py`: generic JSON tree read/create/update/delete operations.
- `generation_fabric/json_documents/sample.py`: schema-driven JSON sample generation helpers.

## Schema

- `generation_fabric/schema/document.py`: schema creation and combinator attachment.
- `generation_fabric/schema/inference.py`: schema inference from sample JSON.
- `generation_fabric/schema/validation.py`: schema and instance validation.

## Markdown

- `generation_fabric/markdown/renderer.py`: deterministic Markdown rendering from schema plus JSON data.
- `generation_fabric/markdown/registry.py`: registry of supported Markdown contract kinds and their canonical assets.
- `generation_fabric/markdown/contracts.py`: loads canonical Markdown contract assets and scaffolds example files.
- `generation_fabric/markdown/importer.py`: imports legacy Markdown into a schema plus JSON contract.

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

## Scripts

- `scripts/generate_table_showcase.py`: portable Python generator for the table showcase example.

## Tests

- `tests/test_json_schema_crud.py`: CLI-level and end-to-end coverage for schema, inference, scaffolding, and Markdown generation.
