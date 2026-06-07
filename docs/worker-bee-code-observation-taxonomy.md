# Worker Bee Code Observation Taxonomy

This document describes how the worker bee should document code in a way that is rich enough for architectural review while staying contract-based and deterministic.

The goal is not to dump raw AST or raw code into Markdown.
The goal is to turn source code into a human-readable inventory with anchors, responsibilities, and execution flow that reviewers can understand quickly.

## North Star

```text
source file
-> deterministic taxonomy scan
-> taxonomy
-> observation contract
-> JSON data
-> Mermaid sequence diagram
-> Markdown review artifact
```

The worker bee should be able to observe a Python file, identify the important execution paths, and generate a document that explains:

- what the file is responsible for
- which symbols matter
- who participates in the flow
- what each step does
- how the flow maps back to code anchors

## Deterministic Base Extraction

The first pass should be a script, not a model call.

That script should scan the source file and extract a base taxonomy that can be stored and reused before any AI review or enrichment happens.

The deterministic scan should capture:

- source file path
- module path
- file hash or freshness stamp
- class declarations
- function declarations
- method declarations
- signatures
- docstrings
- line anchors
- branch conditions
- call targets
- loop markers
- return points
- exception paths
- observed execution paths

If the script can get it from the file directly, it should write it into the taxonomy JSON document instead of asking the model to infer it later.

That turns the worker bee into a retrieval-driven consumer instead of a repeated reader.

## What The Taxonomy Represents

The taxonomy is the bridge between code structure and document structure.

It gives names to the things the worker bee observes:

- repository scope
- file scope
- symbol scope
- role scope
- execution-step scope
- reviewer-note scope

That is what keeps the output coherent.

## Human-Readable Anchors

Each observation should carry anchors that help a reviewer move between the document and the code.

Suggested anchor types:

- `repository_anchor`
- `file_anchor`
- `module_anchor`
- `class_anchor`
- `method_anchor`
- `function_anchor`
- `role_anchor`
- `responsibility_anchor`
- `flow_step_anchor`

These anchors should be readable first and machine-usable second.

Example:

```text
file: generation_fabric/worker_bee/planner.py
symbol: build_generation_packet
role: packet builder
responsibility: turn a brief into a deterministic packet
```

## Human-Readable Labels

The diagram should prefer human-readable labels over raw Python identifiers.

Good labels:

- `Packet Planner`
- `Provider Proposal`
- `Markdown Executor`
- `Sequence Diagram Renderer`
- `Schema Validation`

Less helpful labels:

- `build_generation_packet`
- `write_worker_bee_document`
- `collect_python_function_observations`

The raw symbol name still matters, but it should be stored as an anchor, not treated as the only label the reviewer sees.

## Sequence Diagram Conventions

The sequence diagram should show the execution flow with readable participants and notes.

Recommended conventions:

- participant names should be human readable
- aliases should be safe for Mermaid syntax
- notes should explain why the step matters
- call steps should read like action verbs
- branch markers should be called out explicitly

Example participant mapping:

```text
Caller -> Reader
build_generation_packet -> Packet Planner
build_provider_backed_generation_packet -> Provider Proposal Adapter
write_worker_bee_document -> Worker Bee Document Writer
```

Example note style:

- `note over Packet Planner: resolves a stable packet shape`
- `note over Worker Bee Document Writer: writes contract-backed artifacts only`

## Suggested Contract Fields

The code-observation contract should stay generated, not hand-stitched.

At a minimum, the schema and JSON data should carry:

- source file path
- module path
- file hash or freshness stamp
- shape name
- summary
- inventory of observed symbols
- participants
- execution paths
- notes

For a richer architecture-review output, add:

- taxonomy entries
- file anchors
- symbol anchors
- role descriptions
- responsibility descriptions
- condition text
- declaration metadata
- reviewer notes
- visual hints for badges or icons

## Contract Shape Example

The worker bee can generate a schema and JSON document that look conceptually like this:

```json
{
  "source_file": "generation_fabric/worker_bee/planner.py",
  "module_path": "generation_fabric.worker_bee.planner",
  "source_hash": "sha256:...",
  "shape": "sequence-diagram",
  "summary": "Observed the planner and its helper path.",
  "symbols": [
    {
      "name": "build_generation_packet",
      "kind": "function",
      "anchor": "generation_fabric/worker_bee/planner.py:42-108",
      "signature": "def build_generation_packet(...)",
      "docstring": "Build a deterministic generation packet from a brief."
    }
  ],
  "participants": [
    "Reader",
    "Packet Planner",
    "Strategy Builder"
  ],
  "execution_paths": [
    {
      "name": "build_generation_packet",
      "kind": "function",
      "file_anchor": "generation_fabric/worker_bee/planner.py",
      "method_anchor": "",
      "role_anchor": "packet planner",
      "responsibility_anchor": "turn a brief into a deterministic packet",
      "conditions": [
        {
          "kind": "if",
          "source_text": "if brief:",
          "meaning": "ensure the brief is not empty"
        }
      ],
      "notes": [
        "Normalizes the brief before planning.",
        "Uses the default migration strategy.",
        "Returns a contract-backed packet."
      ]
    }
  ]
}
```

The exact field names can evolve, but the principle should stay stable:

- the JSON contract is the source of truth
- the Markdown is rendered from that contract
- the diagram labels are generated from structured metadata
- branch conditions and declarations are captured in the taxonomy JSON before any model enrichment

## Icon And Badge Strategy

Mermaid sequence diagrams are best at text and flow, not icon-heavy decoration.

If we want visual decoration, we should model it as data first:

- `badge`
- `icon`
- `kind`
- `severity`
- `review_state`

Then the renderer can decide how to represent it:

- plain text label
- Markdown badge
- note callout
- legend entry

That keeps the representation contract-based instead of hard-coded.

## Review Workflow

This is the workflow we want for architecture review:

1. observe the source file
2. extract the taxonomy and anchors
3. generate the JSON contract
4. render the Mermaid and Markdown
5. review the narrative against the code
6. forecast the expected design changes
7. compare future code changes against the documented intent

Once the taxonomy JSON exists, the worker bee should prefer CRUD operations on that JSON over rereading the source file unless the file hash has changed.

That is how we reduce drift.

## Forecast Workflow

The same shape can support forward-looking documentation:

- expected code changes
- planned refactors
- future responsibilities
- file-level ownership changes
- architectural migration notes

That makes the document useful before and after implementation.

## Practical Rule

If a reviewer cannot answer these questions from the document, the taxonomy is too thin:

- who owns this flow?
- what responsibility does this symbol have?
- where does the execution start?
- what steps happen in the middle?
- what code path does this map back to?

## Relationship To The Existing Observation Command

The current `worker-bee-observe` command already establishes the shape-based contract.

This document describes the richer version of that contract:

- more readable labels
- more explicit anchors
- better reviewer notes
- room for taxonomy-driven diagrams and badges

## Design Rule

Keep the observation path contract-backed.

Do not hand-stitch the Markdown narrative, the taxonomy, or the diagram text.
Generate the schema, generate the JSON contract, and let the fabric render the document.
