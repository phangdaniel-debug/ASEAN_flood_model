"""Render a Markdown document to a styled PDF via ReportLab.

Self-contained, no LaTeX / wkhtmltopdf / weasyprint (none available here).
Unicode-safe: registers the DejaVu font family (bundled with matplotlib) so the
maths glyphs in the technical docs (∂ η √ ≥ → × superscripts …) render properly
rather than as the missing-glyph boxes the built-in Helvetica/Courier would give.

Handles the constructs actually used by docs/technical/*.md:
  - ATX headings  # .. ####          - fenced ``` code blocks (mono, boxed)
  - pipe tables   | a | b |          - blockquotes  > ...
  - bullet/numbered lists            - horizontal rules ---
  - inline **bold** *italic* `code` [text](url)
  - a leading HTML comment block (draft front-matter) is stripped

Usage:
  python scripts/_md_to_pdf.py <input.md> [output.pdf] [--title "..."]
Defaults to docs/technical/model-documentation.md -> same stem .pdf.
"""
from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

# --- fonts (full-unicode DejaVu from matplotlib) ---------------------------
_TTF = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DJ", _TTF / "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DJ-B", _TTF / "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DJ-I", _TTF / "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DJM", _TTF / "DejaVuSansMono.ttf"))
pdfmetrics.registerFont(TTFont("DJM-B", _TTF / "DejaVuSansMono-Bold.ttf"))
pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJ-B", italic="DJ-I", boldItalic="DJ-B")

NAVY = colors.HexColor("#1a3a5c")
BLUE = colors.HexColor("#2166ac")
STEEL = colors.HexColor("#4a90d9")
ROW_ALT = colors.HexColor("#eef3f8")
BORDER = colors.HexColor("#b0bec5")
CODEBG = colors.HexColor("#f5f5f7")
QUOTEBG = colors.HexColor("#eef3f8")
GREY = colors.HexColor("#444444")

BODY = ParagraphStyle("body", fontName="DJ", fontSize=9, leading=13, spaceAfter=5,
                      textColor=colors.HexColor("#1a1a1a"))
H = {
    1: ParagraphStyle("h1", fontName="DJ-B", fontSize=17, leading=21, spaceBefore=8,
                      spaceAfter=8, textColor=NAVY, keepWithNext=1),
    2: ParagraphStyle("h2", fontName="DJ-B", fontSize=13, leading=17, spaceBefore=12,
                      spaceAfter=5, textColor=BLUE, keepWithNext=1),
    3: ParagraphStyle("h3", fontName="DJ-B", fontSize=11, leading=15, spaceBefore=9,
                      spaceAfter=4, textColor=STEEL, keepWithNext=1),
    4: ParagraphStyle("h4", fontName="DJ-B", fontSize=9.5, leading=13, spaceBefore=7,
                      spaceAfter=3, textColor=GREY, keepWithNext=1),
}
CODE = ParagraphStyle("code", fontName="DJM", fontSize=7.4, leading=9.4,
                      textColor=colors.HexColor("#12232e"))
QUOTE = ParagraphStyle("quote", parent=BODY, fontName="DJ-I", textColor=GREY,
                       leftIndent=8, borderPadding=(4, 4, 4, 6))
CELL = ParagraphStyle("cell", fontName="DJ", fontSize=7.4, leading=9.4)
CELL_H = ParagraphStyle("cellh", fontName="DJ-B", fontSize=7.4, leading=9.4,
                        textColor=colors.white)


# DejaVuSansMono lacks a few glyphs that DejaVuSans has; substitute in mono spans only.
MONO_FB = {"≪": "<<", "≫": ">>"}  # ≪ ≫


def _mono(s: str) -> str:
    for k, v in MONO_FB.items():
        s = s.replace(k, v)
    return s


def inline(t: str) -> str:
    """Markdown inline -> ReportLab mini-markup (escaping first).

    Code spans are stashed as placeholders BEFORE emphasis is applied. Otherwise a
    literal ``*`` inside backticks — e.g. the glob ``2026-07-04-*canal-hand-pluvial.md``
    in §6.3 — opens an italic that pairs with an unrelated ``*`` later in the same
    paragraph, emitting crossed ``<font>``/``<i>`` tags that ReportLab refuses to parse
    ("saw </font> instead of expected </i>") and aborting the whole build.
    """
    t = html.escape(t, quote=False)
    spans: list[str] = []

    def _stash(m: re.Match) -> str:
        spans.append(f'<font face="DJM" size="8">{_mono(m.group(1))}</font>')
        return f"\x00{len(spans) - 1}\x00"

    t = re.sub(r"`([^`]+)`", _stash, t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
               r'<link href="\2" color="#2166ac">\1</link>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], t)


def strip_frontmatter(md: str) -> str:
    return re.sub(r"\A\s*<!--.*?-->\s*", "", md, count=1, flags=re.DOTALL)


def _longest_word_w(raw: list[list[str]], j: int) -> float:
    """Rendered width of the longest unbreakable word in column ``j``, plus padding."""
    best = 0.0
    for k, row in enumerate(raw):
        for word in row[j].split():
            if "`" in word:                                     # code span: 8 pt mono
                font, size = "DJM", 8
            elif k == 0 or "**" in row[j]:                      # header or bold text
                font, size = "DJ-B", CELL.fontSize
            else:
                font, size = "DJ", CELL.fontSize
            best = max(best, pdfmetrics.stringWidth(re.sub(r"[*`]", "", word), font, size))
    return best + 7  # 3 pt left + 3 pt right cell padding, plus a hair


def parse_table(rows: list[str], avail_w: float) -> Table:
    def cells(line):
        line = line.strip().strip("|")
        return [c.strip() for c in re.split(r"(?<!\\)\|", line)]
    header = cells(rows[0])
    body = [cells(r) for r in rows[2:]]
    ncol = len(header)
    body = [(r + [""] * ncol)[:ncol] for r in body]
    data = [[Paragraph(inline(c), CELL_H) for c in header]]
    data += [[Paragraph(inline(c), CELL) for c in r] for r in body]
    # weight columns by longest raw content so wide columns get more room
    raw = [header] + body
    widths = [max((len(r[j]) for r in raw), default=4) for j in range(ncol)]
    widths = [max(w, 3) ** 0.85 for w in widths]
    s = sum(widths)
    col_w = [avail_w * w / s for w in widths]
    # ...but never narrower than the column's longest word (capped at a quarter of the
    # page). Otherwise a short column next to long prose, such as a "See: A1" reference,
    # gets a sliver and wraps one character per line.
    floor = [min(_longest_word_w(raw, j), 0.25 * avail_w) for j in range(ncol)]
    short = [j for j in range(ncol) if col_w[j] < floor[j]]
    fixed = sum(floor[j] for j in short)
    if short and len(short) < ncol and fixed < 0.8 * avail_w:
        rest = [j for j in range(ncol) if j not in short]
        rest_w = sum(widths[j] for j in rest)
        for j in short:
            col_w[j] = floor[j]
        for j in rest:
            col_w[j] = (avail_w - fixed) * widths[j] / rest_w
    t = Table(data, colWidths=col_w, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(style))
    return t


def build(md_path: Path, pdf_path: Path, title: str) -> None:
    md = strip_frontmatter(md_path.read_text(encoding="utf-8"))
    lines = md.split("\n")
    avail_w = A4[0] - 32 * mm
    flow: list = []
    i, n = 0, len(lines)

    def flush_para(buf):
        if buf:
            flow.append(Paragraph(inline(" ".join(buf).strip()), BODY))
            buf.clear()

    para: list[str] = []
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):                       # code fence
            flush_para(para)
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i].replace("\t", "    "))
                i += 1
            i += 1
            body = html.escape("\n".join(code), quote=False)
            tbl = Table([[Preformatted(body, CODE)]], colWidths=[avail_w])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
                ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(Spacer(1, 2)); flow.append(tbl); flow.append(Spacer(1, 4))
            continue

        m = re.match(r"(#{1,4})\s+(.*)", stripped)             # heading
        if m:
            flush_para(para)
            lvl = len(m.group(1))
            flow.append(Paragraph(inline(m.group(2)), H[lvl]))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):
            flush_para(para)                                    # pipe table
            tbl_rows = []
            while i < n and lines[i].strip().startswith("|"):
                tbl_rows.append(lines[i]); i += 1
            flow.append(Spacer(1, 2)); flow.append(parse_table(tbl_rows, avail_w))
            flow.append(Spacer(1, 5))
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):       # hr
            flush_para(para)
            flow.append(Spacer(1, 3))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=BORDER))
            flow.append(Spacer(1, 3))
            i += 1
            continue

        if stripped.startswith(">"):                            # blockquote
            flush_para(para)
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].strip()); i += 1
            # a bare ">" line separates paragraphs inside one quote; keep them apart
            # rather than running a multi-paragraph callout into a single block
            paras, cur = [], []
            for ln in q + [""]:
                if ln:
                    cur.append(ln)
                elif cur:
                    paras.append(" ".join(cur)); cur = []
            qt = Table([[[Paragraph(inline(p), QUOTE) for p in paras]]], colWidths=[avail_w])
            qt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), QUOTEBG),
                ("LINEBEFORE", (0, 0), (0, -1), 2, STEEL),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(qt); flow.append(Spacer(1, 4))
            continue

        lm = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)", line)     # list block
        if lm:
            flush_para(para)
            items, ordered = [], bool(re.match(r"\d", lm.group(2)))
            while i < n:
                lm2 = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)", lines[i])
                if not lm2:
                    if lines[i].strip() == "":
                        break
                    items[-1] = items[-1] + " " + lines[i].strip() if items else lines[i].strip()
                    i += 1
                    continue
                items.append(lm2.group(3)); i += 1
            lf = ListFlowable(
                [ListItem(Paragraph(inline(it), BODY), leftIndent=12) for it in items],
                bulletType="1" if ordered else "bullet",
                bulletFontName="DJ", bulletFontSize=8, leftIndent=14,
            )
            flow.append(lf); flow.append(Spacer(1, 3))
            continue

        if stripped == "":                                      # blank
            flush_para(para)
            i += 1
            continue

        para.append(stripped)                                   # paragraph text
        i += 1

    flush_para(para)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("DJ", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(20 * mm, 12 * mm, title)
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"{doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=title,
    )
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {pdf_path}  ({pdf_path.stat().st_size // 1024} KB, {doc.page} pages)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    title_arg = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--title=")), None)
    root = Path(__file__).resolve().parents[1]
    src = Path(args[0]) if args else root / "docs" / "technical" / "model-documentation.md"
    out = Path(args[1]) if len(args) > 1 else src.with_suffix(".pdf")
    build(src, out, title_arg or "Flood-v4.0 — Multi-Hazard Flood Screen: Technical Documentation")
