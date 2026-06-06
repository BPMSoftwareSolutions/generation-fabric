# Table Showcase

A contract-driven example that demonstrates Markdown tables and structured document generation.

This example shows how the generation fabric can render tables from structured JSON.

| artifact | source | format | notes |
| --- | --- | --- | --- |
| Schema | json_schema_crud.py new | JSON Schema | Defines the contract |
| Sample JSON | json-sample | JSON | Generated from schema hints |
| Markdown | markdown | Markdown | Rendered deterministically |

1. Define the schema contract
2. Generate the JSON sample
3. Render Markdown from the sample

> The table is generated from JSON, and the JSON is generated from the schema.
