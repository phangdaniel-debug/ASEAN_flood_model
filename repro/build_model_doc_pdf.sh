#!/usr/bin/env bash
# Render the model documentation to PDF:
#   docs/technical/model-documentation.md -> docs/technical/model-documentation.pdf
#
# Requires pandoc and tectonic on PATH, plus the DejaVu fonts (Windows/most Linux ship them).
#
# WHY NOT scripts/_md_to_pdf.py? That builder (ReportLab, hand-rolled Markdown parsing) was
# written when "no LaTeX / wkhtmltopdf / weasyprint" were available here -- no longer true,
# tectonic is installed. It still renders the other docs/technical/*.md fine and is left in
# place for them, but it CANNOT render this document: its inline-emphasis regex reads the
# `*` in the glob `docs/runs/2026-07-04-*canal-hand-pluvial.md` as an italic marker and dies
# with "Parse error: saw </font> instead of expected </i>". pandoc parses Markdown properly,
# and gives a real TOC, hyperlinks and typesetting besides.
#
# FONT CHOICE IS LOAD-BEARING, NOT COSMETIC. The stock LaTeX fonts (Latin Modern) have no
# glyph for operators this document depends on -- >= (U+2265), logical-and (U+2227),
# ~= (U+2248), tau (U+03C4), minus (U+2212) -- and XeTeX drops a missing glyph SILENTLY,
# emitting only a warning. The gate criterion "HR>=0.70 AND CRR>=0.70" then renders as
# "HR0.70 CRR0.70": not ugly, WRONG. DejaVu covers all of them. The guard at the bottom
# fails the build if any glyph goes missing, so this can never regress unnoticed.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=docs/technical/model-documentation.md
OUT=docs/technical/model-documentation.pdf
LOG=$(mktemp)
trap 'rm -f "$LOG" "$HDR"' EXIT

HDR=$(mktemp --suffix=.tex)
cat >"$HDR" <<'TEX'
\usepackage{etoolbox}
% Code blocks. The fences carry no language tag, so pandoc emits `verbatim`. The longest
% true line is 119 characters; \scriptsize DejaVu Sans Mono fits that inside the 17.8cm
% text block WITHOUT wrapping -- which matters, because the equations are ASCII art with
% U+2500 fraction bars that line-breaking would shred.
\AtBeginEnvironment{verbatim}{\scriptsize}
% Tables: source rows run to 633 chars. pandoc wraps cell content to the text block, so
% they fit by construction; \scriptsize keeps the widest ones legible rather than cramped.
\AtBeginEnvironment{longtable}{\scriptsize}
\usepackage{microtype}

% The five codepoints DejaVu Serif lacks (verified against every font on the box with
% fontTools; only DejaVu Sans covers the doc's full set, and a sans body reads worse over
% 40-odd pages). Each has a real LaTeX equivalent, so mapping them is not a workaround --
% it typesets them as proper symbols instead of dropping them. Rendering, not source, is
% the right place for this: the Markdown stays readable as Markdown.
\usepackage{amssymb}
\usepackage{newunicodechar}
\newunicodechar{≪}{\ensuremath{\ll}}
\newunicodechar{≲}{\ensuremath{\lesssim}}
\newunicodechar{✓}{\ensuremath{\checkmark}}
\newunicodechar{✗}{\ensuremath{\times}}
\newunicodechar{⚠}{\textbf{!}}
TEX

pandoc "$SRC" -o "$OUT" \
  --pdf-engine=tectonic \
  --toc --toc-depth=3 \
  --include-in-header="$HDR" \
  -V geometry:a4paper -V geometry:margin=1.6cm \
  -V fontsize=10pt \
  -V mainfont="DejaVu Serif" \
  -V sansfont="DejaVu Sans" \
  -V monofont="DejaVu Sans Mono" \
  -V colorlinks=true -V linkcolor=RoyalBlue -V urlcolor=RoyalBlue -V toccolor=black \
  2>&1 | tee "$LOG"

# Guard: a dropped glyph is a silent correctness bug in a doc whose gate is written in
# set operators. Fail loudly rather than ship "HR0.70".
if grep -qiE "Missing character|could not represent character" "$LOG"; then
  echo "FAIL: the engine dropped characters -- the PDF misrepresents the source." >&2
  grep -iE "Missing character|could not represent character" "$LOG" | sort -u | head >&2
  exit 1
fi
echo "OK -> $OUT"
