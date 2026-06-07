"""Build a self-contained, openable showcase of the ASCII-to-web pipeline.

One file tells the whole story: the ASCII sketch, the SVG blueprint, and the live
rendered dashboard (HTML + CSS inlined), plus the coherence result. This is the
"something to show" artifact — open it in a browser.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from generation_fabric.core.io import write_text_file_atomic
from generation_fabric.css.web_renderer import render_web_css_document
from generation_fabric.html.web_renderer import render_web_html_document
from generation_fabric.layout.ascii_sketch import build_zone_document
from generation_fabric.layout.web_coherence import audit_web_coherence
from generation_fabric.layout.web_contract import build_web_page_contract
from generation_fabric.svg.web_renderer import render_web_svg_document

EXAMPLES = REPO_ROOT / "examples"
PAGE_ID = "operations-dashboard"
OUTPUT_PATH = EXAMPLES / f"{PAGE_ID}.showcase.html"

SHOWCASE_CHROME = """\
  :root { color-scheme: light dark; }
  body.gf-showcase { margin: 0; font-family: system-ui, sans-serif; background: #0b1220; color: #e2e8f0; }
  .showcase-header { padding: 28px 32px 8px; }
  .showcase-header h1 { margin: 0 0 6px; font-size: 1.6rem; }
  .showcase-header p { margin: 0; color: #94a3b8; }
  .showcase-badge { display: inline-block; margin-top: 12px; padding: 4px 12px; border-radius: 999px;
    background: #14532d; color: #bbf7d0; font-weight: 600; font-size: 0.85rem; }
  .showcase-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px 32px 40px; }
  .panel { background: #ffffff; color: #1f2933; border-radius: 12px; padding: 18px 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
  .panel > h2 { margin: 0 0 12px; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.06em; color: #475569; }
  .panel.live { grid-column: 1 / -1; }
  pre.ascii { margin: 0; font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px;
    line-height: 1.25; overflow-x: auto; color: #0f172a; }
  .blueprint svg { width: 100%; height: auto; }
  .live .gf-web-page { padding: 0; }
"""


def main() -> int:
    sketch = (EXAMPLES / f"{PAGE_ID}.ascii.md").read_text(encoding="utf-8").rstrip("\n")
    zones = build_zone_document(sketch, page_id=PAGE_ID, title="Operations Dashboard")
    contract = build_web_page_contract(zones)

    css = render_web_css_document(contract)
    svg = render_web_svg_document(contract)
    full_html = render_web_html_document(contract)
    body_inner = full_html.split('<body class="gf-web">', 1)[1].rsplit("</body>", 1)[0].strip()

    report = audit_web_coherence(contract)
    component_types = ", ".join(c["component_type"] for c in contract["components"])

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ASCII to Web — Operations Dashboard</title>
  <style>
{SHOWCASE_CHROME}
/* --- generated page stylesheet (inlined) --- */
{css}
  </style>
</head>
<body class="gf-showcase">
  <header class="showcase-header">
    <h1>ASCII &rarr; Web &mdash; Operations Dashboard</h1>
    <p>One ASCII sketch becomes component intent, a web contract, and component-aware HTML, CSS, and SVG &mdash; all deterministic.</p>
    <p class="showcase-badge">Coherence {report['score']:.0f}% &middot; {len(contract['components'])} components: {escape(component_types)}</p>
  </header>
  <div class="showcase-grid">
    <section class="panel">
      <h2>1 &middot; ASCII sketch (input)</h2>
      <pre class="ascii">{escape(sketch)}</pre>
    </section>
    <section class="panel blueprint">
      <h2>2 &middot; SVG blueprint</h2>
      {svg.strip()}
    </section>
    <section class="panel live">
      <h2>3 &middot; Rendered page (HTML + CSS)</h2>
      {body_inner}
    </section>
  </div>
</body>
</html>
"""
    write_text_file_atomic(OUTPUT_PATH, document)
    print(f"generated: {OUTPUT_PATH}")
    print(f"{report['summary']} ({report['score']:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
