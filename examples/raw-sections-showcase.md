# Raw Sections Showcase

A contract-driven example that keeps raw Markdown syntax editable as structured sections.

This example shows that raw Markdown syntax can still be captured as editable JSON sections.

## Inline HTML

Inline HTML can be preserved as raw Markdown text and edited through JSON.

<details>
  <summary>Expand me</summary>
  <p>Hidden content can stay in the Markdown source.</p>
</details>

- The raw block is preserved without inventing a new HTML model.
- The section remains editable through JSON CRUD operations.

## Footnotes

Footnote references and definitions can be preserved as raw Markdown text.

Here is a sentence with a footnote.[^1]

[^1]: Footnotes are captured as raw markdown text.

- The source remains easy to edit.
- The renderer does not need special footnote semantics to keep the text intact.

## Task Lists

Task list checkboxes can remain plain Markdown while still being tracked in JSON.

- [ ] Draft schema
- [x] Render output
- [ ] Verify round-trip

- Checkbox syntax stays visible in the output.
- The JSON layer can still update the section body atomically.

## Nested Lists

Nested list syntax can be preserved as raw Markdown content.

- Parent
  - Child
  - Another child
- Sibling

- The structure remains readable in source control.
- No custom nested-list model is required for pass-through use cases.

## Definition Lists

Definition list syntax can be carried through as raw text.

Term
: Definition
Another term
: Another definition

- The importer does not need to normalize this into a special shape.
- Editors can still update the text through CRUD operations.

## Admonitions

Flavor-specific admonition syntax can live inside a raw section.

> [!NOTE]
> This content is preserved as blockquote-style markdown.
> It can still be edited as raw text.

- The fabric can preserve the syntax even when it does not interpret it semantically.
- The source remains deterministic and diffable.

## HTML Tables

HTML table markup can be preserved as raw Markdown source when needed.

<table>
  <tr><th>Name</th><th>Value</th></tr>
  <tr><td>Alpha</td><td>1</td></tr>
</table>

- This keeps custom table layouts intact.
- It avoids forcing HTML into a simplified Markdown table model.

## Math

Inline and block math can remain raw source text in a Markdown section.

Euler said $e^{i\pi} + 1 = 0$ and display math can stay as plain text:
$$
x^2 + y^2 = z^2
$$

- Math delimiters stay visible in source.
- A richer math renderer can be added later if we choose to invest in it.

## Embedded Media

Images, iframes, and other embedded media can be preserved as raw content.

<img src="diagram.png" alt="Diagram" />
<iframe src="https://example.com/demo"></iframe>

- The section stays editable as raw Markdown text.
- Media semantics can be layered on later if needed.

> The section body can remain raw text while still being fully editable through JSON CRUD operations.
