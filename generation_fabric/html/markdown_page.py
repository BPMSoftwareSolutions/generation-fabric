"""Markdown-to-HTML projection for contract-backed reports."""

from __future__ import annotations

from functools import lru_cache
from html import escape as html_escape
import json
import re
from pathlib import Path
from typing import Any

from generation_fabric.exceptions import SchemaError

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = PACKAGE_DIR / "templates" / "observability.html"
CSS_PATH = PACKAGE_DIR / "assets" / "observability.css"
SCRIPT_PATH = PACKAGE_DIR / "assets" / "observability-playback.js"


@lru_cache(maxsize=1)
def _load_asset(path: Path) -> str:
    """Load a text asset from the package tree."""

    if not path.exists():
        raise SchemaError(f"missing HTML asset: {path}")
    return path.read_text(encoding="utf-8")


def _escape_text(value: Any) -> str:
    """Escape text for HTML content."""

    return html_escape("" if value is None else str(value), quote=False)


def _escape_attr(value: Any) -> str:
    """Escape text for an HTML attribute value."""

    return html_escape("" if value is None else str(value), quote=True)


def _safe_json_script(value: Any) -> str:
    """Serialize JSON safely for embedding inside a script tag."""

    text = json.dumps(value, ensure_ascii=False, indent=2)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _render_inline(text: str) -> str:
    """Render a small subset of inline Markdown to HTML."""

    if not text:
        return ""

    code_spans: list[str] = []

    def code_replacement(match: re.Match[str]) -> str:
        code_spans.append(f"<code>{_escape_text(match.group(1))}</code>")
        return f"@@CODE_{len(code_spans) - 1}@@"

    text = re.sub(r"`([^`]+)`", code_replacement, text)
    text = _escape_text(text)

    def link_replacement(match: re.Match[str]) -> str:
        label = _escape_text(match.group(1))
        href = _escape_attr(match.group(2))
        return f'<a href="{href}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_replacement, text)
    text = re.sub(r"\*\*([^*]+)\*\*", lambda match: f"<strong>{_escape_text(match.group(1))}</strong>", text)
    text = re.sub(r"@@CODE_(\d+)@@", lambda match: code_spans[int(match.group(1))], text)
    return text


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+\S", line))


def _is_fence(line: str) -> bool:
    return line.strip().startswith("```")


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*[-*]\s+\S", line))


def _is_ordered_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*\d+\.\s+\S", line))


def _is_blockquote(line: str) -> bool:
    return line.lstrip().startswith(">")


def _is_table_row(line: str) -> bool:
    return "|" in line and line.strip().startswith("|")


def _is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|").strip()
    if not stripped:
        return False
    parts = [part.strip() for part in stripped.split("|")]
    return all(re.fullmatch(r":?-{3,}:?", part) for part in parts if part)


def _split_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    text = text.replace(r"\|", "\u0000")
    cells = [cell.strip().replace("\u0000", "|") for cell in text.split("|")]
    return cells


def _render_table(lines: list[str]) -> str:
    """Render a Markdown table into HTML."""

    if len(lines) < 2:
        return ""

    header = _split_table_row(lines[0])
    body_rows = [row for row in lines[2:] if _is_table_row(row)]
    if not header:
        return ""

    rendered = [
        '<table class="markdown-table">',
        "  <thead>",
        "    <tr>",
        *[f"      <th>{_render_inline(cell)}</th>" for cell in header],
        "    </tr>",
        "  </thead>",
    ]
    if body_rows:
        rendered.extend(["  <tbody>"])
        for row in body_rows:
            cells = _split_table_row(row)
            rendered.extend(
                [
                    "    <tr>",
                    *[f"      <td>{_render_inline(cell)}</td>" for cell in cells],
                    "    </tr>",
                ]
            )
        rendered.append("  </tbody>")
    rendered.append("</table>")
    return "\n".join(rendered)


def _render_list(lines: list[str], ordered: bool) -> str:
    """Render a Markdown list into HTML."""

    tag = "ol" if ordered else "ul"
    items: list[str] = []
    for line in lines:
        match = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.*)$", line)
        if not match:
            continue
        items.append(f"  <li>{_render_inline(match.group(1).strip())}</li>")
    if not items:
        return ""
    return "\n".join([f"<{tag} class=\"markdown-list\">", *items, f"</{tag}>"])


def _render_blockquote(lines: list[str]) -> str:
    """Render a Markdown blockquote into HTML."""

    text_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(">"):
            stripped = stripped[1:]
            if stripped.startswith(" "):
                stripped = stripped[1:]
        text_lines.append(stripped.rstrip())
    text = "\n".join(text_lines).strip()
    if not text:
        return ""
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]
    body = "\n".join(f"  <p>{_render_inline(paragraph.replace(chr(10), ' '))}</p>" for paragraph in paragraphs)
    return "\n".join(["<blockquote class=\"markdown-blockquote\">", body, "</blockquote>"])


def _render_code_block(code: str, language: str, diagram_index: int) -> str:
    """Render a fenced code block into HTML."""

    language = language.strip().lower()
    escaped_code = _escape_text(code.rstrip())
    if language == "mermaid":
        return "\n".join(
            [
                f'<div class="diagram-shell" data-diagram-index="{diagram_index}">',
                '  <details class="diagram-source" open>',
                '    <summary>Mermaid source</summary>',
                f'    <pre class="mermaid-source"><code>{escaped_code}</code></pre>',
                "  </details>",
                f'  <div class="mermaid" data-diagram-index="{diagram_index}">{escaped_code}</div>',
                "</div>",
            ]
        )

    language_attr = f' data-language="{_escape_attr(language)}"' if language else ""
    return "\n".join(
        [
            f'<pre class="markdown-code"{language_attr}><code>{escaped_code}</code></pre>',
        ]
    )


def _render_paragraph(lines: list[str]) -> str:
    """Render a paragraph block into HTML."""

    text = " ".join(line.strip() for line in lines if line.strip()).strip()
    return f"<p class=\"markdown-paragraph\">{_render_inline(text)}</p>" if text else ""


def _render_markdown_fragment(markdown: str) -> tuple[str, int]:
    """Render Markdown into HTML fragments and count Mermaid diagrams."""

    lines = markdown.splitlines()
    blocks: list[str] = []
    index = 0
    diagram_index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if _is_fence(line):
            language = line.strip()[3:].strip()
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not _is_fence(lines[index]):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            if language.lower() == "mermaid":
                diagram_index += 1
            blocks.append(_render_code_block("\n".join(code_lines), language, diagram_index if language.lower() == "mermaid" else 0))
            continue

        if _is_heading(line):
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            assert heading_match is not None
            heading_level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            blocks.append(f"<h{heading_level} class=\"markdown-heading\">{_render_inline(heading_text)}</h{heading_level}>")
            index += 1
            continue

        if _is_table_row(line) and index + 1 < len(lines) and _is_table_separator(lines[index + 1]):
            table_lines = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and _is_table_row(lines[index]):
                table_lines.append(lines[index])
                index += 1
            table_html = _render_table(table_lines)
            if table_html:
                blocks.append(table_html)
            continue

        if _is_blockquote(line):
            quote_lines = [line]
            index += 1
            while index < len(lines) and _is_blockquote(lines[index]):
                quote_lines.append(lines[index])
                index += 1
            blockquote_html = _render_blockquote(quote_lines)
            if blockquote_html:
                blocks.append(blockquote_html)
            continue

        if _is_ordered_list_item(line):
            list_lines = [line]
            index += 1
            while index < len(lines) and _is_ordered_list_item(lines[index]):
                list_lines.append(lines[index])
                index += 1
            blocks.append(_render_list(list_lines, ordered=True))
            continue

        if _is_list_item(line):
            list_lines = [line]
            index += 1
            while index < len(lines) and _is_list_item(lines[index]):
                list_lines.append(lines[index])
                index += 1
            blocks.append(_render_list(list_lines, ordered=False))
            continue

        paragraph_lines = [line]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            if not next_line.strip():
                break
            if (
                _is_heading(next_line)
                or _is_fence(next_line)
                or _is_table_row(next_line)
                or _is_blockquote(next_line)
                or _is_list_item(next_line)
                or _is_ordered_list_item(next_line)
            ):
                break
            paragraph_lines.append(next_line)
            index += 1
        paragraph_html = _render_paragraph(paragraph_lines)
        if paragraph_html:
            blocks.append(paragraph_html)

    fragment = "\n".join(blocks)
    return fragment, diagram_index


def _render_page_shell(body_html: str, panel_html: str, body_class: str) -> str:
    """Render the shared observability page shell."""

    if panel_html.strip():
        return "\n".join(
            [
                '<main class="observability-page">',
                "  <aside class=\"execution-panel\">",
                panel_html.rstrip(),
                "  </aside>",
                "  <article class=\"markdown-body\">",
                body_html,
                "  </article>",
                "</main>",
            ]
        )
    return "\n".join(
        [
            f'<main class="{body_class}">',
            "  <article class=\"markdown-body\">",
            body_html,
            "  </article>",
            "</main>",
        ]
    )


def _render_template(values: dict[str, str]) -> str:
    """Fill the observability template with the provided values."""

    template = _load_asset(TEMPLATE_PATH)
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def render_markdown_html_document(
    markdown: str,
    *,
    title: str = "",
    observability_data: dict[str, Any] | None = None,
    theme: str = "light",
) -> str:
    """Render a Markdown report as a standalone HTML document."""

    fragment, _diagram_count = _render_markdown_fragment(markdown)
    observability_data = observability_data or {}
    playback_json = _safe_json_script(observability_data.get("playback", {}))
    panel_html = str(observability_data.get("panel_html", "") or "")
    body_class = "observability-page" if panel_html.strip() else "markdown-page"
    resolved_title = title.strip() or str(observability_data.get("title", "")).strip() or "Document"
    page_shell = _render_page_shell(fragment, panel_html, body_class)

    return _render_template(
        {
            "TITLE": _escape_text(resolved_title),
            "THEME": _escape_attr(theme),
            "BODY_CLASS": _escape_attr(body_class),
            "CSS": _load_asset(CSS_PATH),
            "PAGE_SHELL": page_shell,
            "PLAYBACK_JSON": playback_json,
            "SCRIPT": _load_asset(SCRIPT_PATH),
        }
    )


__all__ = ["render_markdown_html_document"]
