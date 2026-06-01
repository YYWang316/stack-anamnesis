"""Extractor for DefiLlama stablecoin supply-chart envelopes
(tools/fetchers/defillama_fetch.py, stablecoin path).

Envelope shape (verified against meta/raw/defillama/*.json, TD-023):

    {
      "subject": "USDC",
      "subject_type": "stablecoin",
      "freshness_window": "30d",
      "endpoint": "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=2",
      "fetched_at": "2026-06-01T16:27:13.870016+00:00",
      "raw_response": [                       # <- a LIST, ~2821 daily points
        {"date": "1536624000",
         "totalCirculating":    {"peggedUSD": 2},
         "totalCirculatingUSD": {"peggedUSD": 2}},
        ...
        {"date": "1780272000",
         "totalCirculating":    {"peggedUSD": 75898768744.57},   # nominal SUPPLY
         "totalCirculatingUSD": {"peggedUSD": 75869226873.40}},  # market-value USD
      ]
    }

Unlike the Alchemy / SEC envelopes (a single dict of named reads), the
stablecoin chart is a TIME SERIES. ``extract_stablecoin_supply_series`` returns
ONE ``ExtractedValue`` per daily point — this is the agreed series
representation: it EXTENDS the scalar contract without forking it (each point is
a perfectly normal ``ExtractedValue`` whose ``as_of`` carries the point's day).

All functions here are pure (rule 3): envelope in, typed values out, no I/O.
The series degrades to ``[]`` on an empty/malformed envelope, and individual
malformed points are skipped rather than thrown (rule 1).

----------------------------------------------------------------------------
TD-023 — which field is the SUPPLY, and why ``unit="USD"``
----------------------------------------------------------------------------
A pegged stablecoin point carries two ``peggedUSD`` figures that differ
slightly. Verified on the live USDC envelope's latest point:

    totalCirculating.peggedUSD    = 75,898,768,744.57   (the larger)
    totalCirculatingUSD.peggedUSD = 75,869,226,873.40   (the smaller)
    implied price = 75.869B / 75.899B = 0.99961  (USDC just under its $1 peg)

So ``totalCirculating`` is the NOMINAL CIRCULATING SUPPLY — the token count
valued at the $1 peg — while ``totalCirculatingUSD`` REVALUES that same supply
at the live market price (hence smaller when price < $1). We extract the
SUPPLY (``totalCirculating.peggedUSD``) per the mandate; the market-value
counterpart is preserved in provenance for the audit trail.

``unit="USD"``: DefiLlama denominates a pegged stablecoin's circulating supply
in its peg currency — the ``peggedUSD`` key literally means "denominated in the
USD it is pegged to". The value is therefore the nominal circulating supply in
peg-USD (token count x $1 peg), which is the natural unit for reconciling
against the other multi-chain aggregator totals (CoinGecko / CMC) at the
README's ~0.2% band. We tag the peg denomination, not "tokens", so the
aggregator compares like-for-like without a peg conversion.

``scope="multi_chain"``: the DefiLlama stablecoin total aggregates supply
across every chain the asset lives on — never reconcile it against a
single-chain (e.g. Ethereum-only) figure (README scope rule).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional, Sequence

from analysis_layer.contract import ExtractedValue

SOURCE = "defillama"
METRIC = "circulating_supply"
# DefiLlama reports a pegged stablecoin's circulating supply in its peg
# currency; for USDC that is USD (see module docstring, TD-023).
UNIT = "USD"
# The supply field (nominal, at peg) vs its market-value revaluation. Both are
# nested under a ``peggedUSD`` key.
_SUPPLY_FIELD = "totalCirculating"
_MARKET_VALUE_FIELD = "totalCirculatingUSD"
_PEG_KEY = "peggedUSD"


def _pegged_usd(point: Mapping[str, Any], field: str) -> Optional[float]:
    """Return ``point[field].peggedUSD`` as a float, or None if absent/non-numeric.

    Defensive at each hop: the block can be missing or non-dict, and the
    ``peggedUSD`` value can be null or a string in a malformed point.
    """
    block = point.get(field)
    if not isinstance(block, Mapping):
        return None
    value = block.get(_PEG_KEY)
    # bool is an int subclass — exclude it; a circulating supply is never bool.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_of(point: Mapping[str, Any]) -> Optional[str]:
    """Convert the point's unix-second ``date`` (string or int) to ISO-8601 UTC.

    Daily points land on 00:00:00Z; the full timestamp keeps the day
    unambiguous. Returns None if ``date`` is missing or unparsable.
    """
    raw = point.get("date")
    try:
        ts = int(raw)
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _point_to_value(
    point: Mapping[str, Any], subject: Optional[str], fetched_at: Optional[str]
) -> Optional[ExtractedValue]:
    """One daily point -> one ExtractedValue, or None if it lacks a usable supply.

    Skipping (None) rather than throwing keeps a single bad point from sinking
    the whole series (rule 1).
    """
    if not isinstance(point, Mapping):
        return None
    supply = _pegged_usd(point, _SUPPLY_FIELD)
    if supply is None:
        return None
    as_of = _as_of(point)
    if as_of is None:
        return None

    return ExtractedValue(
        metric=METRIC,
        value=supply,
        unit=UNIT,
        source=SOURCE,
        subject=subject,
        as_of=as_of,
        provenance={
            "scope": "multi_chain",  # cross-chain aggregate (README scope rule)
            "field": f"{_SUPPLY_FIELD}.{_PEG_KEY}",
            "raw_date": point.get("date"),
            # the same supply revalued at live market price; kept for audit /
            # peg-drift cross-check, never used as the supply itself.
            "market_value_usd": _pegged_usd(point, _MARKET_VALUE_FIELD),
            "fetched_at": fetched_at,
        },
    )


def extract_stablecoin_supply_series(
    envelope: Mapping[str, Any],
) -> List[ExtractedValue]:
    """Every daily circulating-supply point as an ordered list of ExtractedValue.

    Returns ``[]`` (not None) when ``raw_response`` is absent, not a list, or
    empty — a series naturally degrades to empty, unlike a scalar which
    degrades to None (rule 1). Malformed individual points are skipped. Order
    follows the envelope (oldest -> newest), so the last element is the most
    recent point (see ``latest``).
    """
    raw = envelope.get("raw_response")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    subject = envelope.get("subject")
    fetched_at = envelope.get("fetched_at")

    out: List[ExtractedValue] = []
    for point in raw:
        ev = _point_to_value(point, subject, fetched_at)
        if ev is not None:
            out.append(ev)
    return out


def latest(envelope: Mapping[str, Any]) -> Optional[ExtractedValue]:
    """The most recent circulating-supply point, or None if the series is empty.

    A thin convenience over ``extract_stablecoin_supply_series`` — the "latest"
    value is simply the last (newest) point in the chronological series.
    """
    series = extract_stablecoin_supply_series(envelope)
    return series[-1] if series else None
