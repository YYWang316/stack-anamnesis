"""analysis_layer/render/html.py — PURE markdown→HTML renderer (B.4 TD-040; ④.1 TD-047).

Turns a crypto research report (the markdown that ``orchestrate`` writes to
``meta/reports/<slug>_<utc>.md``) into ONE self-contained HTML file: inline CSS,
no external ``<link>`` / ``<script src>`` — fully portable, opens anywhere.

④.1 (TD-047) adopts the approved institutional-clean visual system
(``meta/design/report_design_v1.html``): the design's ``:root`` CSS-variable
system + ``@media print`` block is EMBEDDED verbatim below (the module stays
self-contained — the design file is NOT read at runtime), and the renderer emits
the wrapper markup that stylesheet expects: a ``.report-head`` header (title +
"data snapshot · as_of" subline pulled from the report's Part 0 ``Date`` line), a
``.page`` container, ``table.memo`` inside ``.table-wrap``, ``p.prose`` body
prose, and the design's ``.legend``. The badge / chip class names already matched
the design, so those carry over unchanged.

The value-add over the raw markdown is that the report's *status markers* become
visually scannable. The pipeline annotates every metric slot with a tag the eye
otherwise has to hunt for; this renderer turns each into a coloured badge/chip:

  * ``[AUTO ✓ FILLED: …]`` / ``[SEMI-AUTO ✓ COMPUTED: …]`` → green "machine-filled"
  * ``⚠ NEEDS HUMAN REVIEW [SEMI-AUTO]`` / ``⚠ MANUAL`` / ``[MANUAL: …]`` → amber
  * ``⚠ UNFILLED [AUTO]`` → amber (flagged, NOT fabricated)
  * ``[AUTO: …]`` / ``[SEMI-AUTO: …]`` planned-but-unfilled tags → neutral grey
  * confidence ``High`` / ``Medium`` / ``Low`` → green / amber / grey chips

Two pre-passes run before conversion:
  * ``strip_coaching`` — the coaching-channel backstop: any ``> GUIDANCE`` /
    ``> TRAP`` / ``> ↳ Cap check`` blockquote is removed whole, so the internal
    coaching channel can never leak into the deliverable even if the writer
    missed one (the writer strips them per its brief; the renderer enforces it).
  * KEY SIGNAL marker normalisation ``⭐ → ★`` (display transform only).

It is a focused converter for the constrained markdown the template emits
(ATX headers, GFM pipe tables, ``-``/``*`` lists with 4-space nesting, ``>``
blockquotes, ``---`` rules, ``**bold**`` / ``*italic*`` / `` `code` `` inline) —
deliberately NOT a general markdown engine and NOT coupled to the inherited
equity HTML machinery. PURE + deterministic: same markdown in → byte-identical
HTML out (no clock, no network, no randomness). Charts (``.chart-grid`` /
``.chart-ph``, whose CSS sits dormant in the stylesheet) are NOT emitted yet —
that is step ④.2.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

# --------------------------------------------------------------------------- #
# pre-pass 1: coaching-channel strip backstop
# --------------------------------------------------------------------------- #
_COACHING_PREFIXES = ("GUIDANCE", "TRAP", "↳ Cap check")


def strip_coaching(markdown_text: str) -> str:
    """Remove any blockquote whose FIRST line is a coaching marker
    (``> GUIDANCE`` / ``> TRAP`` / ``> ↳ Cap check``) — the entire blockquote
    (all consecutive ``>`` lines), leaving normal blockquotes intact. Defense in
    depth: the writer already strips the coaching channel per its brief, this is
    the renderer's guarantee that it never reaches the reader."""
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].lstrip().startswith(">"):
            j = i
            while j < n and lines[j].lstrip().startswith(">"):
                j += 1
            first = lines[i].lstrip()[1:].lstrip().lstrip("*").lstrip()
            if first.startswith(_COACHING_PREFIXES):
                i = j  # drop the whole coaching blockquote
                continue
            out.extend(lines[i:j])
            i = j
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# inline: escape → badges/chips → bold/italic/code
# --------------------------------------------------------------------------- #
def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


_CHIP_CLASS = {"high": "chip-high", "medium": "chip-med", "low": "chip-low"}


def _chip(level: str) -> str:
    cls = _CHIP_CLASS[level.lower()]
    return f'<span class="chip {cls}">{level}</span>'


# Colour clearly-signed numeric / percent / $ deltas (design's .neg / .pos). The
# sign must be ``+``, ``−`` (U+2212) or ``-`` AND immediately precede a digit or
# ``$`` AND not sit after a word char / ``$`` / ``.`` — so date hyphens
# (``2026-05-28``), hyphenated words (``mixed-to-soft``) and en-dash ranges
# (``3–12mo``) are left alone; only genuine signed magnitudes are wrapped.
_DELTA_RE = re.compile(
    r"(?<![\w$.])([+−-])(\$?\d[\d,]*(?:\.\d+)?(?:%|[A-Za-z]{1,2})?)"
)


def _color_deltas(html_text: str) -> str:
    def _repl(m: "re.Match[str]") -> str:
        cls = "pos" if m.group(1) == "+" else "neg"
        return f'<span class="{cls}">{m.group(1)}{m.group(2)}</span>'

    return _DELTA_RE.sub(_repl, html_text)


def _apply_badges(s: str) -> str:
    """Wrap the report's status markers in coloured spans. Runs on ESCAPED text
    and emits raw span HTML, BEFORE the generic bold/code passes — so it consumes
    the marker's own backticks / ``**`` and the later passes can't corrupt it.
    Order matters: the green ``✓ FILLED`` form is matched before the generic
    ``[AUTO: …]`` tag, and MANUAL before the generic tag.
    """
    # green — machine-filled (backtick-wrapped, carries the ✓)
    s = re.sub(
        r"`\[(AUTO ✓ FILLED[^\]]*|SEMI-AUTO ✓ COMPUTED[^\]]*)\]`",
        r'<span class="badge badge-filled">[\1]</span>',
        s,
    )
    # amber — the bold ⚠ flags the filler emits for unfilled / review / manual slots
    s = re.sub(
        r"⚠ \*\*(NEEDS HUMAN REVIEW \[SEMI-AUTO\]|UNFILLED \[AUTO\]|MANUAL)\*\*",
        r'<span class="badge badge-warn">⚠ \1</span>',
        s,
    )
    # amber — a [MANUAL: source] slot tag (researcher must fill)
    s = re.sub(
        r"`\[(MANUAL[^\]]*)\]`",
        r'<span class="badge badge-manual">[\1]</span>',
        s,
    )
    # grey — planned-but-unfilled [AUTO: …] / [SEMI-AUTO: …] / [SEMI-AUTO] tags
    s = re.sub(
        r"`\[((?:AUTO|SEMI-AUTO)(?::[^\]]*)?)\]`",
        r'<span class="badge badge-tag">[\1]</span>',
        s,
    )
    # confidence chips in running text: "confidence **High** (agree)"
    s = re.sub(
        r"confidence \*\*(High|Medium|Low)\*\*",
        lambda m: "confidence " + _chip(m.group(1)),
        s,
    )
    return s


def _inline(text: str) -> str:
    """Escape + badge + bold/italic/code one run of text → inline HTML."""
    s = _escape(text)
    s = _apply_badges(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)          # bold first
    s = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", s)    # then italic
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)                  # inline code
    return s


# --------------------------------------------------------------------------- #
# block-level classification helpers
# --------------------------------------------------------------------------- #
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_SEP_CELL_RE = re.compile(r":?-{2,}:?")

# design heading classes (the design CSS targets h2.part-title / h3.sub-title /
# h4.minor-title specifically — bare tags would get no rule). Level-1 headers are
# the template's title / "REPORT BODY" boilerplate; they are dropped from the body
# because the title is promoted into the .report-head block.
_H_CLASS = {2: "part-title", 3: "sub-title", 4: "minor-title"}


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _split_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_table_sep(line: str) -> bool:
    s = line.strip()
    if "|" not in s and "-" not in s:
        return False
    cells = _split_row(line)
    return bool(cells) and all(_SEP_CELL_RE.fullmatch(c) for c in cells if c != "") \
        and any(c for c in cells)


def _is_table_header(line: str, nxt: str) -> bool:
    return "|" in line and not _is_blank(line) and _is_table_sep(nxt)


# --------------------------------------------------------------------------- #
# block renderers
# --------------------------------------------------------------------------- #
def _render_table_cell(cell: str) -> str:
    """A table cell → inline HTML, with a bare High/Medium/Low promoted to a chip
    (so the Evidence Table's Confidence column is scannable too) and clearly-signed
    deltas coloured."""
    bare = cell.strip()
    if bare.lower() in _CHIP_CLASS:
        return _chip(bare)
    return _color_deltas(_inline(cell))


def _render_table(lines: List[str], i: int) -> Tuple[str, int]:
    header = _split_row(lines[i])
    i += 2  # header row + separator row
    rows: List[List[str]] = []
    while i < len(lines) and "|" in lines[i] and not _is_blank(lines[i]):
        rows.append(_split_row(lines[i]))
        i += 1
    # design treatment: table.memo inside a .table-wrap
    out = ['<div class="table-wrap">', '<table class="memo">', "<thead><tr>"]
    out += [f"<th>{_inline(c)}</th>" for c in header]
    out += ["</tr></thead>", "<tbody>"]
    for row in rows:
        # verdict-row highlight: a ☑ cell selects the row, a ☐ cell dims it.
        # Lives inside _render_table, so only TABLE rows are touched — the
        # ☑/☐ checkbox LISTS (Part 0 Subject Type, Data Availability, Position)
        # render as lists, not tables, and are unaffected. In the current
        # template the §5.5 KEY SIGNAL matrix is the only table with checkbox
        # cells, so this lands exactly there.
        joined = "".join(row)
        if "☑" in joined:
            out.append('<tr class="is-selected">')
        elif "☐" in joined:
            out.append('<tr class="is-dim">')
        else:
            out.append("<tr>")
        out += [f"<td>{_render_table_cell(c)}</td>" for c in row]
        out.append("</tr>")
    out += ["</tbody>", "</table>", "</div>"]
    return "".join(out), i


def _build_nested(entries: List[Tuple[int, str]]) -> str:
    """(level, inline-html) pairs → well-formed nested <ul>/<li>. Level is the
    4-space indent depth; a child opens a nested <ul> inside its parent's <li>."""
    out: List[str] = []
    open_ul: List[int] = []
    for level, content in entries:
        if not open_ul:
            out.append("<ul>")
            open_ul.append(level)
        elif level > open_ul[-1]:
            out.append("<ul>")
            open_ul.append(level)
        else:
            out.append("</li>")
            while len(open_ul) > 1 and level < open_ul[-1]:
                out.append("</ul></li>")
                open_ul.pop()
        out.append("<li>" + content)
    out.append("</li>")
    while open_ul:
        out.append("</ul>")
        open_ul.pop()
        if open_ul:
            out.append("</li>")
    return "".join(out)


def _render_list(lines: List[str], i: int) -> Tuple[str, int]:
    entries: List[Tuple[int, str]] = []
    while i < len(lines):
        m = _LIST_RE.match(lines[i])
        if not m:
            break
        indent = len(m.group(1).replace("\t", "    "))
        entries.append((indent // 4, _inline(m.group(2))))
        i += 1
    return _build_nested(entries), i


def _render_blockquote(lines: List[str], i: int) -> Tuple[str, int]:
    parts: List[str] = []
    while i < len(lines) and lines[i].lstrip().startswith(">"):
        parts.append(_inline(lines[i].lstrip()[1:].lstrip()))
        i += 1
    return "<blockquote>" + "<br>".join(parts) + "</blockquote>", i


# A paragraph opening with "One-line conclusion:" / "VERDICT:" (optionally
# wrapped in markdown bold) becomes the design's .callout summary block.
_CALLOUT_RE = re.compile(r"^\*{0,2}\s*(One-line conclusion|VERDICT)\s*[:：]\*{0,2}\s*(.*)$")


def _render_paragraph(lines: List[str], i: int) -> Tuple[str, int]:
    raw_parts: List[str] = []
    while i < len(lines):
        ln = lines[i]
        if (
            _is_blank(ln)
            or _HEADER_RE.match(ln)
            or _LIST_RE.match(ln)
            or ln.strip() == "---"
            or ln.lstrip().startswith(">")
            or (i + 1 < len(lines) and _is_table_header(ln, lines[i + 1]))
        ):
            break
        raw_parts.append(ln.strip())
        i += 1
    raw = " ".join(raw_parts)
    m = _CALLOUT_RE.match(raw)
    if m:
        label = _escape(m.group(1))
        body = _color_deltas(_inline(m.group(2)))
        return f'<div class="callout"><span class="label">{label}</span> {body}</div>', i
    return '<p class="prose">' + _color_deltas(_inline(raw)) + "</p>", i


# --------------------------------------------------------------------------- #
# body assembly
# --------------------------------------------------------------------------- #
def _markdown_to_body(markdown_text: str) -> str:
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if _is_blank(ln):
            i += 1
            continue
        if ln.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        m = _HEADER_RE.match(ln)
        if m:
            level = len(m.group(1))
            if level == 1:
                # template title / "REPORT BODY" boilerplate → promoted to header
                i += 1
                continue
            cls = _H_CLASS.get(level)
            attr = f' class="{cls}"' if cls else ""
            out.append(f"<h{level}{attr}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue
        if i + 1 < n and _is_table_header(ln, lines[i + 1]):
            html, i = _render_table(lines, i)
            out.append(html)
            continue
        if ln.lstrip().startswith(">"):
            html, i = _render_blockquote(lines, i)
            out.append(html)
            continue
        if _LIST_RE.match(ln):
            html, i = _render_list(lines, i)
            out.append(html)
            continue
        html, i = _render_paragraph(lines, i)
        out.append(html)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# header extraction (deterministic — pulled from the report's own Part 0)
# --------------------------------------------------------------------------- #
def _first_h1(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            return m.group(1).strip()
    return ""


def _doc_title(markdown_text: str, override: Optional[str]) -> str:
    if override:
        return override
    # prefer the Part 0 "- **Title**: X" line (strip a trailing `[…]` tag)
    for line in markdown_text.splitlines():
        m = re.match(r"^-\s+\*\*Title\*\*:\s*(.+)$", line)
        if m:
            t = re.sub(r"\s*`\[[^\]]*\]`\s*$", "", m.group(1)).strip()
            if t:
                return t
    return _first_h1(markdown_text) or "Crypto Research Report"


def _header_block(markdown_text: str, doc_title: str) -> str:
    """The .report-head block the design CSS expects: eyebrow + title + a
    snapshot subline carrying as_of (and subject_type / issuer when cleanly
    present). If no Part 0 ``Date`` line is found, the subline is omitted —
    title only."""
    inner = [
        '<p class="eyebrow">Stack Anamnesis · Research Memo</p>',
        f"<h1>{_escape(doc_title)}</h1>",
    ]
    m_date = re.search(r"^-\s+\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})", markdown_text, re.M)
    if m_date:
        snap = [
            '<div class="snapshot">',
            f'<span><span class="snap-key">Data snapshot</span> · as_of '
            f"<strong>{_escape(m_date.group(1))}</strong></span>",
        ]
        m_type = re.search(r"subject_type\s+(\w+)", markdown_text)
        if m_type:
            snap.append('<span class="sep">|</span>')
            snap.append(
                f'<span>subject_type <code>{_escape(m_type.group(1))}</code></span>'
            )
        m_iss = re.search(r"·\s*issuer\s+([^·\n]+?)\s*·", markdown_text)
        if m_iss:
            cell = f"issuer <strong>{_escape(m_iss.group(1).strip())}</strong>"
            m_cik = re.search(r"sec_cik=`?(\d+)`?", markdown_text)
            if m_cik:
                cell += f' · CIK <code>{_escape(m_cik.group(1))}</code>'
            snap.append('<span class="sep">|</span>')
            snap.append(f"<span>{cell}</span>")
        snap.append("</div>")
        inner.append("".join(snap))
    return '<header class="report-head">' + "".join(inner) + "</header>"


# --------------------------------------------------------------------------- #
# the document (inline CSS — no external resources)
#
# _DESIGN_CSS is the approved institutional-clean visual system, EMBEDDED
# verbatim from meta/design/report_design_v1.html so this module stays
# self-contained (the design file is never read at runtime). _SUPPLEMENTAL_CSS
# below harmonises the few generic tags the constrained markdown renderer emits
# (nested <ul>/<li>, <blockquote>, <hr>, h5/h6) which the design's bespoke,
# class-targeted CSS does not style on its own.
# --------------------------------------------------------------------------- #
_DESIGN_CSS = """
/* =========================================================================
   STACK ANAMNESIS — institutional research-memo visual system  (v1 design spec)
   Self-contained: system fonts only, no external resources, no JS.
   All theming via :root custom properties so a string-renderer can reproduce
   this deterministically.
   ========================================================================= */
:root {
  color-scheme: light;

  /* ---- Type stacks (system only) ---------------------------------------- */
  --font-ui:   -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-body: Georgia, "Times New Roman", "Songti SC", "Noto Serif", serif;
  --font-mono: "SFMono-Regular", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;

  /* ---- Neutral base + ONE restrained navy accent ------------------------ */
  --color-bg:          #ffffff;   /* page                                   */
  --color-surface:     #f9fafb;   /* off-white panels / table head / chart   */
  --color-surface-2:   #f4f6f8;   /* zebra / nested fill                     */
  --color-ink:         #1b2330;   /* primary text (navy-tinted near-black)   */
  --color-ink-soft:    #39424f;   /* secondary text                         */
  --color-muted:       #5c6675;   /* captions / meta                        */
  --color-faint:       #8b95a3;   /* least-emphasis labels                  */
  --color-accent:      #1b3a6b;   /* deep navy — the single accent          */
  --color-accent-deep: #15305a;   /* hover / emphatic navy                  */
  --color-accent-tint: #eef2f8;   /* navy wash for headers / callouts       */

  /* ---- Hairline rules (memo, not boxes) --------------------------------- */
  --color-rule:        #e5e8ee;   /* default hairline                       */
  --color-rule-soft:   #eef0f4;   /* faintest divider                       */
  --color-rule-strong: #c9d0da;   /* table head underline / strong divider  */

  /* ---- Status palette — muted & professional (NOT candy) ---------------- */
  --ok-ink:    #2f6b46;  --ok-bg:    #eef4f0;  --ok-border:    #cbe0d3;  /* green  */
  --warn-ink:  #8a6014;  --warn-bg:  #f8f1e2;  --warn-border:  #e9d8b2;  /* amber  */
  --bad-ink:   #9a3b32;  --bad-bg:   #f5ece9;  --bad-border:   #e3c9c3;  /* red    */
  --neutral-ink: #54607a; --neutral-bg: #eef0f4; --neutral-border: #d6dbe3; /* grey */

  /* ---- Spacing scale ---------------------------------------------------- */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;

  /* ---- Radii ------------------------------------------------------------ */
  --radius-sm: 3px;  --radius-md: 5px;  --radius-lg: 8px;

  /* ---- Type scale ------------------------------------------------------- */
  --fs-eyebrow: 0.72rem;
  --fs-meta:    0.82rem;
  --fs-body:    1.0rem;
  --fs-h4:      1.05rem;
  --fs-h3:      1.22rem;
  --fs-h2:      1.5rem;
  --fs-h1:      2.0rem;
}

/* ---- Reset-ish ---------------------------------------------------------- */
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-ink);
  font-family: var(--font-ui);
  font-size: var(--fs-body);
  line-height: 1.65;
}
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: var(--space-7) var(--space-6) var(--space-8);
}

/* =========================================================================
   1 · REPORT HEADER
   ========================================================================= */
.report-head {
  border-top: 3px solid var(--color-accent);
  padding-top: var(--space-5);
  margin-bottom: var(--space-6);
}
.report-head .eyebrow {
  font-size: var(--fs-eyebrow);
  letter-spacing: 0.13em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-accent);
  margin: 0 0 var(--space-3);
}
.report-head h1 {
  font-family: var(--font-ui);
  font-size: var(--fs-h1);
  line-height: 1.18;
  font-weight: 650;
  letter-spacing: -0.012em;
  margin: 0 0 var(--space-3);
  color: var(--color-ink);
}
.report-head .subtitle {
  font-family: var(--font-body);
  font-size: 1.08rem;
  color: var(--color-ink-soft);
  margin: 0 0 var(--space-4);
}
.snapshot {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  align-items: baseline;
  font-size: var(--fs-meta);
  color: var(--color-muted);
  border-top: 1px solid var(--color-rule);
  border-bottom: 1px solid var(--color-rule);
  padding: var(--space-3) 0;
}
.snapshot .snap-key {
  font-weight: 600;
  color: var(--color-ink-soft);
}
.snapshot .sep { color: var(--color-faint); }
.snapshot code, .meta-mono {
  font-family: var(--font-mono);
  font-size: 0.92em;
  color: var(--color-accent);
}

/* =========================================================================
   2 · SECTION HEADINGS  (Part N — Title)
   ========================================================================= */
.part {
  margin-top: var(--space-8);
}
.part-eyebrow {
  font-size: var(--fs-eyebrow);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-accent);
  margin: 0 0 var(--space-2);
}
h2.part-title {
  font-family: var(--font-ui);
  font-size: var(--fs-h2);
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: var(--space-8) 0 var(--space-2);
  padding-bottom: var(--space-3);
  border-bottom: 2px solid var(--color-rule-strong);
  color: var(--color-ink);
}
h3.sub-title {
  font-family: var(--font-ui);
  font-size: var(--fs-h3);
  font-weight: 600;
  margin: var(--space-6) 0 var(--space-2);
  color: var(--color-ink);
}
h4.minor-title {
  font-family: var(--font-ui);
  font-size: var(--fs-h4);
  font-weight: 650;
  margin: var(--space-5) 0 var(--space-2);
  color: var(--color-ink);
}

/* ---- Body prose (serif, generous leading) ------------------------------ */
p.prose {
  font-family: var(--font-body);
  font-size: 1.02rem;
  line-height: 1.72;
  color: var(--color-ink-soft);
  margin: 0 0 var(--space-4);
}
p.prose strong { color: var(--color-ink); font-weight: 700; }
p.prose em { color: var(--color-ink); }
.lead { font-size: 1.06rem; }
code, .mono { font-family: var(--font-mono); }
p.prose code {
  font-size: 0.88em;
  background: var(--color-surface-2);
  padding: 0.05em 0.32em;
  border-radius: var(--radius-sm);
  color: var(--color-accent);
}

/* =========================================================================
   TABLES — printed-memo treatment: light horizontal rules, restrained head
   ========================================================================= */
.table-wrap { margin: var(--space-4) 0 var(--space-5); }
.table-caption {
  font-size: var(--fs-meta);
  color: var(--color-muted);
  margin: 0 0 var(--space-2);
}
.table-caption .tnum {
  font-weight: 700;
  color: var(--color-accent);
  letter-spacing: 0.04em;
}
table.memo {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-ui);
  font-size: 0.9rem;
  line-height: 1.5;
}
table.memo thead th {
  text-align: left;
  font-weight: 600;
  font-size: var(--fs-eyebrow);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
  background: var(--color-surface);
  padding: var(--space-3) var(--space-3);
  border-bottom: 2px solid var(--color-rule-strong);
  vertical-align: bottom;
  white-space: nowrap;
}
table.memo tbody td {
  padding: var(--space-3) var(--space-3);
  border-bottom: 1px solid var(--color-rule);
  vertical-align: top;
  color: var(--color-ink-soft);
}
table.memo tbody tr:last-child td { border-bottom: 1px solid var(--color-rule-strong); }
table.memo td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.memo td.idx { color: var(--color-faint); font-variant-numeric: tabular-nums; width: 1.5em; }
table.memo td strong { color: var(--color-ink); }
table.memo .neg { color: var(--bad-ink); font-weight: 600; }
table.memo .pos { color: var(--ok-ink); font-weight: 600; }
/* selected (verdict) row gets a restrained navy left-marker */
table.memo tr.is-selected td { background: var(--color-accent-tint); }
table.memo tr.is-selected td:first-child { box-shadow: inset 3px 0 0 var(--color-accent); }
table.memo tr.is-dim td { color: var(--color-faint); }

/* =========================================================================
   STATUS BADGES + CONFIDENCE CHIPS
   ========================================================================= */
.badge {
  display: inline-block;
  font-family: var(--font-ui);
  font-size: 0.72rem;
  font-weight: 650;
  line-height: 1.4;
  letter-spacing: 0.01em;
  padding: 0.05em 0.5em;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  white-space: nowrap;
  vertical-align: baseline;
}
/* [AUTO ✓ FILLED] — green */
.badge-filled { background: var(--ok-bg);   color: var(--ok-ink);   border-color: var(--ok-border); }
/* [⚠ NEEDS HUMAN REVIEW] / [⚠ MANUAL] / [⚠ UNFILLED] — amber */
.badge-warn,
.badge-manual { background: var(--warn-bg); color: var(--warn-ink); border-color: var(--warn-border); }
/* planned slot tag (no value yet) — neutral grey */
.badge-tag    { background: var(--neutral-bg); color: var(--neutral-ink); border-color: var(--neutral-border); }

.chip {
  display: inline-block;
  font-family: var(--font-ui);
  font-size: 0.72rem;
  font-weight: 650;
  line-height: 1.4;
  padding: 0.03em 0.55em;
  border-radius: 999px;
  border: 1px solid transparent;
  white-space: nowrap;
}
.chip-high { background: var(--ok-bg);      color: var(--ok-ink);      border-color: var(--ok-border); }      /* High   — muted green */
.chip-med  { background: var(--warn-bg);    color: var(--warn-ink);    border-color: var(--warn-border); }    /* Medium — muted amber */
.chip-low  { background: var(--neutral-bg); color: var(--neutral-ink); border-color: var(--neutral-border); } /* Low    — neutral grey */

/* verdict pills inside the KEY SIGNAL table */
.verdict { font-weight: 700; }
.verdict-confirm { color: var(--ok-ink); }
.verdict-diverge { color: var(--bad-ink); }
.verdict-inconc  { color: var(--color-accent); }
.tick { color: var(--color-accent); font-weight: 700; }

/* legend strip */
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-5);
  align-items: center;
  font-size: var(--fs-meta);
  color: var(--color-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  margin: var(--space-5) 0;
}
.legend .legend-item { display: inline-flex; align-items: center; gap: var(--space-2); }

/* =========================================================================
   CALLOUT — one-line conclusion / verdict summary
   ========================================================================= */
.callout {
  border-left: 3px solid var(--color-accent);
  background: var(--color-accent-tint);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: var(--space-3) var(--space-4);
  margin: var(--space-4) 0;
  font-family: var(--font-body);
  font-size: 0.98rem;
  line-height: 1.65;
  color: var(--color-ink-soft);
}
.callout .label {
  font-family: var(--font-ui);
  font-size: var(--fs-eyebrow);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-accent);
  display: block;
  margin-bottom: var(--space-1);
}
.callout strong { color: var(--color-ink); }

/* =========================================================================
   CHART PLACEHOLDERS  (empty containers — SVG arrives in step ④.2)
   ========================================================================= */
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin: var(--space-5) 0;
}
.chart-ph {
  border: 1px dashed var(--color-rule-strong);
  border-radius: var(--radius-lg);
  background:
    repeating-linear-gradient(135deg,
      var(--color-surface) 0, var(--color-surface) 11px,
      var(--color-surface-2) 11px, var(--color-surface-2) 22px);
  min-height: 220px;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
}
.chart-ph .ph-tag {
  align-self: flex-start;
  font-size: var(--fs-eyebrow);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-accent);
  background: var(--color-bg);
  border: 1px solid var(--color-rule-strong);
  border-radius: var(--radius-sm);
  padding: 0.15em 0.55em;
}
.chart-ph .ph-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-faint);
  font-size: var(--fs-meta);
  text-align: center;
}
.chart-ph .ph-caption {
  font-size: var(--fs-meta);
  color: var(--color-muted);
  border-top: 1px solid var(--color-rule);
  padding-top: var(--space-2);
}
.chart-ph .ph-caption strong { color: var(--color-ink-soft); }

/* =========================================================================
   MISC
   ========================================================================= */
ul.tight { margin: var(--space-2) 0 var(--space-4); padding-left: 1.3em; }
ul.tight li { margin: var(--space-1) 0; color: var(--color-ink-soft); font-family: var(--font-body); }
ul.tight li code { font-family: var(--font-mono); font-size: 0.85em; color: var(--color-accent); }
.foot {
  margin-top: var(--space-8);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-rule);
  font-size: var(--fs-meta);
  color: var(--color-faint);
}

@media (max-width: 680px) {
  .page { padding: var(--space-6) var(--space-4) var(--space-7); }
  .chart-grid { grid-template-columns: 1fr; }
  table.memo { font-size: 0.84rem; }
}

/* =========================================================================
   PRINT / PDF  — light, ink-saving, no heavy fills, avoid broken tables
   ========================================================================= */
@media print {
  :root { --fs-body: 10.5pt; }
  body { font-size: 10.5pt; line-height: 1.5; }
  .page { max-width: none; margin: 0; padding: 0; }
  .report-head { border-top-width: 2pt; }
  .part { margin-top: 22pt; }
  h2.part-title, h3.sub-title, h4.minor-title { page-break-after: avoid; }
  .table-wrap, .chart-grid, .callout { page-break-inside: avoid; }
  table.memo { font-size: 8.6pt; }
  table.memo thead th { background: #f2f4f6 !important; }
  tr.is-selected td { background: #eef2f8 !important; }
  .chart-ph { background: #fff !important; border: 1pt dashed #aab2bd; min-height: 150px; }
  .legend { background: #fff !important; }
  a { color: inherit; text-decoration: none; }
  /* every status color is a light fill — already ink-safe */
}
""".strip()


# Harmonises the plain tags the constrained markdown renderer emits with the
# design tokens above. The design CSS targets bespoke classes (ul.tight, .callout,
# table.memo …); these rules cover the generic <ul>/<li>, <blockquote>, <hr> and
# h5/h6 the renderer produces so nothing falls back to unstyled browser defaults.
_SUPPLEMENTAL_CSS = """
/* ---- supplemental: generic tags emitted by the string-renderer ---------- */
ul { margin: var(--space-2) 0 var(--space-4); padding-left: 1.35em; }
li { margin: var(--space-1) 0; color: var(--color-ink-soft); font-family: var(--font-body); }
li > strong { color: var(--color-ink); }
li code { font-family: var(--font-mono); font-size: 0.85em; color: var(--color-accent); }
ul ul { margin: var(--space-1) 0; }
blockquote {
  margin: var(--space-4) 0;
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-rule-strong);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  background: var(--color-surface);
  color: var(--color-ink-soft);
  font-family: var(--font-body);
  font-size: 0.95rem;
  line-height: 1.6;
}
blockquote strong { color: var(--color-ink); }
blockquote code { font-family: var(--font-mono); font-size: 0.86em; color: var(--color-accent); }
hr { border: 0; border-top: 1px solid var(--color-rule); margin: var(--space-6) 0; }
h5, h6 {
  font-family: var(--font-ui);
  font-size: var(--fs-h4);
  font-weight: 650;
  margin: var(--space-4) 0 var(--space-2);
  color: var(--color-ink);
}

/* ---- ④.2: a .chart-ph carrying a real inline-SVG chart (is-filled) drops the
   dashed "placeholder" hatch for a clean solid panel; the dashed hatch stays for
   the "no data this run" slots so a missing chart still reads as a gap, not a
   chart. The empty slots reuse the design's .ph-body / .ph-caption verbatim. --- */
.chart-at-glance { margin: var(--space-5) 0 var(--space-6); }
.chart-at-glance .part-eyebrow { margin-bottom: var(--space-2); }
.chart-ph.is-filled {
  background: var(--color-bg);
  border: 1px solid var(--color-rule);
}
.chart-ph .chart-body { width: 100%; margin: var(--space-2) 0; }
.chart-ph .chart-body svg { display: block; width: 100%; height: auto; }
""".strip()


_CSS = _DESIGN_CSS + "\n\n" + _SUPPLEMENTAL_CSS


_LEGEND = (
    '<div class="legend">'
    '<span class="legend-item"><span class="badge badge-filled">AUTO ✓ FILLED</span> auto-extracted / computed</span>'
    '<span class="legend-item"><span class="badge badge-warn">⚠ NEEDS HUMAN REVIEW</span> manual / unfilled</span>'
    '<span class="legend-item"><span class="badge badge-tag">planned slot</span> tag, no value yet</span>'
    '<span class="legend-item">confidence '
    '<span class="chip chip-high">High</span>'
    '<span class="chip chip-med">Medium</span>'
    '<span class="chip chip-low">Low</span></span>'
    "</div>"
)


# --------------------------------------------------------------------------- #
# ④.2 — inline-SVG charts from the facts bundle (subject-agnostic, field-driven)
#
# The charts are built by analysis_layer.render.charts from the in-memory facts
# bundle dict (build_facts_bundle output) the caller passes as ``facts=``. The
# renderer stays PURE/offline — it reads the dict it is handed, never the disk.
# Placement (TD-023): the design file parks the .chart-grid INSIDE the On-Chain
# Metrics section, but that section has no stable anchor in the constrained
# markdown, so we render the grid in an "At a glance" panel right after the legend
# and before the body (the prompt's stated default) — one canonical spot, always
# present whenever facts are supplied.
# --------------------------------------------------------------------------- #
def _chart_figure(tag: str, svg: Optional[str], caption: str) -> str:
    """One .chart-ph cell: the real inline SVG when present (is-filled), else the
    design's dashed placeholder with an honest 'no data this run' body. The
    caption is data-derived (source / fiscal year) — never fabricated."""
    head = f'<span class="ph-tag">{_escape(tag)}</span>'
    cap = f'<figcaption class="ph-caption">{caption}</figcaption>'
    if svg:
        return (
            '<figure class="chart-ph is-filled">'
            f'{head}<div class="chart-body">{svg}</div>{cap}</figure>'
        )
    return (
        '<figure class="chart-ph">'
        f'{head}<div class="ph-body">no data this run</div>{cap}</figure>'
    )


def _supply_caption(momentum) -> str:
    """Data-derived caption for the supply-momentum chart (windows + source)."""
    if not momentum:
        return "Net supply change by window — <strong>no data this run</strong>."
    windows = ", ".join(str(m.get("window")) for m in momentum if m.get("window"))
    srcs = sorted({m.get("source") for m in momentum if m.get("source")})
    src = f" (<code>{_escape(srcs[0])}</code>)" if len(srcs) == 1 else ""
    return f"<strong>Supply momentum</strong> — net supply change {windows}{src}."


def _financials_caption(fin) -> str:
    """Data-derived caption for the issuer-financials chart (fiscal year + source)."""
    if not fin:
        return "Issuer financials — <strong>no data this run</strong>."
    fy = fin.get("fiscal_year")
    fy_txt = f" (FY{fy})" if fy is not None else ""
    srcs = sorted({
        cell.get("source")
        for cell in fin.values()
        if isinstance(cell, dict) and cell.get("source")
    })
    src = f" (<code>{_escape(srcs[0])}</code>)" if len(srcs) == 1 else ""
    issuer = fin.get("issuer")
    who = f"{_escape(issuer)} " if issuer else ""
    return f"<strong>{who}issuer financials</strong>{fy_txt} — flow vs stock{src}."


def _chart_section(facts: Optional[dict]) -> str:
    """The 'At a glance' chart grid built from the facts bundle, or ``""`` when
    ``facts`` is None (backward-compatible: no chart section at all)."""
    if facts is None:
        return ""
    from analysis_layer.render.charts import (
        issuer_financials_svg, supply_momentum_svg,
    )
    momentum = facts.get("supply_momentum")
    fin = facts.get("issuer_financials")
    supply_svg = supply_momentum_svg(momentum)
    fin_svg = issuer_financials_svg(fin)
    grid = (
        '<div class="chart-grid">'
        + _chart_figure("Supply momentum", supply_svg, _supply_caption(momentum))
        + _chart_figure("Issuer financials", fin_svg, _financials_caption(fin))
        + "</div>"
    )
    return (
        '<section class="chart-at-glance">'
        '<p class="part-eyebrow">At a glance</p>'
        f"{grid}</section>\n"
    )


def render_html(markdown_text: str, *, title: str = None, facts: dict = None) -> str:
    """Render a crypto research report (markdown) into ONE self-contained HTML
    string: the approved institutional-clean design, inline CSS only, no external
    resources, deterministic. Two pre-passes run first — the coaching-channel
    strip backstop and the ``⭐ → ★`` KEY SIGNAL normalisation. ``title`` defaults
    to the report's Part 0 ``Title`` line (or first ``# `` header).

    ``facts`` is the in-memory facts-bundle dict (``build_facts_bundle`` output,
    TD-041) — when supplied, an 'At a glance' grid of subject-agnostic inline-SVG
    charts (supply momentum + issuer financials) is drawn from its fields; a field
    that is absent renders an honest 'no data this run' placeholder rather than a
    fabricated chart. ``facts=None`` (the default) emits NO chart section, so
    existing callers are unaffected. The renderer stays pure/offline — ``facts``
    is read from memory, never from disk."""
    md = strip_coaching(markdown_text)
    md = md.replace("⭐", "★")  # KEY SIGNAL marker — display normalisation only
    doc_title = _doc_title(md, title)
    header = _header_block(md, doc_title)
    charts = _chart_section(facts)
    body = _markdown_to_body(md)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_escape(doc_title)}</title>\n"
        f"<style>\n{_CSS}\n</style>\n"
        "</head>\n<body>\n"
        '<div class="page">\n'
        f"{header}\n"
        f"{_LEGEND}\n"
        f"{charts}"
        f"{body}\n"
        "</div>\n"
        "</body>\n</html>\n"
    )
