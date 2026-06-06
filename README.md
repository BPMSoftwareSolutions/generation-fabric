# Generation Fabric

Generation Fabric is a small contract-driven compiler pipeline for structured documents.

The core idea is simple:

`JSON Schema -> validate -> JSON content -> render -> Markdown`

That lets us keep each responsibility isolated while still composing them into one deterministic workflow.

## What Lives Here

- `json_schema_crud.py` is the compatibility entrypoint for the CLI.
- `generation_fabric/cli.py` is orchestration only.
- `generation_fabric/core/` holds shared JSON and IO helpers.
- `generation_fabric/json_documents/` handles generic JSON tree CRUD and schema-driven sample generation.
- `generation_fabric/schema/` owns schema creation, inference, and validation.
- `generation_fabric/markdown/` owns Markdown rendering, the contract registry, contract scaffolding, and Markdown import.
- `examples/` contains canonical schema, JSON, and Markdown artifacts.
- `scripts/generate_table_showcase.py` is the portable Python generator for the table showcase example.
- `tests/` contains end-to-end coverage for the published behaviors.

If you want the full taxonomy, see [docs/module-map.md](docs/module-map.md).
If you want the implementation plan, see [docs/compiler-pipeline-roadmap.md](docs/compiler-pipeline-roadmap.md).

## Why It Exists

This repository is built around a few strict rules:

- each module has one responsibility
- file names should tell the implementation story
- schema documents define the contract
- JSON documents provide the structured source data
- Markdown is a derived artifact, not the source of truth
- examples should be real, committed artifacts that prove the pipeline works

That keeps the system coherent as it grows from simple file operations into a more general generation fabric.

## Quick Start

Run the CLI from the repository root:

```powershell
python json_schema_crud.py --help
```

Create a new schema:

```powershell
python json_schema_crud.py new --output user.schema.json --title User
```

Read or mutate a schema:

```powershell
python json_schema_crud.py read --file user.schema.json
python json_schema_crud.py create --file user.schema.json --pointer /properties/name --value '{"type":"string"}'
python json_schema_crud.py update --file user.schema.json --pointer /properties/name/type --value string
python json_schema_crud.py delete --file user.schema.json --pointer /properties/name
```

Validate a schema or an instance:

```powershell
python json_schema_crud.py validate --file user.schema.json
python json_schema_crud.py validate --file user.schema.json --instance '"Ada"'
python json_schema_crud.py validate --file user.schema.json --instance-file sample.json
```

Infer a schema from sample JSON:

```powershell
python json_schema_crud.py infer --sample-file sample.json --output inferred.schema.json --title Users
```

Render Markdown from a schema contract and JSON data:

```powershell
python json_schema_crud.py markdown --schema examples/release-notes.schema.json --data-file examples/release-notes.json
```

Scaffold a ready-to-use Markdown contract:

```powershell
python json_schema_crud.py markdown-contract --directory examples --with-markdown
```

Import a legacy Markdown file into a schema plus JSON contract:

```powershell
python json_schema_crud.py markdown-import --file legacy.md --directory generated --with-markdown
```

Start the interactive schema shell:

```powershell
python json_schema_crud.py interactive
```

## CLI Surface

- `new`: create a brand-new schema file
- `read`: inspect a schema or any JSON Pointer path inside it
- `create`: add a new node
- `update`: replace an existing node
- `delete`: remove a node
- `validate`: validate a schema or a subschema, plus an optional instance
- `infer`: build a schema from sample JSON
- `json-sample`: generate a JSON sample from a schema
- `json-read`: inspect a JSON document or any JSON Pointer path inside it
- `json-create`: add a new node to a JSON document
- `json-update`: replace an existing node in a JSON document
- `json-delete`: remove a node from a JSON document
- `oneof`: attach a `oneOf` combinator
- `anyof`: attach an `anyOf` combinator
- `markdown`: render Markdown from a schema plus JSON data
- `markdown-contract`: scaffold a canonical document contract
- `markdown-import`: convert a legacy Markdown file into a schema plus JSON contract
- `interactive`: use the tiny schema shell for quick experiments

## Canonical Example

The repository includes a release-notes contract that demonstrates the full pipeline:

- [examples/release-notes.schema.json](examples/release-notes.schema.json)
- [examples/release-notes.json](examples/release-notes.json)
- [examples/release-notes.md](examples/release-notes.md)

Those files serve as a golden example for how the contract, content, and rendered output should line up.

## Testing

The repository uses standard-library unit tests:

```powershell
python -m unittest discover -s tests -v
```

The tests cover:

- schema creation and CRUD
- schema validation
- schema inference
- generic JSON document CRUD
- JSON sample scaffolding
- `oneOf` and `anyOf`
- Markdown rendering
- contract scaffolding
- the interactive shell

## Design Principle

The long-term direction is to keep the pipeline layered and deterministic:

1. define the contract with JSON Schema
2. shape content with JSON documents
3. render Markdown from structured data
4. add richer document models only when editable round-tripping is required

That is the generation fabric: a coherent set of modules that can scale without turning into one giant monolith.
