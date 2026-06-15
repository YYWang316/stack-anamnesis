"""analysis_layer/render/provenance.py — "where each number came from" (v1, TD-051).

PURE, self-contained, deterministic surfacing of data provenance for the report
renderer. Like ``charts.py`` it reads ONLY the facts bundle (``build_facts_bundle``
output, TD-041) and is driven entirely by the bundle's FIELD NAMES — never a USDC
literal or a hard-coded subject. Two pieces, both ``facts=``-driven:

  1. ``data_sources_section(facts)`` — a "Data Sources" block listing the DISTINCT
     sources that actually back a value (``metrics[].source`` /
     ``supply_momentum[].source`` / each ``issuer_financials`` cell's ``source``),
     mapped to human-readable company names with the as-of date (or range).

  2. ``build_prov_index`` + ``wrap_body_numbers`` — a native ``title`` tooltip on
     each machine-traceable number in the body: ``<span class="src" title="CoinGecko
     · as of 2026-05-27">$76.5B</span>``. The value→source map is built from the
     SAME canonical renderings the ⑤.1 numbers-trace gate uses (reused from
     ``analysis_layer.qc.numbers``), so the strings match what is actually in the
     report. ONLY unambiguous matches are wrapped — a display string that maps to
     more than one distinct (source, as-of) is SKIPPED (honesty over coverage: never
     attach a possibly-wrong source).

★ Constraints (same family as ④.1/④.2): NO URLs (titles carry only "Company · as of
DATE"), NO ``<script>`` / JavaScript, NO external resource — so the ④.3
``validate_report_html`` self-containment gate still passes UNCHANGED. ``facts=None``
→ no Data Sources section and no wrapping (existing behaviour untouched). The wrap is
applied to body TEXT ONLY via a tag-aware split, so it never lands inside a tag,
attribute, or SVG. Deterministic: same facts → byte-identical output.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from analysis_layer.qc.numbers import (
    _metric_forms, _normalise, _signed_usd_forms,
)

# --------------------------------------------------------------------------- #
# source slug → human-readable company name
# --------------------------------------------------------------------------- #
_SOURCE_DISPLAY = {
    "coingecko": "CoinGecko",
    "sec_edgar": "SEC EDGAR",
    "defillama": "DefiLlama",
    "alchemy": "Alchemy",
    "etherscan": "Etherscan",
    "coinmarketcap": "CoinMarketCap",
}


def _display_name(slug: str) -> str:
    """A source slug → company name; unknown slug → a title-cased fallback
    (``some_source`` → ``Some Source``)."""
    if slug in _SOURCE_DISPLAY:
        return _SOURCE_DISPLAY[slug]
    return slug.replace("_", " ").title()


def _date(as_of: Any) -> str:
    """An ISO ``as_of`` timestamp → its ``YYYY-MM-DD`` date part (deterministic);
    ``""`` when absent/unparseable."""
    if not isinstance(as_of, str) or not as_of:
        return ""
    return as_of.split("T", 1)[0][:10]


def _attr_escape(text: str) -> str:
    """Escape a string for safe use inside an HTML attribute value. Company names
    and dates are plain ASCII, but escape defensively all the same."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


# --------------------------------------------------------------------------- #
# Piece 1 — the "Data Sources" section
# --------------------------------------------------------------------------- #
def _collect_source_dates(facts: Mapping[str, Any]) -> Dict[str, Set[str]]:
    """``{source_slug -> set of YYYY-MM-DD dates}`` over every bundle value that
    carries a source: spot metrics, supply-momentum windows, financial cells."""
    by_source: Dict[str, Set[str]] = defaultdict(set)

    def _add(source: Any, as_of: Any) -> None:
        if isinstance(source, str) and source:
            by_source[source].add(_date(as_of))

    for m in facts.get("metrics", []) or ():
        if isinstance(m, Mapping):
            _add(m.get("source"), m.get("as_of"))
    for sm in facts.get("supply_momentum", []) or ():
        if isinstance(sm, Mapping):
            _add(sm.get("source"), sm.get("as_of"))
    financials = facts.get("issuer_financials")
    if isinstance(financials, Mapping):
        for cell in financials.values():
            if isinstance(cell, Mapping):
                _add(cell.get("source"), cell.get("as_of"))
    return by_source


def _date_phrase(dates: Set[str]) -> str:
    """A set of dates → ``as of DATE`` (single) or ``DATE – DATE`` (range);
    ``""`` when no usable date."""
    clean = sorted(d for d in dates if d)
    if not clean:
        return ""
    if len(clean) == 1:
        return f"as of {clean[0]}"
    return f"as of {clean[0]} – {clean[-1]}"


def data_sources_section(facts: Optional[Mapping[str, Any]]) -> str:
    """The "Data Sources" block (distinct human-readable sources + as-of date/range)
    appended at the end of the report. ``facts=None`` / no sourced value → ``""``
    (backward-compatible: no section at all)."""
    if not facts:
        return ""
    by_source = _collect_source_dates(facts)
    if not by_source:
        return ""
    rows: List[Tuple[str, str]] = []
    for slug, dates in by_source.items():
        rows.append((_display_name(slug), _date_phrase(dates)))
    rows.sort()  # deterministic — by company display name

    items = []
    for name, phrase in rows:
        tail = f" — {_attr_escape(phrase)}" if phrase else ""
        items.append(
            f'<li><span class="src-name">{_attr_escape(name)}</span>{tail}</li>'
        )
    return (
        '<section class="data-sources">'
        '<p class="part-eyebrow">Data Sources</p>'
        '<ul class="src-list">' + "".join(items) + "</ul>"
        "</section>\n"
    )


# --------------------------------------------------------------------------- #
# Piece 2 — value → (source, as-of) index + tag-safe body wrapping
# --------------------------------------------------------------------------- #
def _add_forms(multimap: Dict[str, Set[Tuple[str, str]]], forms: Set[str],
               source: Any, as_of: Any) -> None:
    """Record each canonical form (plus a Unicode-minus variant) against the
    (source, date) pair it traces to. The variant lets a key built from the
    filler's ASCII ``-`` also match the writer's Unicode ``−`` in the body."""
    if not isinstance(source, str) or not source:
        return
    pair = (source, _date(as_of))
    for f in forms:
        if not f:
            continue
        multimap[f].add(pair)
        if "-" in f:
            multimap[f.replace("-", "−")].add(pair)


def build_prov_index(
    facts: Optional[Mapping[str, Any]]
) -> Optional[Dict[str, str]]:
    """``{canonical_display_string -> "Company · as of DATE"}`` for every UNAMBIGUOUS
    machine value in the bundle. A string mapping to more than one distinct
    (source, as-of) pair is dropped (never attach a possibly-wrong source). Reuses
    the ⑤.1 gate's canonical renderings so the keys match the report. ``None`` when
    ``facts`` is absent or nothing unambiguous remains (caller then wraps nothing).
    """
    if not facts:
        return None
    subject = str(facts.get("subject") or "")
    multimap: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

    # 1. spot metrics
    for m in facts.get("metrics", []) or ():
        if not isinstance(m, Mapping):
            continue
        value = m.get("value")
        if value is None:
            continue
        forms = _metric_forms(value, m.get("unit", ""), m.get("metric", "?"),
                              subject)
        _add_forms(multimap, forms, m.get("source"), m.get("as_of"))

    # 2. supply-momentum windows — filler-exact percent + signed absolute change
    for sm in facts.get("supply_momentum", []) or ():
        if not isinstance(sm, Mapping):
            continue
        src, as_of = sm.get("source"), sm.get("as_of")
        pct = sm.get("net_change_pct")
        if pct is not None:
            _add_forms(multimap, {f"{float(pct):+.2f}%"}, src, as_of)
        abs_change = sm.get("net_change_abs")
        if abs_change is not None:
            _add_forms(multimap, _signed_usd_forms(float(abs_change)), src, as_of)

    # 3. issuer SEC financials — each non-null cell carries its own value/unit
    financials = facts.get("issuer_financials")
    if isinstance(financials, Mapping):
        for key, cell in financials.items():
            if not isinstance(cell, Mapping):
                continue
            value = cell.get("value")
            if value is None:
                continue
            forms = _metric_forms(value, cell.get("unit", "USD"), key, subject)
            _add_forms(multimap, forms, cell.get("source"), cell.get("as_of"))

    # keep ONLY unambiguous strings (exactly one distinct source/as-of pair)
    index: Dict[str, str] = {}
    for display, pairs in multimap.items():
        if len(pairs) != 1:
            continue
        source, date = next(iter(pairs))
        title = _display_name(source)
        if date:
            title += f" · as of {date}"
        index[display] = title
    return index or None


# split a fragment into (text, tag, text, tag, …) — odd indices are tags
_TAG_SPLIT = re.compile(r"(<[^>]*>)")


def _wrap_regex(index: Mapping[str, str]) -> "re.Pattern[str]":
    """One alternation over the index keys, longest first (so a longer value is
    matched before any shorter substring of it). Bounded so a key never matches
    inside a larger number/word: not preceded by a word char / ``$`` / ``.`` and
    not followed by a word char / ``%``."""
    keys = sorted(index.keys(), key=len, reverse=True)
    alt = "|".join(re.escape(k) for k in keys)
    return re.compile(r"(?<![\w$.])(" + alt + r")(?![\w%])")


def wrap_body_numbers(body_html: str, index: Optional[Mapping[str, str]]) -> str:
    """Wrap each unambiguous machine number in ``body_html`` with a native ``title``
    tooltip span. TAG-SAFE: the body is split on tags and only TEXT segments are
    rewritten, so a number inside a tag / attribute is never touched (and the body
    carries no SVG — charts live in their own fragment). ``index`` falsy → returned
    unchanged. Deterministic."""
    if not index:
        return body_html
    rx = _wrap_regex(index)

    def _sub(m: "re.Match[str]") -> str:
        value = m.group(1)
        title = index.get(value) or index.get(value.replace("−", "-"))
        if not title:
            return value
        return f'<span class="src" title="{_attr_escape(title)}">{value}</span>'

    parts = _TAG_SPLIT.split(body_html)
    for i in range(0, len(parts), 2):  # even indices are text, odd are tags
        if parts[i]:
            parts[i] = rx.sub(_sub, parts[i])
    return "".join(parts)
