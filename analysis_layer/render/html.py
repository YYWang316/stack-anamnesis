"""analysis_layer/render/html.py — PURE markdown→HTML renderer (B.4, TD-040).

Turns a crypto research report (the markdown that ``orchestrate`` writes to
``meta/reports/<slug>_<utc>.md``) into ONE self-contained HTML file: inline CSS,
no external ``<link>`` / ``<script src>`` — fully portable, opens anywhere.

The value-add over the raw markdown is that the report's *status markers* become
visually scannable. The pipeline annotates every metric slot with a tag the eye
otherwise has to hunt for; this renderer turns each into a coloured badge/chip:

  * ``[AUTO ✓ FILLED: …]`` / ``[SEMI-AUTO ✓ COMPUTED: …]`` → green "machine-filled"
  * ``⚠ NEEDS HUMAN REVIEW [SEMI-AUTO]`` / ``⚠ MANUAL`` / ``[MANUAL: …]`` → amber
  * ``⚠ UNFILLED [AUTO]`` → amber (flagged, NOT fabricated)
  * ``[AUTO: …]`` / ``[SEMI-AUTO: …]`` planned-but-unfilled tags → neutral grey
  * confidence ``High`` / ``Medium`` / ``Low`` → green / amber / grey chips

It is a focused converter for the constrained markdown the template emits
(ATX headers, GFM pipe tables, ``-``/``*`` lists with 4-space nesting, ``>``
blockquotes, ``---`` rules, ``**bold**`` / ``*italic*`` / `` `code` `` inline) —
deliberately NOT a general markdown engine and NOT coupled to the inherited
equity HTML machinery. PURE + deterministic: same markdown in → byte-identical
HTML out (no clock, no network, no randomness).
"""
from __future__ import annotations

import re
from typing import List, Tuple

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
    (so the Evidence Table's Confidence column is scannable too)."""
    bare = cell.strip()
    if bare.lower() in _CHIP_CLASS:
        return _chip(bare)
    return _inline(cell)


def _render_table(lines: List[str], i: int) -> Tuple[str, int]:
    header = _split_row(lines[i])
    i += 2  # header row + separator row
    rows: List[List[str]] = []
    while i < len(lines) and "|" in lines[i] and not _is_blank(lines[i]):
        rows.append(_split_row(lines[i]))
        i += 1
    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{_inline(c)}</th>" for c in header]
    out += ["</tr></thead>", "<tbody>"]
    for row in rows:
        out.append("<tr>")
        out += [f"<td>{_render_table_cell(c)}</td>" for c in row]
        out.append("</tr>")
    out += ["</tbody>", "</table>"]
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


def _render_paragraph(lines: List[str], i: int) -> Tuple[str, int]:
    parts: List[str] = []
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
        parts.append(_inline(ln.strip()))
        i += 1
    return "<p>" + " ".join(parts) + "</p>", i


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
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
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


def _first_h1(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            return m.group(1).strip()
    return ""


# --------------------------------------------------------------------------- #
# the document (inline CSS — no external resources)
# --------------------------------------------------------------------------- #
_CSS = """
:root { color-scheme: light; }
body { max-width: 920px; margin: 2rem auto; padding: 0 1.25rem;
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #1f2328; background: #ffffff; }
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin: 1.6em 0 0.5em; }
h1 { font-size: 1.9rem; border-bottom: 2px solid #e3e6ea; padding-bottom: .3em; }
h2 { font-size: 1.45rem; border-bottom: 1px solid #eaecef; padding-bottom: .25em; }
h3 { font-size: 1.2rem; } h4 { font-size: 1.05rem; }
p { margin: .6em 0; }
ul { margin: .4em 0; padding-left: 1.4em; }
li { margin: .2em 0; }
code { background: #f4f5f7; border-radius: 4px; padding: .1em .35em;
  font: 0.86em "SFMono-Regular", Menlo, Consolas, monospace; }
blockquote { margin: .8em 0; padding: .5em .9em; border-left: 4px solid #d7dbe0;
  background: #f8f9fb; color: #515a64; }
hr { border: 0; border-top: 1px solid #e3e6ea; margin: 1.6em 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .94em; }
th, td { border: 1px solid #dfe2e5; padding: .45em .7em; text-align: left;
  vertical-align: top; }
th { background: #f4f6f8; font-weight: 600; }
tbody tr:nth-child(even) { background: #fbfcfd; }
.badge { display: inline-block; border-radius: 5px; padding: .05em .45em;
  font-size: .8em; font-weight: 600; white-space: nowrap; }
.badge-filled { background: #e4f5ea; color: #1a7f43; border: 1px solid #aedcc0; }
.badge-warn, .badge-manual { background: #fdf3e3; color: #9a6400; border: 1px solid #f0d29a; }
.badge-tag { background: #eef0f2; color: #5a636c; border: 1px solid #d4d8dd; }
.chip { display: inline-block; border-radius: 999px; padding: .03em .55em;
  font-size: .82em; font-weight: 600; }
.chip-high { background: #e4f5ea; color: #1a7f43; }
.chip-med  { background: #fdf3e3; color: #9a6400; }
.chip-low  { background: #eef0f2; color: #5a636c; }
.legend { margin: 1em 0 1.5em; padding: .7em .9em; background: #f8f9fb;
  border: 1px solid #e7eaee; border-radius: 8px; font-size: .85em; color: #515a64; }
.legend .badge, .legend .chip { margin-right: .15em; }
.legend span + span { margin-left: .9em; }
""".strip()


_LEGEND = (
    '<div class="legend">'
    '<span><span class="badge badge-filled">machine-filled</span> auto-extracted / computed</span>'
    '<span><span class="badge badge-warn">⚠ needs human</span> review / manual / unfilled</span>'
    '<span><span class="badge badge-tag">planned</span> slot tag, no value yet</span>'
    '<span>confidence '
    '<span class="chip chip-high">High</span>'
    '<span class="chip chip-med">Medium</span>'
    '<span class="chip chip-low">Low</span></span>'
    "</div>"
)


def render_html(markdown_text: str, *, title: str = None) -> str:
    """Render a crypto research report (markdown) into ONE self-contained HTML
    string: inline CSS only, no external resources, deterministic. ``title``
    defaults to the document's first ``# `` header (or a generic fallback)."""
    doc_title = title or _first_h1(markdown_text) or "Crypto Research Report"
    body = _markdown_to_body(markdown_text)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_escape(doc_title)}</title>\n"
        f"<style>\n{_CSS}\n</style>\n"
        "</head>\n<body>\n"
        f"{_LEGEND}\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )
