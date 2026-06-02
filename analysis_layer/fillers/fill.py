"""The markdown template filler (B.2.8) — FINAL stage of the analysis-layer
trunk (extractor -> resolver -> aggregator -> filler).

``fill`` consumes the aggregator's ``ReconciledValue``s (trustworthy values +
confidence signals) and drops them into the research template's ``[AUTO]`` slots,
builds a data-layer Evidence Table (value · source · confidence), and leaves
``[SEMI-AUTO]`` / ``[MANUAL]`` slots FLAGGED for a human. The output is an
objective research markdown — NO YYFoundry brand voice (that lives in a separate
layer and stays OUT of the deliverable).

THE CARDINAL FAITHFULNESS RULE (QC integrity):
  * ONLY ``[AUTO]`` slots get auto-filled, and only with a real reconciled value.
  * ``[SEMI-AUTO]`` -> a visibly-flagged "needs human review" placeholder (a
    drafted suggestion is allowed only if flagged, never presented as final).
  * ``[MANUAL]`` -> placeholder left intact, flagged.
  * An ``[AUTO]`` slot with NO matching reconciled value stays flagged — we never
    fabricate a number, source, or claim for a slot the data doesn't cover.
  * A reconciled value with NO template slot is NOT dropped silently — it lands in
    the Evidence Table with a "no matching slot" note.

Two carry-over rules from the B.2.7 aggregator:
  a. SCOPE LABEL — scope is shown ONLY where it is a real fact (the two supply
     scopes: single-chain Ethereum-only vs cross-chain multi_chain). It is NEVER
     printed on price / market_cap / volume / rank, even though those carry a
     ``multi_chain`` tag internally.
  b. UNIT — every value renders with its OWN unit; when a cross-check compared two
     different units (DefiLlama circulating_supply is USD-peg vs CMC's tokens) the
     Evidence Table notes the mismatch rather than implying same-unit.

PURE: ``fill`` does no I/O and is deterministic — it derives the report date from
the data's own ``as_of`` timestamps, never the wall clock. A thin I/O wrapper
(``fill_template_file``) is provided for convenience but the core is testable on a
template string. This module does NOT import the extractors or the aggregator (the
caller wires the chain). OUT OF SCOPE: the orchestrator / front-door gate, B.3 web
third-source / red-team checks, and md->HTML / cards / DB (B.4+).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from analysis_layer.contract import ReconciledValue, SubjectRef

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
# Supply is the ONLY metric family that carries a meaningful scope split
# (single-chain Ethereum-only vs cross-chain aggregate). Scope is shown for these
# and suppressed everywhere else (carry-over rule a).
_SUPPLY_METRICS = frozenset({"total_supply", "circulating_supply"})

# agreement -> (confidence label, human note). Mirrors the template's H/M/L scale.
_CONFIDENCE: Dict[str, Tuple[str, str]] = {
    "agree": ("High", "cross-checked, within tolerance band"),
    "single_source": ("Medium", "single source — unverified"),
    "divergence": ("Low", "FLAG — a cross-check fell outside the band"),
}

# Human scope labels for the supply sub-bullets.
_SCOPE_HUMAN = {
    "single-chain": "single-chain",   # refined with the chain name when known
    "multi_chain": "cross-chain (multi_chain)",
}

# Sort order so a slot lists single-chain (Ethereum-only) before the cross-chain
# aggregate, and within a scope total_supply before circulating_supply.
_SCOPE_SORT = {"single-chain": 0, "multi_chain": 1, None: 2}

# Markers we recognise. SEMI-AUTO first so the alternation never mis-binds it to
# AUTO. A marker whose body still holds an angle-bracket placeholder (``<source>``)
# is a LEGEND/format definition, not a real slot — skipped (see ``_iter_marker``).
_MARKER_RE = re.compile(r"\[(SEMI-AUTO|MANUAL|AUTO):\s*([^\]]*)\]")

_ANY_SCOPE = "__ANY__"


# --------------------------------------------------------------------------- #
# slot registry — maps an [AUTO] marker line to the (metric, scope) facts it
# should hold. Matching is by stable keyword anchors present in the template
# prose; the FIRST spec whose keywords ALL appear in the (lowercased) line claims
# it. Order: most specific first. Adding a slot is a DATA edit here.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SlotSpec:
    name: str
    keywords: Tuple[str, ...]          # all must appear in the lowercased line
    metrics: Tuple[str, ...]           # metrics this slot accepts
    scope: str = _ANY_SCOPE            # exact scope, or _ANY_SCOPE
    # When True this slot lives behind a [SEMI-AUTO] marker but is FILLABLE from a
    # computed derivation (B.2.9): a matching value flips it to "[SEMI-AUTO ✓
    # COMPUTED]" instead of flag-for-human. A [SEMI-AUTO] slot WITHOUT a matching
    # value still flags as before. Only designed semi-fillable slots set this, so a
    # plain [SEMI-AUTO] line can never be auto-filled from an [AUTO] metric.
    computed: bool = False

    def matches_line(self, line_lower: str) -> bool:
        return all(k in line_lower for k in self.keywords)

    def accepts(self, rv: ReconciledValue) -> bool:
        if rv.metric not in self.metrics:
            return False
        return self.scope == _ANY_SCOPE or rv.scope == self.scope


SLOTS: Tuple[SlotSpec, ...] = (
    # change-layer supply momentum (B.2.9, TD-035) — a [SEMI-AUTO] slot that becomes
    # FILLABLE once the supply_change derivation computes a window. Anchored on the
    # Part 5.5 A "Net 7d / 30d supply change" line ("supply change" is unique to it;
    # "net flow" / "supply breakdown" lines do not contain it).
    SlotSpec("net_supply_change", ("supply change",),
             ("net_supply_change_7d", "net_supply_change_30d", "net_supply_change_90d"),
             _ANY_SCOPE, computed=True),
    # explicit per-scope supply slots (for templates that split the two scopes)
    SlotSpec("supply_eth", ("supply", "ethereum"), ("total_supply",), "single-chain"),
    SlotSpec("supply_single", ("supply", "single-chain"), ("total_supply",), "single-chain"),
    SlotSpec("supply_cross", ("supply", "cross-chain"), ("total_supply",), "multi_chain"),
    # combined stablecoin-supply slot (the real v1.2 template line) — holds BOTH
    # supply scopes + circulating supply, each rendered as a distinct sub-bullet.
    SlotSpec("stablecoin_supply", ("stablecoin supply",),
             ("total_supply", "circulating_supply"), _ANY_SCOPE),
    SlotSpec("circulating_supply", ("circulating supply",), ("circulating_supply",), _ANY_SCOPE),
    SlotSpec("total_supply", ("total supply",), ("total_supply",), _ANY_SCOPE),
    # market-data slots (present in token-centric templates; absent in v1.2)
    SlotSpec("market_cap_rank", ("market cap rank",), ("market_cap_rank",), _ANY_SCOPE),
    SlotSpec("market_cap", ("market cap",), ("market_cap",), _ANY_SCOPE),
    SlotSpec("price", ("price",), ("price",), _ANY_SCOPE),
    SlotSpec("volume_24h", ("24h volume",), ("volume_24h",), _ANY_SCOPE),
    SlotSpec("tvl", ("tvl",), ("tvl",), _ANY_SCOPE),
)


# --------------------------------------------------------------------------- #
# value rendering
# --------------------------------------------------------------------------- #
def _magnitude(value: float) -> Tuple[float, str]:
    """Scale a number into (mantissa, suffix) — T/B/M/K — for human display."""
    a = abs(value)
    if a >= 1e12:
        return value / 1e12, "T"
    if a >= 1e9:
        return value / 1e9, "B"
    if a >= 1e6:
        return value / 1e6, "M"
    if a >= 1e3:
        return value / 1e3, "K"
    return value, ""


def render_value(rv: ReconciledValue, subject_ref: Optional[SubjectRef]) -> str:
    """Human-readable rendering of a reconciled value, per its own unit.

    USD amounts -> ``$76.39B`` (or ``$0.9997`` for sub-$1000 price-like values);
    token counts -> ``52.57B USDC`` (the subject names the token); ordinal counts
    (rank) -> ``#6``. Full precision is preserved in the Evidence Table, never
    here.
    """
    value = rv.value
    unit = rv.unit
    symbol = subject_ref.subject if subject_ref is not None else (rv.metric or "")

    if unit == "count" or rv.metric == "market_cap_rank":
        return f"#{int(value)}"

    if unit == "USD":
        if abs(value) < 1000:               # price-like — keep 4 decimals
            return f"${value:,.4f}"
        scaled, suffix = _magnitude(value)
        return f"${scaled:,.2f}{suffix}"

    if unit == "tokens":
        if abs(value) < 1000:
            return f"{value:,.2f} {symbol}".rstrip()
        scaled, suffix = _magnitude(value)
        return f"{scaled:,.2f}{suffix} {symbol}".rstrip()

    # unknown unit -> faithful "value unit" (never silently drop the unit)
    return f"{value} {unit}"


def _chain_of(rv: ReconciledValue) -> Optional[str]:
    """The chain name a single-chain supply read came from (Etherscan tags it in
    provenance), or None. Lets the scope label read ``single-chain (ethereum)``
    instead of a hard-coded chain."""
    for ev in rv.inputs:
        prov = ev.provenance if isinstance(ev.provenance, Mapping) else {}
        chain = prov.get("chain")
        if isinstance(chain, str) and chain and not chain.startswith("chainid"):
            return chain
    return None


def _scope_label(rv: ReconciledValue) -> Optional[str]:
    """Human scope label, ONLY for supply metrics (carry-over rule a). Non-supply
    metrics return None so the renderer omits any scope annotation."""
    if rv.metric not in _SUPPLY_METRICS:
        return None
    base = _SCOPE_HUMAN.get(rv.scope, rv.scope or "unscoped")
    if rv.scope == "single-chain":
        chain = _chain_of(rv)
        if chain:
            return f"single-chain ({chain})"
    return base


# --------------------------------------------------------------------------- #
# cross-check / evidence helpers
# --------------------------------------------------------------------------- #
def _crosscheck_cell(rv: ReconciledValue) -> str:
    """The Evidence-Table cross-check cell from the audit trail.

    One segment per cross-check: ``vs <source> Δ<delta>% (band <band>%) ✓/✗``,
    plus the as_of gap (single-chain) and a UNIT-MISMATCH note (carry-over rule b)
    when the cross-check source reported a different unit than the chosen value.
    """
    ccs = rv.audit.get("cross_checks") if isinstance(rv.audit, Mapping) else None
    if not ccs:
        return "single source — unverified"
    unit_by_source = {ev.source: ev.unit for ev in rv.inputs}
    parts: List[str] = []
    for cc in ccs:
        src = cc.get("source")
        mark = "✓" if cc.get("within_band") else "✗ DIVERGENCE"
        seg = (f"vs {src} Δ{cc.get('delta', 0.0) * 100:.4f}% "
               f"(band {cc.get('band', 0.0) * 100:.4f}%) {mark}")
        if cc.get("gap_days") is not None:
            seg += f", gap {cc['gap_days']:.2f}d"
        other_unit = unit_by_source.get(src)
        if other_unit and other_unit != rv.unit:
            seg += f" [unit: {rv.unit} vs {other_unit}]"
        parts.append(seg)
    return "; ".join(parts)


def build_evidence_table(
    reconciled: List[ReconciledValue],
    placed: "set[Tuple[str, Optional[str]]]",
) -> str:
    """The data-layer Evidence Table — one row per reconciled fact, full precision.

    Confidence maps the aggregator's ``agreement`` signal (agree -> High,
    single_source -> Medium/Unverified, divergence -> Low/Flag). Scope is shown
    only for supply rows (rule a). A fact whose ``(metric, scope)`` is not in
    ``placed`` (no matching template slot) is flagged in its notes rather than
    dropped.
    """
    lines = [
        "",
        "## Auto Evidence Table — Data Layer `[AUTO — B.2.8 filler]`",
        "",
        "> One row per reconciled fact (full precision). **Confidence** maps the "
        "aggregator's agreement signal; **Cross-check** shows each corroborating "
        "source's relative delta vs the tolerance band from the audit trail. "
        "Values here are the authority's actual number — never an average.",
        "",
        "| # | Metric | Scope | Value (exact) | Unit | Source | As of | Confidence | Cross-check / notes |",
        "|---|--------|-------|---------------|------|--------|-------|------------|---------------------|",
    ]
    for i, rv in enumerate(reconciled, 1):
        scope = rv.scope if rv.metric in _SUPPLY_METRICS else "—"
        conf, _note = _CONFIDENCE.get(rv.agreement, ("?", rv.agreement))
        cross = _crosscheck_cell(rv)
        if (rv.metric, rv.scope) not in placed:
            cross = f"{cross} · ⚠ no matching [AUTO] template slot — recorded here only"
        as_of = (rv.as_of or "")[:19]
        lines.append(
            f"| {i} | {rv.metric} | {scope} | {rv.value} | {rv.unit} | "
            f"{rv.source_used} | {as_of} | {conf} ({rv.agreement}) | {cross} |"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# slot filling
# --------------------------------------------------------------------------- #
def _match_slot(line_lower: str) -> Optional[SlotSpec]:
    for spec in SLOTS:
        if spec.matches_line(line_lower):
            return spec
    return None


def _slot_subbullet(rv: ReconciledValue, subject_ref: Optional[SubjectRef]) -> str:
    """One filled sub-bullet under an [AUTO] slot."""
    val = render_value(rv, subject_ref)
    conf, _ = _CONFIDENCE.get(rv.agreement, ("?", ""))
    scope_lbl = _scope_label(rv)
    prefix = f"**{scope_lbl}** — " if scope_lbl else ""
    as_of = (rv.as_of or "")[:10]
    return (f"    - {prefix}{val} · source `{rv.source_used}` · as_of {as_of} "
            f"· confidence **{conf}** ({rv.agreement})")


def _signed_usd(value: float) -> str:
    """Signed USD magnitude — ``+$2.10B`` / ``-$1.30B`` (sign before the $)."""
    scaled, suffix = _magnitude(value)
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(scaled):,.2f}{suffix}"


def _net_change_subbullet(rv: ReconciledValue) -> str:
    """One filled sub-bullet for a computed net-supply-change window (B.2.9).

    Renders abs + pct + the ACTUAL day-gap (honest about a "7d" computed over 6.4
    real days), e.g.::

        - **30d**: +$2.10B (+2.83%) · up · over 30d (actual 30.0d, 2026-04-28→2026-05-28) …
    """
    audit = rv.audit if isinstance(rv.audit, Mapping) else {}
    conf, _ = _CONFIDENCE.get(rv.agreement, ("?", ""))
    window = audit.get("window_days")
    abs_change = audit.get("abs_change")
    actual_days = audit.get("actual_days")
    direction = audit.get("direction", "")
    then_date = audit.get("then_date", "")
    now_date = audit.get("now_date", "")
    abs_part = _signed_usd(float(abs_change)) if isinstance(abs_change, (int, float)) else "—"
    actual = f"{actual_days:.1f}d" if isinstance(actual_days, (int, float)) else "?"
    return (
        f"    - **{window}d**: {abs_part} ({float(rv.value):+.2f}%) · {direction} · "
        f"over {window}d (actual {actual}, {then_date}→{now_date}) · source "
        f"`{rv.source_used}` · confidence **{conf}** ({rv.agreement})"
    )


def _window_sort_key(rv: ReconciledValue) -> int:
    """Sort computed windows ascending (7d before 30d before 90d)."""
    audit = rv.audit if isinstance(rv.audit, Mapping) else {}
    days = audit.get("window_days")
    return days if isinstance(days, int) else 9999


def _fill_semi_auto_line(
    line: str,
    marker_text: str,
    body: str,
    by_key: "Dict[Tuple[str, Optional[str]], ReconciledValue]",
    placed: "set[Tuple[str, Optional[str]]]",
) -> List[str]:
    """A [SEMI-AUTO] slot: FILL it when it is a designed computed slot WITH a matching
    value (B.2.9), otherwise flag it for a human exactly as before.

    Only a slot flagged ``computed`` can be auto-filled here — a plain [SEMI-AUTO]
    line (DEX pool liquidity, attestation cadence, …) always stays flagged, never
    fabricated from an unrelated [AUTO] metric.
    """
    spec = _match_slot(line.lower())
    if spec is None or not spec.computed:
        return [_semi_flag(line, body)]

    facts = [rv for key, rv in by_key.items()
             if key not in placed and spec.accepts(rv)]
    if not facts:
        # designed-fillable, but nothing was computed this run -> flag as before.
        return [_semi_flag(line, body)]
    facts.sort(key=_window_sort_key)

    for rv in facts:
        placed.add((rv.metric, rv.scope))
    filled_marker = f"[SEMI-AUTO ✓ COMPUTED: {body}]"
    out = [line.replace(marker_text, filled_marker)]
    out.extend(_net_change_subbullet(rv) for rv in facts)
    return out


def _semi_flag(line: str, body: str) -> str:
    return (f"{line}  → ⚠ **NEEDS HUMAN REVIEW [SEMI-AUTO]** — compute / verify "
            f"manually before publish: {body}")


def _fill_auto_line(
    line: str,
    marker_text: str,
    body: str,
    by_key: "Dict[Tuple[str, Optional[str]], ReconciledValue]",
    placed: "set[Tuple[str, Optional[str]]]",
    subject_ref: Optional[SubjectRef],
) -> List[str]:
    """Resolve a single [AUTO] marker line to filled sub-bullets or a flag."""
    spec = _match_slot(line.lower())
    facts: List[ReconciledValue] = []
    if spec is not None:
        facts = [rv for key, rv in by_key.items()
                 if key not in placed and spec.accepts(rv)]
        facts.sort(key=lambda rv: (_SCOPE_SORT.get(rv.scope, 9), rv.metric))

    if not facts:
        # No reconciled value for this slot -> leave the marker, flag it.
        return [f"{line}  → ⚠ **UNFILLED [AUTO]** — no reconciled value for this "
                f"slot (left flagged, NOT fabricated)"]

    for rv in facts:
        placed.add((rv.metric, rv.scope))
    filled_marker = f"[AUTO ✓ FILLED: {body}]"
    out = [line.replace(marker_text, filled_marker)]
    out.extend(_slot_subbullet(rv, subject_ref) for rv in facts)
    return out


def _process_line(
    line: str,
    by_key: "Dict[Tuple[str, Optional[str]], ReconciledValue]",
    placed: "set[Tuple[str, Optional[str]]]",
    subject_ref: Optional[SubjectRef],
) -> List[str]:
    """Transform one template line: fill an [AUTO] slot, or flag SEMI/MANUAL."""
    m = _MARKER_RE.search(line)
    if m is None:
        return [line]
    kind, body = m.group(1), m.group(2).strip()
    # A legend/format definition (body still holds a ``<placeholder>``) is not a
    # real slot — leave it untouched.
    if "<" in body:
        return [line]

    if kind == "AUTO":
        return _fill_auto_line(line, m.group(0), body, by_key, placed, subject_ref)
    if kind == "SEMI-AUTO":
        return _fill_semi_auto_line(line, m.group(0), body, by_key, placed)
    # MANUAL
    return [f"{line}  → ⚠ **MANUAL** — researcher must fill: {body}"]


# --------------------------------------------------------------------------- #
# header context (from SubjectRef)
# --------------------------------------------------------------------------- #
def _subject_ref_block(subject_ref: SubjectRef) -> str:
    ids = " · ".join(
        f"{k}=`{v}`" for k, v in sorted(subject_ref.identifiers.items())
    )
    return (
        "> **[AUTO subject_ref]** "
        f"subject **{subject_ref.subject}** · subject_type {subject_ref.subject_type} "
        f"· issuer {subject_ref.issuer or '—'} · decimals {subject_ref.decimals} "
        f"· ids: {ids}"
    )


def _latest_as_of(reconciled: List[ReconciledValue]) -> Optional[str]:
    stamps = [rv.as_of for rv in reconciled if isinstance(rv.as_of, str) and rv.as_of]
    return max(stamps)[:10] if stamps else None


def _apply_header_context(
    line: str, subject_ref: SubjectRef, data_date: Optional[str]
) -> str:
    """Fill the few clearly-labelled Part 0 identity slots from SubjectRef.

    Identity bindings (title / subject type / data date) are deterministic facts,
    not measured numbers — filling them is not a fabrication. Only an EMPTY slot
    is filled; a human-edited value is never overwritten.
    """
    stripped = line.strip()
    if stripped == "- **Title**:":
        issuer = f" ({subject_ref.issuer})" if subject_ref.issuer else ""
        return f"- **Title**: {subject_ref.subject}{issuer} — automated data snapshot `[AUTO subject_ref]`"
    if stripped == "- **Date**:" and data_date:
        return f"- **Date**: {data_date} (data as_of) `[AUTO — latest reconciled as_of]`"
    if subject_ref.subject_type in {"stablecoin", "asset", "token"} and "☐ Asset/Token" in line:
        return line.replace("☐ Asset/Token", "☑ Asset/Token")
    return line


# --------------------------------------------------------------------------- #
# module-aware section selection (B.2.8b)
# --------------------------------------------------------------------------- #
# The v1.4 template is ONE unified SOP spanning every subject type. TWO
# INDEPENDENT tag axes live in the section headers (inside `[...]` / `（...）`):
#
#   SUBJECT-TYPE axis — only on the type-specific modules: Part 5.1 [Chain / L2 /
#     DeFi], 5.2 [Chain / L2], 5.3 [Payment chain], 5.4 [DeFi], 5.5 [Stablecoin],
#     Part 4.3 [Crypto-native asset / token-bearing protocol], and Part 8's
#     valuation paths (Path A crypto-native, Path B "no token exists" infra,
#     Path C stablecoin). A section carrying a subject-type tag is KEPT only when
#     the run's ``subject_type`` is among the types it names — a section may name
#     SEVERAL (the stackable/hybrid case, e.g. [Chain / L2 / DeFi]).
#
#   MODE axis — [Both] / [Mode A …] / [Mode B …]. ★ [Both] here means both MODES
#     (A subject-driven, B news-driven), NOT both subject types: a [Both] (or
#     untagged) section is subject-type-AGNOSTIC and is always kept, subject only
#     to the mode filter.
#
# ``subject_type`` values match ``SubjectRef.subject_type``. Subject tokens are
# matched LONGEST-FIRST and consumed, so "payment chain" never also counts as the
# generic "chain"; and detection is restricted to the `[...]`/`（...）` tag groups
# so a plain title word ("On-Chain Metrics", "Stablecoin valuation") cannot
# trip a match.
_TYPE_TOKENS: Tuple[Tuple[str, "frozenset[str]"], ...] = (
    ("token-bearing protocol", frozenset({"defi_protocol", "crypto_native_asset"})),
    ("crypto-native asset",     frozenset({"crypto_native_asset"})),
    ("payment chain",           frozenset({"payment_chain"})),
    ("defi protocol",           frozenset({"defi_protocol"})),
    ("stablecoin",              frozenset({"stablecoin"})),
    ("rollup",                  frozenset({"l2"})),
    ("payment",                 frozenset({"payment_chain"})),
    ("defi",                    frozenset({"defi_protocol"})),
    ("chain",                   frozenset({"chain", "l1"})),
    ("l2",                      frozenset({"l2"})),
)

# Every subject_type the selector knows how to place. An unknown/unmapped type
# (or ``None``) trips the FAIL-SAFE — keep everything — rather than silently
# dropping a section it cannot reason about.
_KNOWN_SUBJECT_TYPES: "frozenset[str]" = frozenset(
    t for _tok, types in _TYPE_TOKENS for t in types
)

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# A header's delimited tag groups: `[...]` (ASCII) and `（...）` (full-width). The
# CJK 【...】 brackets are deliberately NOT matched (they carry prose, not tags).
_TAG_GROUP_RE = re.compile(r"\[([^\]]*)\]|（([^）]*)）")


def _subject_types_in_tag(tag_text: str) -> "frozenset[str]":
    """The subject types a tag string names (possibly several — the stackable
    hybrid case). Empty when the tag carries no subject-type token."""
    text = tag_text.lower()
    matched: "set[str]" = set()
    for token, types in _TYPE_TOKENS:
        if token in text:
            matched |= types
            text = text.replace(token, " ")   # consume so "chain" ⊄ "payment chain"
    return frozenset(matched)


def _header_subject_types(header: str) -> "frozenset[str]":
    """Subject types named in a header's delimited tags, plus the valuation-path
    "no token exists" branch (Part 8 Path B → no-token infra). Empty ⇒ the header
    is subject-type-agnostic (kept regardless of subject_type)."""
    matched: "set[str]" = set()
    for m in _TAG_GROUP_RE.finditer(header):
        matched |= _subject_types_in_tag(m.group(1) or m.group(2) or "")
    if "no token" in header.lower():          # Part 8 Path B — infra w/o a token
        matched |= {"payment_chain"}
    return frozenset(matched)


def _header_mode_excluded(header: str, mode: str) -> bool:
    """True when a header's MODE tag excludes it from the active ``mode``.

    Mode A == ``"subject_driven"``, Mode B == ``"news_driven"``. A [Both] / dual
    (names both modes) / untagged header is never excluded — only a single-mode
    EXCLUSIVE one is (e.g. Part 2 News Hook is [Mode B only] → dropped in Mode A).
    """
    low = header.lower()
    has_a, has_b = "mode a" in low, "mode b" in low
    if "both" in low or (has_a and has_b) or (not has_a and not has_b):
        return False
    if mode == "subject_driven":              # Mode A — drop Mode-B-only sections
        return has_b and not has_a
    return has_a and not has_b                # Mode B — drop Mode-A-only sections


def select_sections(
    template_text: str,
    subject_type: Optional[str],
    mode: str = "subject_driven",
) -> "Tuple[str, Dict[str, object]]":
    """Module-aware section selection (B.2.8b) — turn the unified v1.4 SOP into a
    clean per-subject report. PURE and deterministic.

    Splits the template into header-delimited sections (a section spans its header
    down to the next header of the SAME-OR-HIGHER level — so omitting a Part drops
    its sub-sections too) and KEEPS only those that apply:
      * a section carrying a SUBJECT-TYPE tag is kept only when ``subject_type`` is
        among the types it names;
      * a subject-type-AGNOSTIC section ([Both] / untagged) is kept, subject only
        to the MODE filter.
    Omitted sections vanish ENTIRELY (header AND body) — they are NOT flagged-empty.

    FAIL-SAFE: an unknown/unmapped ``subject_type`` (or ``None``) keeps EVERYTHING
    and records a note — never a silent drop.

    Returns ``(kept_text, info)`` with ``info`` = ``{kept, omitted, failsafe}``
    (``kept``/``omitted`` are header strings; ``failsafe`` is a note or ``None``).
    """
    if subject_type not in _KNOWN_SUBJECT_TYPES:
        note = (f"subject_type {subject_type!r} is not a mapped module type — "
                f"ALL sections kept (module-aware selection skipped; nothing dropped)")
        return template_text, {"kept": [], "omitted": [], "failsafe": note}

    out: List[str] = []
    kept: List[str] = []
    omitted: List[str] = []
    skip_level: Optional[int] = None          # currently dropping a section at this level

    for line in template_text.split("\n"):
        m = _HEADER_RE.match(line)
        level = len(m.group(1)) if m else None

        if skip_level is not None:
            if level is not None and level <= skip_level:
                skip_level = None             # this header re-enters normal evaluation
            else:
                continue                      # still inside the dropped section

        if m is not None:
            types = _header_subject_types(line)
            omit = (bool(types) and subject_type not in types) \
                or _header_mode_excluded(line, mode)
            if omit:
                skip_level = level
                omitted.append(line.strip())
                continue
            kept.append(line.strip())

        out.append(line)

    return "\n".join(out), {"kept": kept, "omitted": omitted, "failsafe": None}


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def fill(
    template_text: str,
    reconciled: List[ReconciledValue],
    subject_ref: Optional[SubjectRef] = None,
    mode: str = "subject_driven",
) -> str:
    """Fill a research-template string from reconciled values. PURE — no I/O.

    When a ``subject_ref`` is supplied, a MODULE-AWARE section-selection pass
    (B.2.8b — ``select_sections``) runs FIRST, keyed on ``subject_ref.subject_type``
    and ``mode`` (``"subject_driven"`` = Mode A, ``"news_driven"`` = Mode B): only
    the template sections that apply to the subject + mode survive; the rest are
    omitted entirely (gone, NOT flagged-empty). The existing ``[AUTO]`` slot-filling
    then runs on the KEPT sections only.

    Returns the filled markdown:
      * each ``[AUTO]`` slot it can map (by keyword -> metric/scope) gets the
        reconciled value(s) as sub-bullets; the two supply scopes render as
        DISTINCT sub-bullets, never merged;
      * an ``[AUTO]`` slot with no matching value stays flagged;
      * every ``[SEMI-AUTO]`` / ``[MANUAL]`` slot stays flagged for a human;
      * a ``subject_ref`` context block + Part 0 identity slots are filled from
        ``subject_ref`` (when provided);
      * a data-layer Evidence Table (one row per reconciled fact, full precision)
        is appended — including any reconciled value that found no slot.

    See the module docstring for the faithfulness and scope/unit rules, and
    ``select_sections`` for the section-selection axes and fail-safe.
    """
    rvs = [rv for rv in reconciled if isinstance(rv, ReconciledValue)]
    by_key: "Dict[Tuple[str, Optional[str]], ReconciledValue]" = {}
    for rv in rvs:
        by_key.setdefault((rv.metric, rv.scope), rv)

    placed: "set[Tuple[str, Optional[str]]]" = set()
    data_date = _latest_as_of(rvs)

    # MODULE-AWARE pass first: keep only the sections that apply to this subject +
    # mode, so the [AUTO] slot-filling below runs on the kept sections only.
    selection_note: Optional[str] = None
    if subject_ref is not None:
        template_text, info = select_sections(template_text, subject_ref.subject_type, mode)
        selection_note = info["failsafe"]      # type: ignore[assignment]

    out: List[str] = []
    for line in template_text.split("\n"):
        if subject_ref is not None:
            line = _apply_header_context(line, subject_ref, data_date)
        out.extend(_process_line(line, by_key, placed, subject_ref))
        # inject the subject_ref context block + module-aware note after Part 0
        if subject_ref is not None and line.startswith("## Part 0"):
            out.append("")
            out.append(_subject_ref_block(subject_ref))
            out.append("")
            if selection_note:
                out.append(f"> **[AUTO module-aware]** ⚠ {selection_note}")
            else:
                out.append(
                    f"> **[AUTO module-aware]** rendered for subject_type "
                    f"`{subject_ref.subject_type}` · mode `{mode}` — template sections "
                    f"that do not apply to this subject/mode are omitted (not flagged)."
                )

    out.append(build_evidence_table(rvs, placed))
    return "\n".join(out)


def fill_template_file(
    template_path: str,
    output_path: str,
    reconciled: List[ReconciledValue],
    subject_ref: Optional[SubjectRef] = None,
) -> str:
    """Thin I/O wrapper: read the template, ``fill`` it, write the markdown.

    Returns the filled markdown (also written to ``output_path``). The pure
    ``fill`` does all the work; this only touches the filesystem.
    """
    from pathlib import Path

    text = Path(template_path).read_text(encoding="utf-8")
    result = fill(text, reconciled, subject_ref)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result, encoding="utf-8")
    return result
