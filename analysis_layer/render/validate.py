"""analysis_layer/render/validate.py — the rendered-HTML validator (④.3 TD-047).

The HTML-integrity backstop — the LAST piece of ④. A PURE, stdlib-only,
no-network gate over the FINAL rendered HTML (``render_html`` output). It is
DISTINCT from ⑤ (the numbers / confidence-cap gate, TD-048): this one never looks
at a value's correctness, only at the document's integrity — that the coaching
channel did not leak, that the file stays self-contained, that the design
structure and status badges survived rendering, and that any inline-SVG chart
carries sane geometry.

It is wired FAIL-CLOSED in the orchestrator: a non-empty result RAISES, so a
report that leaks coaching or pulls an external resource is never shipped. The
real rendered report returns ``[]`` (calibrated against the live USDC HTML), so
the live path is unaffected.

Deterministic: same HTML in → same violations out (no clock, no network, no
randomness).
"""
from __future__ import annotations

import re
from typing import List

# --------------------------------------------------------------------------- #
# coaching channel — must never reach the reader (verifies the ④.1 + writer strip)
#
# ⚠ CALIBRATION / DEVIATION (TD-023). The ④.3 brief said "none of 'GUIDANCE' /
# 'TRAP' / '↳ Cap check' appear in the output" as a bare substring test, AND that
# the real USDC report must return []. Those two conflict: the live v2 template's
# front matter LEGITIMATELY names the coaching channel in PRESERVED prose — a
# "VERSION NOTE … M5 GUIDANCE/TRAP channel separating writer-coaching from the
# deliverable body" blockquote and a "↳ Cap check pointers" reading-convention
# note (with inline <code>&gt; GUIDANCE</code> mentions). A bare substring check
# fail-closes on that legitimate description. The SUBSTANCE the gate protects is
# "no coaching BLOCKQUOTE leaked" — and coaching is, by definition, a blockquote
# whose FIRST content is one of these markers (exactly what the ④.1 strip targets;
# see render/html.py strip_coaching). So we anchor the check to a marker LEADING a
# blockquote: this stays FAIL-CLOSED against the actual leak vector (an unstripped
# coaching blockquote) while not flagging prose that merely names the channel —
# strictly better than downgrading the whole check to a warning.
# --------------------------------------------------------------------------- #
_COACHING_MARKERS = ("GUIDANCE", "TRAP", "↳ Cap check")
# a coaching marker at the START of a blockquote (optionally behind an inline tag
# like <strong>/<em> the renderer emits for `> **GUIDANCE**`).
_COACHING_LEAK_RE = re.compile(
    r"<blockquote>(?:\s*<[^>]+>)*\s*(" + "|".join(re.escape(m) for m in _COACHING_MARKERS) + ")"
)

# --------------------------------------------------------------------------- #
# self-containment — no external resource of any kind
# --------------------------------------------------------------------------- #
_EXTERNAL_MARKERS = (
    "http://", "https://", "<script", "<link", "src=", "@import", "cdn",
)

# --------------------------------------------------------------------------- #
# design structure — catches a renderer regression that drops the design
# --------------------------------------------------------------------------- #
_STRUCTURE_REQUIRED = (
    ('class="page"', "design structure: missing class=\"page\""),
    ('class="report-head"', "design structure: missing class=\"report-head\""),
    ('class="legend"', "design structure: missing class=\"legend\""),
    ('<table class="memo">', "design structure: missing <table class=\"memo\">"),
    (":root", "design structure: missing :root token block"),
    ("@media print", "design structure: missing @media print block"),
)

# --------------------------------------------------------------------------- #
# SVG geometry — numeric attributes that must be finite & non-negative.
# Scoped to attribute VALUES inside <svg> regions, NEVER substring-matched
# against free text (so prose words like "fi-nan-cials" / "cove-nan-t" are safe).
# --------------------------------------------------------------------------- #
_GEOM_ATTRS = frozenset((
    "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2",
    "cx", "cy", "r", "rx", "ry", "points", "d",
))
# an attribute occurrence: name NOT preceded by a word char or hyphen, so
# "stroke-width" / "max-width" do not register as the geom attr "width".
_ATTR_RE = re.compile(r'(?<![\w-])([A-Za-z][A-Za-z0-9]*)\s*=\s*"([^"]*)"')
# a numeric token within an attribute value: an optional sign, then a number OR a
# non-finite literal (nan / inf / infinity). The "100%" form yields "100" (the
# trailing % is left out) — a positive number, correctly not flagged.
_NUM_RE = re.compile(
    r"[-+]?(?:\d+\.\d+|\.\d+|\d+\.|\d+|nan|inf(?:inity)?)", re.IGNORECASE
)
_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)


def _geometry_violations(html: str) -> List[str]:
    """NaN / Inf / negative in any SVG numeric geometry attribute → violations.

    Operates ONLY on attribute values inside ``<svg>…</svg>`` regions; text
    content is never inspected, so the check cannot be tripped by prose."""
    out: List[str] = []
    for region in _SVG_RE.findall(html):
        for name, value in _ATTR_RE.findall(region):
            if name not in _GEOM_ATTRS:
                continue
            for tok in _NUM_RE.findall(value):
                low = tok.lower()
                if "nan" in low or "inf" in low:
                    out.append(
                        f"chart geometry: non-finite {name}=\"{value}\" (token {tok!r})"
                    )
                    continue
                try:
                    num = float(tok)
                except ValueError:  # pragma: no cover - regex guarantees parseable
                    continue
                if num < 0:
                    out.append(
                        f"chart geometry: negative {name}=\"{value}\" (token {tok!r})"
                    )
    return out


def validate_report_html(html: str, *, facts_present: bool = False) -> List[str]:
    """Validate the FINAL rendered report HTML. PURE — returns a list of violation
    strings (empty = clean). ``facts_present`` enables the chart-integrity checks
    (the caller passes ``facts is not None``).

    Checks: no coaching leak · self-contained (no external resource) · design
    structure present · ≥1 status badge applied · (when ``facts_present``) the
    "At a glance" chart section exists with sane SVG geometry · well-formed-ish."""
    violations: List[str] = []

    # 1. no coaching leak — a coaching marker LEADING a blockquote (see the
    #    CALIBRATION note above for why this is anchored, not a bare substring)
    for m in _COACHING_LEAK_RE.finditer(html):
        violations.append(f"coaching leak: {m.group(1)!r} leads a blockquote")

    # 2. self-contained — no external resource
    low = html.lower()
    for marker in _EXTERNAL_MARKERS:
        if marker in low:
            violations.append(f"external resource: {marker!r} found")

    # 3. design structure present
    for needle, message in _STRUCTURE_REQUIRED:
        if needle not in html:
            violations.append(message)

    # 4. badges applied (soft — prove the marker-wrapping ran, not that every
    #    raw marker wrapped)
    if not re.search(r"badge-(?:filled|warn|manual|tag)", html):
        violations.append("badges: no status badge span found (marker-wrap did not run)")

    # 5. chart integrity (only when a facts bundle was supplied)
    if facts_present:
        if 'class="chart-at-glance"' not in html:
            violations.append('chart integrity: missing "At a glance" section')
        violations.extend(_geometry_violations(html))

    # 6. well-formed-ish
    if not html.startswith("<!DOCTYPE html>"):
        violations.append("well-formed: missing <!DOCTYPE html> prologue")
    if not re.search(r"<html\b", html):
        violations.append("well-formed: missing <html> element")
    if "</html>" not in html:
        violations.append("well-formed: missing </html> closing tag")

    return violations
