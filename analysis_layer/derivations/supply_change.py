"""Change layer (B.2.9) — supply-momentum derivation (TD-035).

The stablecoin KEY SIGNAL (Part 5.5 "Supply Momentum: organic vs mechanical") reads
the SLOPE of circulating supply, not its absolute level. This module computes that
slope's SUPPLY LEG: net 7d / 30d / 90d change of the DefiLlama historical supply
series the fetcher already pulls.

It is LEG 1 of 3 of the KEY SIGNAL — the holder-count leg and the real-usage leg
come later, so this module does NOT decide the CONFIRMATION / DIVERGENCE verdict; it
only supplies the supply-direction number(s) that verdict will later weigh.

WHY a ``ReconciledValue`` directly (not ExtractedValue -> reconcile)
------------------------------------------------------------------------------
The aggregator's job is cross-source reconciliation — pick the authority's number,
record agreement as a confidence signal. But only ONE source (DefiLlama) carries a
historical supply TIME SERIES; CoinGecko/CMC/on-chain give a single latest snapshot,
not a back-series. So a window change is single-source BY NATURE: there is nothing to
cross-check, no authority contest to resolve. We therefore emit ``ReconciledValue``
directly with ``agreement="single_source"`` rather than fabricating a one-source
"reconciliation". (If a SECOND historical-series source ever appears, route both
through ``reconcile`` instead — see TD-035.)

NON-CONTEMPORANEOUS HONESTY (mirrors the aggregator's drift handling)
------------------------------------------------------------------------------
Daily points rarely land exactly on ``now − window``. We take the point NEAREST to
the target and RECORD the actual day-gap, so a nominal "7d" window computed over 6.4
real days is labelled as such, never silently presented as exactly 7d. A window the
series cannot cover (its oldest point is newer than ``now − window``) is SKIPPED with
a note — never faked.

PURE + deterministic: envelope in (already loaded by the caller), typed values out,
no I/O and no wall-clock — "now" is the series' own latest point.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Mapping, Optional, Tuple

from analysis_layer.contract import ExtractedValue, ReconciledValue, SubjectRef
from analysis_layer.extractors.defillama import extract_stablecoin_supply_series

SOURCE = "defillama"
# Windows (in days) the KEY SIGNAL reads. Each computes independently; one being
# uncoverable never blocks the others.
_DEFAULT_WINDOWS: Tuple[int, ...] = (7, 30, 90)
# Flat dead-band: a move whose magnitude is below this (relative) is "flat", not a
# direction. 5 bps — below it the change is noise against a ~$76B base, not a slope.
_FLAT_BAND = 0.0005
# Single-source-by-nature: no second historical-series source to cross-check against.
_AGREEMENT_NOTE = (
    "single source — DefiLlama is the only historical supply series; "
    "snapshot sources (CoinGecko/CMC/on-chain) carry no back-series to cross-check"
)


def _parse(as_of: Optional[str]) -> Optional[datetime]:
    """Parse an extractor's ISO-8601 ``as_of`` to a tz-aware datetime, or None."""
    if not isinstance(as_of, str) or not as_of:
        return None
    try:
        return datetime.fromisoformat(as_of)
    except ValueError:
        return None


def _scope_of(ev: ExtractedValue) -> Optional[str]:
    """The series' reconciliation scope (DefiLlama stablecoin total = multi_chain)."""
    prov = ev.provenance if isinstance(ev.provenance, Mapping) else {}
    scope = prov.get("scope")
    return scope if isinstance(scope, str) else None


def _direction(pct_change: float, flat_band: float) -> str:
    """Signed direction with a documented flat dead-band (see ``_FLAT_BAND``)."""
    if pct_change > flat_band:
        return "up"
    if pct_change < -flat_band:
        return "down"
    return "flat"


def compute_supply_change(
    defillama_envelope: Mapping[str, Any],
    subject_ref: Optional[SubjectRef] = None,
    windows: Tuple[int, ...] = _DEFAULT_WINDOWS,
    flat_band: float = _FLAT_BAND,
) -> Tuple[List[ReconciledValue], List[str]]:
    """Net supply change over each window the series can cover.

    Returns ``(values, notes)``: one ``ReconciledValue`` per COVERABLE window, plus a
    list of human notes for the windows SKIPPED (insufficient history / unusable
    endpoint). The mandate's nominal ``-> list[ReconciledValue]`` is widened to also
    surface the skip notes — the same non-fabrication honesty the rest of the layer
    keeps: a skipped window must be visible, not silently absent.

    For each window the series covers:
      * ``now`` = the latest series point; ``then`` = the point NEAREST to
        ``now − window`` (exact match not required — the actual day-gap is recorded).
      * net change = now − then (signed); percent = net / then.
      * one ``ReconciledValue``: ``metric="net_supply_change_{w}d"``, ``value`` =
        signed PERCENT POINTS (e.g. ``+2.83`` == +2.83%, comparable across windows),
        ``unit="%"``, ``scope`` = the series' scope, ``source_used="defillama"``,
        ``as_of`` = now's timestamp, ``agreement="single_source"``, ``inputs`` =
        (then, now) endpoints, ``audit`` carrying BOTH abs and pct so the filler can
        render "+$2.1B (+2.8%) over 30d".

    A window whose target predates the series' oldest point — or whose ``then`` value
    is zero (no valid base for a percent) — is SKIPPED with a note, never faked.
    """
    series = extract_stablecoin_supply_series(defillama_envelope)
    notes: List[str] = []

    if len(series) < 2:
        notes.append(
            f"insufficient history — need >= 2 supply points to derive a change; "
            f"got {len(series)}"
        )
        return [], notes

    now_ev = series[-1]
    now_dt = _parse(now_ev.as_of)
    oldest_dt = _parse(series[0].as_of)
    if now_dt is None or oldest_dt is None:
        notes.append("unparsable series timestamps — cannot derive any window")
        return [], notes

    now_value = float(now_ev.value)
    scope = _scope_of(now_ev)
    now_date = now_ev.as_of[:10]

    results: List[ReconciledValue] = []
    for days in windows:
        label = f"{days}d"
        target = now_dt - timedelta(days=days)

        if oldest_dt > target:
            notes.append(
                f"net_supply_change_{label}: insufficient history — series oldest "
                f"point {series[0].as_of[:10]} is newer than the {label} target "
                f"{target.date().isoformat()} (before {now_date}); window SKIPPED, "
                f"not fabricated"
            )
            continue

        # NEAREST point to the target — exact match not required (daily granularity).
        then_ev = min(
            series,
            key=lambda ev: abs((_parse(ev.as_of) or now_dt) - target),
        )
        then_dt = _parse(then_ev.as_of)
        then_value = float(then_ev.value)
        if then_dt is None or then_value == 0:
            notes.append(
                f"net_supply_change_{label}: endpoint unusable (then_value="
                f"{then_value}, then_date={then_ev.as_of}); window SKIPPED"
            )
            continue

        abs_change = now_value - then_value
        pct_change = abs_change / then_value             # signed fraction
        actual_days = (now_dt - then_dt).total_seconds() / 86400.0
        direction = _direction(pct_change, flat_band)

        audit = {
            "then_date": then_ev.as_of[:10],
            "then_value": then_value,
            "now_date": now_date,
            "now_value": now_value,
            "window_days": days,
            "actual_days": actual_days,        # real gap, e.g. 6.4 for a "7d" window
            "abs_change": abs_change,          # signed, USD-peg (series unit)
            "pct_change": pct_change,          # signed fraction (net / then)
            "direction": direction,
            "flat_band": flat_band,
            "source": SOURCE,
            "agreement_note": _AGREEMENT_NOTE,
        }

        results.append(
            ReconciledValue(
                metric=f"net_supply_change_{label}",
                value=pct_change * 100.0,        # signed PERCENT POINTS
                unit="%",
                source_used=SOURCE,
                scope=scope,
                as_of=now_ev.as_of,
                agreement="single_source",
                inputs=(then_ev, now_ev),
                audit=audit,
            )
        )

    return results, notes
