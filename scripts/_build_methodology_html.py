"""
Rebuild docs/hazard_methodology_comparison.html from the markdown source,
adding a sidebar navigation panel auto-generated from H2/H3 headings.

Workflow:
  1. pandoc docs/hazard_methodology_comparison.md -t html5 -> body fragment
  2. Parse H2 and H3 headings (with their pandoc-assigned id attrs)
  3. Wrap body in custom template with sidebar nav + CSS

Usage:
  pandoc docs/hazard_methodology_comparison.md -t html5 -o /tmp/body.html
  python scripts/_build_methodology_html.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs" / "hazard_methodology_comparison.md"
OUT_HTML = ROOT / "docs" / "hazard_methodology_comparison.html"
TMP = ROOT / "_methodology_body.tmp.html"


def run_pandoc() -> str:
    subprocess.run(
        ["pandoc", str(MD), "-t", "html5", "--syntax-highlighting=none", "-o", str(TMP)],
        check=True,
    )
    return TMP.read_text(encoding="utf-8")


HEADING_RE = re.compile(r'<(h[23])\s+id="([^"]+)"[^>]*>(.*?)</\1>', re.DOTALL)


def build_nav(body: str) -> str:
    items: list[str] = []
    current_h2 = None
    for m in HEADING_RE.finditer(body):
        level, hid, raw = m.group(1), m.group(2), m.group(3)
        text = re.sub(r"<[^>]+>", "", raw).strip()
        if level == "h2":
            if current_h2 is not None:
                items.append("</div>")
            label = text if len(text) <= 60 else text[:57] + "…"
            items.append(f'<a href="#{hid}" class="nav-h2">{label}</a>')
            items.append(f'<div class="nav-h3-group" data-parent="{hid}">')
            current_h2 = hid
        elif level == "h3" and current_h2 is not None:
            label = text if len(text) <= 55 else text[:52] + "…"
            items.append(f'<a href="#{hid}" class="nav-h3">{label}</a>')
    if current_h2 is not None:
        items.append("</div>")
    return "\n".join(items)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ASEAN Multi-Hazard Flood Modelling — Open Methodology</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #f5f6fa;
    --surface: #ffffff;
    --text: #1a1a2e;
    --text-muted: #4a4a6a;
    --border: #dde1f0;
    --accent: #3b5bdb;
    --nav-bg: #1a1a2e;
    --nav-text: #c8ccdf;
    --nav-text-dim: #7c82a8;
    --nav-text-bright: #ffffff;
    --nav-active: #3b5bdb;
    --nav-w: 280px;
    --radius: 6px;
    --mono: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    --sans: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  }

  html { scroll-behavior: smooth; }
  body {
    font-family: var(--sans);
    font-size: 14.5px;
    line-height: 1.65;
    color: var(--text);
    background: var(--bg);
  }

  /* Sidebar nav */
  nav#toc {
    position: fixed;
    top: 0; left: 0;
    width: var(--nav-w);
    height: 100vh;
    overflow-y: auto;
    background: var(--nav-bg);
    color: var(--nav-text);
    padding: 22px 0 40px;
    z-index: 100;
    border-right: 1px solid #2e3155;
  }
  nav#toc .nav-header {
    padding: 0 18px 14px;
    border-bottom: 1px solid #2e3155;
    margin-bottom: 12px;
  }
  nav#toc .nav-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--nav-text-bright);
    margin-bottom: 4px;
  }
  nav#toc .nav-subtitle {
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--nav-text-dim);
  }
  nav#toc a {
    display: block;
    text-decoration: none;
    color: var(--nav-text);
    border-left: 3px solid transparent;
    transition: all .15s;
  }
  nav#toc a.nav-h2 {
    padding: 7px 16px 7px 15px;
    font-size: 12.5px;
    font-weight: 600;
    color: #d6d9ec;
    margin-top: 4px;
  }
  nav#toc a.nav-h2:hover {
    color: var(--nav-text-bright);
    background: rgba(255,255,255,0.04);
    border-left-color: var(--nav-active);
  }
  nav#toc a.nav-h2.active {
    color: var(--nav-text-bright);
    background: rgba(59,91,219,0.18);
    border-left-color: var(--nav-active);
  }
  nav#toc a.nav-h3 {
    padding: 4px 16px 4px 30px;
    font-size: 11.5px;
    color: #9da3c4;
    line-height: 1.4;
  }
  nav#toc a.nav-h3:hover {
    color: var(--nav-text-bright);
    background: rgba(255,255,255,0.03);
  }
  nav#toc a.nav-h3.active {
    color: var(--nav-text-bright);
    background: rgba(59,91,219,0.12);
    border-left-color: var(--nav-active);
  }
  nav#toc .nav-h3-group { margin-bottom: 2px; }

  /* Main content */
  main {
    margin-left: var(--nav-w);
    padding: 36px 48px 80px;
    max-width: calc(1100px + var(--nav-w));
  }
  main > * { max-width: 1000px; }

  h1 {
    font-size: 28px;
    margin-bottom: 14px;
    line-height: 1.25;
    color: var(--text);
    border-bottom: 3px solid var(--accent);
    padding-bottom: 10px;
  }
  h2 {
    font-size: 22px;
    margin: 36px 0 14px;
    line-height: 1.3;
    color: var(--text);
    border-bottom: 2px solid var(--border);
    padding-bottom: 6px;
    scroll-margin-top: 16px;
  }
  h3 {
    font-size: 17.5px;
    margin: 26px 0 10px;
    color: var(--text);
    scroll-margin-top: 16px;
  }
  h4 {
    font-size: 15px;
    margin: 18px 0 8px;
    color: var(--text-muted);
  }
  p { margin: 0 0 12px; }
  ul, ol { margin: 0 0 14px 22px; }
  li { margin: 3px 0; }

  blockquote {
    margin: 14px 0;
    padding: 12px 18px;
    background: #f0f4ff;
    border-left: 4px solid var(--accent);
    border-radius: 0 var(--radius) var(--radius) 0;
    color: var(--text-muted);
  }

  code {
    font-family: var(--mono);
    font-size: 0.88em;
    background: #eef0fa;
    padding: 1.5px 5px;
    border-radius: 3px;
    color: #2a2a55;
  }
  pre {
    background: #1a1a2e;
    color: #d6d9ec;
    padding: 14px 18px;
    border-radius: var(--radius);
    overflow-x: auto;
    margin: 14px 0;
    font-size: 12.5px;
    line-height: 1.5;
  }
  pre code { background: transparent; padding: 0; color: inherit; font-size: inherit; }

  table {
    border-collapse: collapse;
    margin: 16px 0;
    background: var(--surface);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(26,26,46,.05);
    font-size: 13.5px;
    width: 100%;
  }
  th, td {
    text-align: left;
    padding: 9px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  th {
    background: #eef0fa;
    color: var(--text);
    font-weight: 600;
    font-size: 13px;
  }
  tr:last-child td { border-bottom: 0; }
  tr:hover td { background: #fafbff; }

  hr { border: 0; border-top: 1px solid var(--border); margin: 30px 0; }
  a { color: var(--accent); }
  a:hover { text-decoration: none; }
  strong, b { color: var(--text); font-weight: 600; }

  nav#toc::-webkit-scrollbar { width: 8px; }
  nav#toc::-webkit-scrollbar-track { background: transparent; }
  nav#toc::-webkit-scrollbar-thumb { background: #2e3155; border-radius: 4px; }
  nav#toc::-webkit-scrollbar-thumb:hover { background: #3e4275; }

  @media print {
    nav#toc { display: none; }
    main { margin-left: 0; padding: 20px; }
  }

  @media (max-width: 900px) {
    nav#toc {
      transform: translateX(-100%);
      transition: transform .25s;
    }
    nav#toc.open { transform: translateX(0); }
    main { margin-left: 0; padding: 20px; }
    #nav-toggle { display: block; }
  }

  #nav-toggle {
    display: none;
    position: fixed;
    top: 12px; left: 12px;
    z-index: 101;
    background: var(--nav-bg);
    color: var(--nav-text-bright);
    border: 0;
    padding: 8px 12px;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 14px;
  }
</style>
</head>
<body>

<button id="nav-toggle" aria-label="Toggle navigation" onclick="document.getElementById('toc').classList.toggle('open')">&#9776; Menu</button>

<nav id="toc" aria-label="Document navigation">
  <div class="nav-header">
    <div class="nav-title">ASEAN Flood Methodology</div>
    <div class="nav-subtitle">Updated 2026-05-14</div>
  </div>
__NAV_PLACEHOLDER__
</nav>

<main>
__BODY_PLACEHOLDER__
</main>

<script>
(function() {
  const links = Array.from(document.querySelectorAll('#toc a'));
  const targets = links
    .map(a => ({ link: a, target: document.getElementById(a.getAttribute('href').slice(1)) }))
    .filter(x => x.target);

  function onScroll() {
    let active = null;
    const threshold = window.innerHeight * 0.3;
    for (const { link, target } of targets) {
      const rect = target.getBoundingClientRect();
      if (rect.top <= threshold) active = link;
      else break;
    }
    links.forEach(l => l.classList.remove('active'));
    if (active) {
      active.classList.add('active');
      const nav = document.getElementById('toc');
      const navRect = nav.getBoundingClientRect();
      const linkRect = active.getBoundingClientRect();
      if (linkRect.top < navRect.top + 60 || linkRect.bottom > navRect.bottom - 60) {
        active.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();
</script>

</body>
</html>
"""


def main() -> None:
    body = run_pandoc()
    nav = build_nav(body)
    out = TEMPLATE.replace("__NAV_PLACEHOLDER__", nav).replace("__BODY_PLACEHOLDER__", body)
    OUT_HTML.write_text(out, encoding="utf-8")
    n_h2 = nav.count('class="nav-h2"')
    n_h3 = nav.count('class="nav-h3"')
    print(f"Wrote {OUT_HTML.relative_to(ROOT)}: {len(out):,} chars; nav has {n_h2} H2 + {n_h3} H3 entries")
    TMP.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
