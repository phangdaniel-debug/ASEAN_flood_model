"""Build a PDF of the journal manuscript with figures embedded.

markdown -> HTML (tables, fenced code) -> PDF via xhtml2pdf (pure-Python,
no system deps). Uses matplotlib's bundled DejaVuSans for full Unicode
(Δ, ≥, ×, β, ≪, –). Run:
    python scripts/_build_manuscript_pdf.py
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown
import matplotlib
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs/paper"
MD = PAPER / "singapore_pluvial_manuscript.md"
OUT = PAPER / "singapore_pluvial_manuscript.pdf"

_fontdir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DV", str(_fontdir / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DV-b", str(_fontdir / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DV-i", str(_fontdir / "DejaVuSans-Oblique.ttf")))
addMapping("DV", 0, 0, "DV")
addMapping("DV", 1, 0, "DV-b")
addMapping("DV", 0, 1, "DV-i")
addMapping("DV", 1, 1, "DV-b")

CSS = """
@page { size: A4; margin: 1.8cm 1.7cm; }
body { font-family: "DV"; font-size: 9.3pt; line-height: 1.38; color: #111; }
h1 { font-size: 15pt; line-height: 1.2; margin: 0 0 6pt 0; }
h2 { font-size: 12pt; margin: 14pt 0 4pt 0; border-bottom: 0.5pt solid #999; padding-bottom: 2pt; }
h3 { font-size: 10.3pt; margin: 9pt 0 3pt 0; }
h4 { font-size: 9.6pt; margin: 7pt 0 2pt 0; }
p { margin: 0 0 5pt 0; text-align: justify; }
em { font-style: italic; }
table { border-collapse: collapse; margin: 5pt 0 7pt 0; font-size: 8.2pt; }
th, td { border: 0.5pt solid #888; padding: 2.4pt 4pt; }
th { background: #eef; font-weight: bold; }
img { max-width: 460px; }
code { font-size: 8.3pt; }
.fig { text-align: center; margin: 6pt 0; }
hr { border: none; border-top: 0.5pt solid #ccc; margin: 8pt 0; }
"""

def link_callback(uri: str, rel: str) -> str:
    """Resolve image/font URIs to absolute filesystem paths."""
    if uri.startswith("file://"):
        return uri[7:]
    if Path(uri).is_absolute() and Path(uri).exists():
        return uri
    p = (PAPER / uri).resolve()
    return p.as_posix() if p.exists() else uri


def main() -> None:
    text = MD.read_text(encoding="utf-8")
    # Center images (they're on their own line as ![..](..)) and drop alt-text noise.
    html_body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    # wrap standalone <img> in a centered figure div
    html_body = re.sub(r"(<p>)?(<img [^>]+>)(</p>)?",
                       r'<div class="fig">\2</div>', html_body)
    html = f'<html><head><meta charset="utf-8"><style>{CSS}</style></head>' \
           f'<body>{html_body}</body></html>'
    with open(OUT, "wb") as fh:
        res = pisa.CreatePDF(html, dest=fh, link_callback=link_callback,
                             encoding="utf-8")
    if res.err:
        raise SystemExit(f"PDF build had {res.err} error(s)")
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT}  ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
