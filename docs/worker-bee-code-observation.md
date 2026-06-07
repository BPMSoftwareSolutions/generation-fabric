# Worker Bee Code Observation

The worker bee now has a first supported code-observation shape: `sequence-diagram`.

That shape is a good fit for Python execution paths because it makes three things visible at once:

- the participants involved in the flow
- the order of calls and branch markers
- the resulting Mermaid diagram that can be rendered directly into Markdown

## Why Sequence Diagrams

Sequence diagrams are a strong default for code observation because they show execution as a story:

1. a caller invokes a function or method
2. the function calls helpers in order
3. branch markers make control flow visible
4. the worker bee renders the result as contract-backed Markdown

## CLI Entry Point

Use the observation command from the repository root:

```powershell
python json_schema_crud.py worker-bee-observe --source-file generation_fabric/worker_bee/planner.py --output generated/planner-observation.md
```

The command writes:

- a schema contract
- a JSON observation document
- the rendered Markdown file

## Design Rule

The shape should stay explicit.

If we add more shapes later, they should be named, contracted, and benchmarked the same way so the worker bee keeps generating structured output instead of ad-hoc text.
