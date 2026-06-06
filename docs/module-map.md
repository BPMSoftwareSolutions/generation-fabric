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

## Schema

- `generation_fabric/schema/document.py`: schema creation and combinator attachment.
- `generation_fabric/schema/inference.py`: schema inference from sample JSON.
- `generation_fabric/schema/validation.py`: schema and instance validation.

## Markdown

- `generation_fabric/markdown/renderer.py`: deterministic Markdown rendering from schema plus JSON data.
- `generation_fabric/markdown/contracts.py`: canonical Markdown contract scaffolding and examples.

## Example Assets

- `examples/release-notes.schema.json`: canonical schema contract.
- `examples/release-notes.json`: canonical source data.
- `examples/release-notes.md`: canonical rendered Markdown output.

## Tests

- `tests/test_json_schema_crud.py`: CLI-level and end-to-end coverage for schema, inference, scaffolding, and Markdown generation.

