"""Render a Markdown document to a self-contained, mobile-friendly HTML file via pandoc.

Companion to scripts/_md_to_pdf.py. Produces a single file with no external requests:
all CSS is inline, there are no web fonts and no images. The only script is one inline
line that collapses the contents list on narrow viewports.

Responsive design (2026-08-10 rewrite; the previous version emitted a fixed-width A4
print stylesheet at 9.3pt that was unreadable on a phone):
  * fluid type via clamp(), so body text scales with viewport width;
  * every table wrapped in a horizontally scrollable container — wide parameter
    registers no longer force the whole page to scroll sideways;
  * code blocks scroll independently;
  * a collapsible table of contents built from the H2/H3 structure, open on desktop
    and closed on phones;
  * dark-mode support via prefers-color-scheme;
  * the A4 @page rules are retained inside @media print, so the print/PDF path is
    unchanged.

Pandoc (gfm -> html5 fragment) handles pipe tables, fenced code, blockquotes, lists;
the unicode maths glyphs render via the reader's system fonts. The leading HTML
draft-status comment in the .md is stripped.

Usage:
  python scripts/_md_to_html.py <input.md> [output.html] [--title="..."]
Defaults to docs/technical/model-documentation.md -> same stem .html.
"""
from __future__ import annotations

import html as _html
import re
import subprocess
import sys
from pathlib import Path

PANDOC = r"C:/Users/Daniel/AppData/Local/Pandoc/pandoc"

STYLE = """
*,*::before,*::after { box-sizing:border-box; }
:root{
  --ink:#1a1a1a; --muted:#5a6a66; --accent:#0f6e56; --accent-dk:#0f3d2e;
  --rule:#d6dedb; --tbl-rule:#c9d2cf; --tbl-head:#e7efec; --tbl-alt:#fafbfb;
  --code-bg:#eef2f1; --pre-bg:#f5f7f6; --pre-rule:#e0e6e4; --quote-bg:#f6f8f7;
  --bg:#fff;
}
@media (prefers-color-scheme: dark){
  :root{
    --ink:#e6e9e8; --muted:#9fb0ab; --accent:#4fbf9b; --accent-dk:#8fd9c2;
    --rule:#2b3532; --tbl-rule:#33403c; --tbl-head:#1c2a26; --tbl-alt:#161d1b;
    --code-bg:#1c2422; --pre-bg:#151b19; --pre-rule:#2b3532; --quote-bg:#161d1b;
    --bg:#0f1413;
  }
}
html{ -webkit-text-size-adjust:100%; }
body{
  font-family:"Segoe UI","Helvetica Neue",Arial,system-ui,sans-serif;
  font-size:clamp(15px, 0.95rem + 0.15vw, 17px);
  line-height:1.62; color:var(--ink); background:var(--bg);
  max-width:64rem; margin:0 auto; padding:1.5rem 1.15rem 4rem;
  overflow-wrap:break-word;
}
h1{ font-size:clamp(1.55rem,1.2rem + 1.6vw,2.1rem); line-height:1.22; margin:0 0 .4rem; color:var(--accent-dk); }
h2{ font-size:clamp(1.22rem,1.05rem + 0.8vw,1.5rem); line-height:1.3; margin:2.4rem 0 .6rem;
    padding-bottom:.25rem; border-bottom:2px solid var(--accent); color:var(--accent-dk); }
h3{ font-size:clamp(1.06rem,1rem + 0.4vw,1.2rem); margin:1.6rem 0 .4rem; color:var(--accent-dk); }
h4{ font-size:1rem; margin:1.2rem 0 .3rem; color:var(--muted); }
p,li{ margin:.55rem 0; }
ul,ol{ padding-left:1.35rem; }
blockquote{
  border-left:4px solid var(--accent); margin:1rem 0; padding:.6rem .9rem;
  color:var(--ink); background:var(--quote-bg); border-radius:0 6px 6px 0;
}
blockquote p:first-child{ margin-top:0; } blockquote p:last-child{ margin-bottom:0; }
code{ font-family:"Consolas","DejaVu Sans Mono",ui-monospace,monospace;
      font-size:.88em; background:var(--code-bg); padding:.1em .3em; border-radius:3px; }
pre{ background:var(--pre-bg); border:1px solid var(--pre-rule); border-radius:6px;
     padding:.7rem .8rem; font-size:.82rem; line-height:1.45; overflow-x:auto;
     -webkit-overflow-scrolling:touch; }
pre code{ background:none; padding:0; font-size:inherit; white-space:pre; }
/* tables: scroll the table, never the page */
.tw{ overflow-x:auto; -webkit-overflow-scrolling:touch; margin:.9rem 0;
     border:1px solid var(--tbl-rule); border-radius:6px; }
.tw table{ border-collapse:collapse; width:100%; min-width:34rem; font-size:.86rem; margin:0; }
.tw th,.tw td{ border:1px solid var(--tbl-rule); padding:.4rem .55rem;
               text-align:left; vertical-align:top; }
.tw th{ background:var(--tbl-head); font-weight:600; position:sticky; top:0; }
.tw tr:nth-child(even) td{ background:var(--tbl-alt); }
a{ color:var(--accent); text-decoration:none; } a:hover{ text-decoration:underline; }
strong{ color:var(--ink); font-weight:650; }
hr{ border:none; border-top:1px solid var(--rule); margin:2rem 0; }
/* collapsible contents */
#toc{ border:1px solid var(--rule); border-radius:8px; padding:.5rem .9rem; margin:1.5rem 0 2rem;
      background:var(--quote-bg); }
#toc summary{ cursor:pointer; font-weight:650; color:var(--accent-dk); padding:.25rem 0;
              font-size:1rem; }
#toc ol{ list-style:none; padding-left:0; margin:.6rem 0 .3rem; columns:2; column-gap:2rem; }
#toc li{ margin:.18rem 0; break-inside:avoid; font-size:.92rem; }
#toc li.sub{ padding-left:1rem; font-size:.86rem; }
#toc li.sub a{ color:var(--muted); }
@media (max-width:640px){
  body{ padding:1rem .85rem 3rem; line-height:1.58; }
  h2{ margin-top:1.9rem; }
  #toc ol{ columns:1; }
  .tw table{ min-width:28rem; font-size:.8rem; }
  pre{ font-size:.76rem; }
}
@media print{
  @page{ size:A4; margin:1.5cm 1.4cm 1.7cm 1.4cm;
    @bottom-center{ content:counter(page) " / " counter(pages); font-size:8pt; color:#888; } }
  body{ max-width:none; font-size:9.3pt; line-height:1.42; color:#1a1a1a; background:#fff;
        padding:0; margin:0; }
  h1{ font-size:18pt; } h2{ font-size:13.5pt; page-break-after:avoid; }
  h3{ font-size:11pt; page-break-after:avoid; } h4{ font-size:9.6pt; page-break-after:avoid; }
  .tw{ border:none; overflow:visible; } .tw table{ min-width:0; font-size:8.1pt;
        page-break-inside:avoid; }
  .tw th{ position:static; }
  pre{ font-size:7.9pt; overflow:visible; white-space:pre-wrap; page-break-inside:avoid; }
  #toc{ display:none; }
}
"""

TOC_SKIP = re.compile(r"^\s*(appendices|references)\s*$", re.I)


def strip_frontmatter(md: str) -> str:
    return re.sub(r"\A\s*<!--.*?-->\s*", "", md, count=1, flags=re.DOTALL)


def wrap_tables(body: str) -> str:
    """Put every pandoc <table> in a horizontally scrollable div."""
    return re.sub(r"(<table\b.*?</table>)", r'<div class="tw">\1</div>', body, flags=re.S)


def build_toc(body: str) -> str:
    """Collapsible contents from the H2/H3 headings pandoc gave ids to."""
    items = []
    for lvl, hid, inner in re.findall(
        r'<h([23])[^>]*\bid="([^"]+)"[^>]*>(.*?)</h\1>', body, flags=re.S
    ):
        text = re.sub(r"<[^>]+>", "", inner).strip()
        if not text or TOC_SKIP.match(text):
            continue
        cls = "" if lvl == "2" else ' class="sub"'
        items.append(f'<li{cls}><a href="#{hid}">{_html.escape(text)}</a></li>')
    if not items:
        return ""
    return (
        '<details id="toc" open><summary>Contents</summary>\n'
        "<ol>\n" + "\n".join(items) + "\n</ol>\n</details>\n"
    )


def build(md_path: Path, out_path: Path, title: str) -> None:
    md = strip_frontmatter(md_path.read_text(encoding="utf-8"))
    body = subprocess.run(
        [PANDOC, "-f", "gfm", "-t", "html5"],
        input=md, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    toc = build_toc(body)
    body = wrap_tables(body)
    # place the contents after the opening blockquote intro, else at the top
    m = re.search(r"</blockquote>", body)
    if toc and m:
        cut = m.end()
        body = body[:cut] + "\n" + toc + body[cut:]
    elif toc:
        body = toc + body
    doc = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='color-scheme' content='light dark'>"
        f"<title>{_html.escape(title)}</title><style>{STYLE}</style></head>"
        f"<body>\n{body}\n"
        "<script>if(matchMedia('(max-width:640px)').matches){"
        "var t=document.getElementById('toc');if(t)t.open=false;}</script>\n"
        "</body></html>\n"
    )
    out_path.write_text(doc, encoding="utf-8")
    print(f"wrote {out_path}  ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    title_arg = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--title=")), None)
    root = Path(__file__).resolve().parents[1]
    src = Path(args[0]) if args else root / "docs" / "technical" / "model-documentation.md"
    out = Path(args[1]) if len(args) > 1 else src.with_suffix(".html")
    build(src, out, title_arg or "Flood-v4.0 — Multi-Hazard Flood Screen: Technical Documentation")
