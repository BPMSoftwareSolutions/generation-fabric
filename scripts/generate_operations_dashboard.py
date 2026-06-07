"""Generate the operations-dashboard ASCII-to-web example using the fabric.

This authors an aligned ASCII sketch that uses the component dialect, parses it
into a zone taxonomy, extracts component intent, and writes both sidecars. It is
the first milestone of the ASCII-to-web pipeline: a page with a form, a gauge, a
data grid, and a chart.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from generation_fabric.core.io import write_json_file_atomic, write_text_file_atomic
from generation_fabric.css.web_renderer import render_web_css_document
from generation_fabric.html.web_renderer import render_web_html_document
from generation_fabric.layout.ascii_sketch import build_zone_document
from generation_fabric.layout.component_intent import build_component_intent_document
from generation_fabric.layout.web_coherence import write_web_coherence_report
from generation_fabric.layout.web_contract import build_web_page_contract
from generation_fabric.svg.web_renderer import render_web_svg_document

OUTPUT_DIR = REPO_ROOT / "examples"
PAGE_ID = "operations-dashboard"
TITLE = "Operations Dashboard"

WIDTH = 60
DIVIDER = 28
INNER = WIDTH - 2          # 58
LEFT_W = DIVIDER - 1       # 27
RIGHT_W = WIDTH - DIVIDER - 2  # 30

# Each band is ("full", [lines]) or ("split", [left_lines], [right_lines]).
BANDS = [
    ("full", ["OPERATIONS DASHBOARD [page]"]),
    (
        "split",
        ["FILTERS [form]", "fields: date,status,team", "action: apply_filters"],
        ["DELIVERY HEALTH [gauge]", "value: delivery_health", "min: 0 max: 100"],
    ),
    ("full", ["RUNS [data_grid]", "data: runs[]", "columns: id,status,owner,duration"]),
    ("full", ["SUCCESS TREND [chart_line]", "x: day y: success_rate"]),
]


def _full_row(text: str) -> str:
    return "|" + (" " + text).ljust(INNER) + "|"


def _split_row(left: str, right: str) -> str:
    return "|" + (" " + left).ljust(LEFT_W) + "|" + (" " + right).ljust(RIGHT_W) + "|"


def _divider(interior: bool) -> str:
    if interior:
        return "+" + "-" * LEFT_W + "+" + "-" * RIGHT_W + "+"
    return "+" + "-" * INNER + "+"


def _is_split(band) -> bool:
    return band[0] == "split"


def render_sketch() -> str:
    lines = [_divider(_is_split(BANDS[0]))]
    for index, band in enumerate(BANDS):
        if band[0] == "full":
            lines.extend(_full_row(line) for line in band[1])
        else:
            left_lines, right_lines = band[1], band[2]
            for row in range(max(len(left_lines), len(right_lines))):
                left = left_lines[row] if row < len(left_lines) else ""
                right = right_lines[row] if row < len(right_lines) else ""
                lines.append(_split_row(left, right))
        if index < len(BANDS) - 1:
            lines.append(_divider(_is_split(band) or _is_split(BANDS[index + 1])))
        else:
            lines.append(_divider(_is_split(band)))

    bad = [(i, len(line)) for i, line in enumerate(lines) if len(line) != WIDTH]
    assert not bad, bad
    return "\n".join(lines) + "\n"


def main() -> int:
    sketch = render_sketch()
    zones_document = build_zone_document(sketch, page_id=PAGE_ID, title=TITLE)
    components_document = build_component_intent_document(zones_document)
    web_contract = build_web_page_contract(zones_document, components_document)

    html = render_web_html_document(web_contract)
    css = render_web_css_document(web_contract)
    svg = render_web_svg_document(web_contract)

    sketch_path = OUTPUT_DIR / f"{PAGE_ID}.ascii.md"
    zones_path = OUTPUT_DIR / f"{PAGE_ID}.zones.json"
    components_path = OUTPUT_DIR / f"{PAGE_ID}.components.json"
    web_path = OUTPUT_DIR / f"{PAGE_ID}.web.json"
    html_path = OUTPUT_DIR / f"{PAGE_ID}.html"
    css_path = OUTPUT_DIR / f"{PAGE_ID}.css"
    svg_path = OUTPUT_DIR / f"{PAGE_ID}.svg"

    write_text_file_atomic(sketch_path, sketch)
    write_json_file_atomic(zones_path, zones_document)
    write_json_file_atomic(components_path, components_document)
    write_json_file_atomic(web_path, web_contract)
    write_text_file_atomic(html_path, html)
    write_text_file_atomic(css_path, css)
    write_text_file_atomic(svg_path, svg)

    coherence_paths, report = write_web_coherence_report(
        web_contract,
        output=str(OUTPUT_DIR / f"{PAGE_ID}.web-coherence.md"),
        overwrite=True,
    )

    written = [
        sketch_path, zones_path, components_path, web_path, html_path, css_path, svg_path,
        coherence_paths.markdown_path,
    ]
    print("generated: " + ", ".join(str(path) for path in written))
    types = [component["component_type"] for component in components_document["components"]]
    print(f"components: {', '.join(types)}")
    print(f"{report['summary']} ({report['score']:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
