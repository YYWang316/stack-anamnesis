"""The reconciliation / credibility layer (B.2.7) — third stage in the
analysis-layer trunk (extractor -> resolver -> aggregator -> filler).

Several sources report the same fact and the numbers don't perfectly match.
``reconcile`` turns a pile of ``ExtractedValue``s into a list of trustworthy
single values, each carrying a confidence signal.

THE CARDINAL RULE: it does NOT blend or average. The reported ``value`` is
ALWAYS a real source's actual number — the authority's (via the
``source_authority`` resolver), with fallback down the cross-check order when
the primary emitted nothing. Cross-source agreement is recorded as a confidence
signal (``agreement`` + ``audit``), never used to synthesize a number. On
divergence the value still stays the authority's number — flagged, not dropped.

Four steps (see ``reconcile``):
  1. GROUP by (metric, scope). Never reconcile across scopes — single-chain
     supply (~$52.6B Ethereum-only) and multi-chain aggregate supply (~$76.4B)
     are DIFFERENT facts -> two separate ReconciledValues.
  2. PICK the authority's actual value (fallback down the cross-check order).
  3. CROSS-CHECK every other available source against the chosen value, vs a
     scope-aware tolerance band — widened by the ``as_of`` gap for single-chain
     on-chain reads (drift rule below).
  4. Label agreement: agree / divergence / single_source.

Pure: no I/O, no network. Takes already-extracted ``ExtractedValue``s; it does
NOT import the extractors. OUT OF SCOPE: markdown rendering (B.2.8), web
third-source / red-team checks (B.3), and any averaging of values.
"""
from __future__ import annotations

import statistics
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

from analysis_layer.contract import ExtractedValue, ReconciledValue
from analysis_layer.resolvers.source_authority import authority_for

# --------------------------------------------------------------------------- #
# tolerance bands (relative fractions; 0.005 == 0.5%) — derived from
# analysis_layer/README.md "Reconciliation rules".
# --------------------------------------------------------------------------- #
BAND_GENERAL_CURRENCY = 0.005   # MEMORY.md hard rule: currency amounts ±0.5%
BAND_MULTI_CHAIN_SUPPLY = 0.002  # multi-chain aggregator supply total ~0.2%
BAND_SINGLE_CHAIN_SUPPLY = 0.0005  # single-chain same-contract, CONTEMPORANEOUS only (~0.05%)

# Supply metrics get the tighter scope-specific bands; everything else
# (price / market_cap / volume_24h) is a general currency amount at ±0.5%.
_SUPPLY_METRICS = frozenset({"total_supply", "circulating_supply"})

# Two single-chain reads are "contemporaneous" only if their as_of are within
# this window; beyond it the tight band is widened for mint/burn drift.
CONTEMPORANEOUS_WINDOW_SEC = 3600  # 1 hour

# ★ DRIFT_RATE — expected single-chain supply drift from normal mint/burn, per
# day, as a relative fraction. DERIVATION: the two real on-chain USDC envelopes
# are ~1.86 days apart and differ ~0.26% (52.571B vs 52.708B) => ~0.14%/day. Set
# slightly above that (0.15%/day) so genuine drift over the real gap reads as
# "agree", never a false divergence. Tunable: raise if real reads false-flag.
DRIFT_RATE_PER_DAY = 0.0015

# agreement labels
AGREE = "agree"
DIVERGENCE = "divergence"
SINGLE_SOURCE = "single_source"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _parse_as_of(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 ``as_of`` to a tz-aware UTC datetime, or None.

    Handles the ``Z`` suffix (CMC/CoinGecko) which 3.9's ``fromisoformat`` can't,
    and the ``+00:00`` offsets (Alchemy/Etherscan/DefiLlama). Naive datetimes are
    assumed UTC. Anything unparseable returns None (never throws — rule 1).
    """
    if not isinstance(value, str) or not value.strip():
        return None
    txt = value.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _rel_delta(a: float, b: float) -> float:
    """Relative difference of ``a`` vs reference ``b`` (|a-b|/|b|).

    Both zero -> 0.0; reference zero but a nonzero -> +inf (always out of band).
    """
    if b == 0:
        return 0.0 if a == 0 else float("inf")
    return abs(a - b) / abs(b)


def _scope_of(value: ExtractedValue) -> Optional[str]:
    """The reconciliation scope a value belongs to.

    Primary source: the extractor's own ``provenance["scope"]`` tag. FALLBACK:
    the Alchemy ``total_supply`` extractor currently emits NO scope tag (see
    alchemy.py provenance), so when the tag is absent we infer the scope from
    ``source_authority`` — the scope whose authority ranking names this source
    for this metric. This avoids a hardcoded source->scope map and stays correct
    if Alchemy later adds the tag (its tag would then simply win here).
    """
    prov = value.provenance if isinstance(value.provenance, Mapping) else {}
    scope = prov.get("scope")
    if isinstance(scope, str) and scope:
        return scope
    for candidate in ("single-chain", "multi_chain"):
        auth = authority_for(value.metric, candidate)
        if auth is not None and (
            value.source == auth.primary or value.source in auth.cross_checks
        ):
            return candidate
    return None


def _band_for_crosscheck(
    metric: str,
    scope: Optional[str],
    chosen: ExtractedValue,
    other: ExtractedValue,
) -> Dict[str, Any]:
    """The tolerance band to judge ``other`` against ``chosen``, scope-aware.

    Returns a dict with the band applied plus the ``as_of``-gap context. Non-
    supply metrics use the ±0.5% general currency band regardless of the
    (multi_chain) scope tag the price/market_cap extractors happen to carry —
    the tighter 0.2% band is for SUPPLY TOTALS, not prices.
    """
    if metric not in _SUPPLY_METRICS:
        return {"band": BAND_GENERAL_CURRENCY, "base_band": BAND_GENERAL_CURRENCY,
                "contemporaneous": None, "gap_hours": None, "gap_days": None,
                "note": "general currency band ±0.5%"}

    if scope == "multi_chain":
        return {"band": BAND_MULTI_CHAIN_SUPPLY, "base_band": BAND_MULTI_CHAIN_SUPPLY,
                "contemporaneous": None, "gap_hours": None, "gap_days": None,
                "note": "multi-chain aggregate supply band ~0.2%"}

    if scope == "single-chain":
        t0 = _parse_as_of(chosen.as_of)
        t1 = _parse_as_of(other.as_of)
        if t0 is None or t1 is None:
            # Can't confirm contemporaneity -> fall back to the safe ±0.5% band.
            return {"band": BAND_GENERAL_CURRENCY, "base_band": BAND_SINGLE_CHAIN_SUPPLY,
                    "contemporaneous": False, "gap_hours": None, "gap_days": None,
                    "note": "single-chain as_of unparseable: conservative ±0.5% band"}
        gap_sec = abs((t1 - t0).total_seconds())
        gap_days = gap_sec / 86400.0
        gap_hours = gap_sec / 3600.0
        if gap_sec <= CONTEMPORANEOUS_WINDOW_SEC:
            return {"band": BAND_SINGLE_CHAIN_SUPPLY, "base_band": BAND_SINGLE_CHAIN_SUPPLY,
                    "contemporaneous": True, "gap_hours": gap_hours, "gap_days": gap_days,
                    "note": "single-chain contemporaneous (gap <= 1h): tight band ~0.05%"}
        # ★ widen the tight band by expected mint/burn drift over the gap.
        widened = BAND_SINGLE_CHAIN_SUPPLY + gap_days * DRIFT_RATE_PER_DAY
        return {"band": widened, "base_band": BAND_SINGLE_CHAIN_SUPPLY,
                "contemporaneous": False, "gap_hours": gap_hours, "gap_days": gap_days,
                "note": (f"single-chain non-contemporaneous (gap {gap_days:.2f}d): tight band "
                         f"widened by drift {DRIFT_RATE_PER_DAY:.4%}/day to {widened:.4%}")}

    # supply with no/unknown scope -> safe general band.
    return {"band": BAND_GENERAL_CURRENCY, "base_band": BAND_GENERAL_CURRENCY,
            "contemporaneous": None, "gap_hours": None, "gap_days": None,
            "note": "supply with unknown scope: conservative ±0.5% band"}


def _ordered_sources(
    available: List[str], auth, chosen_source: str
) -> List[str]:
    """Cross-check sources in authority order (primary first), chosen excluded,
    then any remaining available sources appended alphabetically."""
    ordered: List[str] = []
    if auth is not None:
        for s in (auth.primary,) + tuple(auth.cross_checks):
            if s in available and s != chosen_source and s not in ordered:
                ordered.append(s)
    for s in sorted(available):
        if s != chosen_source and s not in ordered:
            ordered.append(s)
    return ordered


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def reconcile(values: List[ExtractedValue]) -> List[ReconciledValue]:
    """Reconcile same-fact ``ExtractedValue``s into authoritative
    ``ReconciledValue``s — one per (metric, scope) group. Pure; never throws.

    See the module docstring for the four steps and the cardinal
    authority-not-average rule.
    """
    # Step 1 — GROUP by (metric, scope). Insertion-ordered for determinism is
    # not enough (input order varies), so we sort the groups at emit time.
    groups: "OrderedDict[Tuple[str, Optional[str]], List[ExtractedValue]]" = OrderedDict()
    for v in values:
        if not isinstance(v, ExtractedValue):
            continue
        key = (v.metric, _scope_of(v))
        groups.setdefault(key, []).append(v)

    out: List[ReconciledValue] = []
    for (metric, scope) in sorted(groups, key=lambda k: (k[0], k[1] or "")):
        group = groups[(metric, scope)]

        # one value per source (first wins; same source rarely repeats a scalar).
        by_source: "OrderedDict[str, ExtractedValue]" = OrderedDict()
        for v in group:
            by_source.setdefault(v.source, v)
        available = list(by_source)

        auth = authority_for(metric, scope)

        # Step 2 — PICK the authority's actual value (fallback down the order).
        chosen_source = None
        if auth is not None:
            for s in (auth.primary,) + tuple(auth.cross_checks):
                if s in by_source:
                    chosen_source = s
                    break
        if chosen_source is None:
            # no authority, or none of the ranked sources present -> deterministic.
            chosen_source = sorted(available)[0]
        chosen = by_source[chosen_source]
        fallback = auth is not None and chosen_source != auth.primary

        # Step 3 — CROSS-CHECK each other available source (best-effort).
        cross_records: List[Dict[str, Any]] = []
        all_within = True
        for s in _ordered_sources(available, auth, chosen_source):
            other = by_source[s]
            band_info = _band_for_crosscheck(metric, scope, chosen, other)
            delta = _rel_delta(float(other.value), float(chosen.value))
            within = delta <= band_info["band"]
            all_within = all_within and within
            cross_records.append({
                "source": s,
                "value": other.value,
                "as_of": other.as_of,
                "delta": delta,
                "band": band_info["band"],
                "base_band": band_info["base_band"],
                "within_band": within,
                "contemporaneous": band_info["contemporaneous"],
                "gap_hours": band_info["gap_hours"],
                "gap_days": band_info["gap_days"],
                "note": band_info["note"],
            })

        # Step 4 — agreement label.
        if not cross_records:
            agreement = SINGLE_SOURCE
        elif all_within:
            agreement = AGREE
        else:
            agreement = DIVERGENCE

        # confidence signal: spread + median across available values (RECORDED,
        # never used as the value).
        nums = [float(by_source[s].value) for s in available]
        median = statistics.median(nums)
        spread = (max(nums) - min(nums)) / abs(median) if median else (
            0.0 if max(nums) == min(nums) else float("inf"))

        audit = {
            "primary": auth.primary if auth is not None else None,
            "authority_order": ([auth.primary] + list(auth.cross_checks))
            if auth is not None else None,
            "fallback": fallback,
            "n_sources": len(available),
            "available_sources": available,
            "cross_checks": cross_records,
            "spread": spread,      # (max-min)/median, relative fraction
            "median": median,
        }

        out.append(ReconciledValue(
            metric=metric,
            value=chosen.value,
            unit=chosen.unit,
            source_used=chosen_source,
            scope=scope,
            as_of=chosen.as_of,
            agreement=agreement,
            inputs=tuple(group),
            audit=audit,
        ))

    return out
