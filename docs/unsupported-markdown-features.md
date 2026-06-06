# Markdown Features Not Yet Modeled as Structured Nodes

This document lists Markdown constructs that the current importer and renderer do not model as first-class contract data.

Important nuance:

- many of these constructs can still be preserved as raw or plain text
- the gap is structured editing, validation, and semantic round-tripping
- if a feature is only being passed through, that is often already good enough for migration

It is intentionally manual so we can judge where the generation fabric should invest next.

## What The Fabric Supports Today

- headings
- paragraphs
- blockquotes
- ordered lists
- unordered lists
- fenced code blocks
- tables
- contract-driven sections built from JSON Schema plus JSON data

## What It Does Not Model Yet As First-Class Structure

| Feature | Example | Current behavior | Notes |
| --- | --- | --- | --- |
| Inline HTML | `<details><summary>More</summary><p>Hidden content.</p></details>` | Usually preserved as raw text | Useful when Markdown needs collapsible UI or custom markup |
| Footnotes | `This sentence has a note.[^1]` | Usually preserved as text | The reference and definition are not modeled separately |
| Task lists | `- [ ] Draft schema` | Usually preserved as list text | Checkbox state is not represented as a structured field |
| Nested lists | `- Parent\n  - Child` | Usually preserved as text, but not as nested node structure | Hierarchy is not represented as nested list nodes |
| Definition lists | `Term\n: Definition` | Usually preserved as text | No term/definition contract exists |
| Admonitions | `!!! note` or `> [!NOTE]` | Usually preserved as block text | Flavor-specific syntax is not recognized |
| HTML tables | `<table>...</table>` | Usually preserved as text | The fabric only models Markdown table syntax today |
| Math | `$x^2$` or `$$x^2$$` | Usually preserved as text | No math parser or renderer exists |
| Embedded media | `<img>`, `<iframe>`, `<video>` | Usually preserved as text | These are not modeled as structured assets |

## Inline HTML Example

```markdown
<details>
  <summary>Expand me</summary>
  <p>This is HTML, not Markdown structure.</p>
</details>
```

Why this matters for structured editing:

- the current importer may keep the content as text
- the current renderer would not reconstruct a semantic HTML tree
- round-tripping becomes lossy if the source relies on HTML semantics rather than plain text preservation

## Footnote Example

```markdown
Here is a sentence with a footnote.[^1]

[^1]: Footnotes are not modeled yet.
```

Why this matters for structured editing:

- the reference and definition are not linked in the current contract model
- the importer does not create a footnote node
- the renderer cannot emit a dedicated footnote section

## Recommendation

If we decide to invest further, the most practical next candidates are:

1. task lists
2. footnotes
3. nested lists with true hierarchy
4. inline HTML preservation as raw blocks

Those features are common enough that they would improve migration fidelity without forcing us into a full Markdown parser immediately.

## Generated Companion

The same ideas are demonstrated in [examples/raw-sections-showcase.md](../examples/raw-sections-showcase.md), which is generated from JSON Schema plus JSON data and preserves these raw Markdown sections as editable content.
