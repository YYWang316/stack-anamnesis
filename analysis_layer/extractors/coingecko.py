"""Extractor for CoinGecko envelopes (tools/fetchers/coingecko_fetch.py).

Envelope shape (verified against meta/raw/coingecko/*.json, TD-023):

    {
      "subject": "USDC",
      "subject_type": "stablecoin",
      "freshness_window": "30d",
      "endpoint": "https://api.coingecko.com/api/v3/coins/usd-coin",
      "fetched_at": "2026-05-27T15:23:04.309098+00:00",
      "raw_response": {
        "search":  {... /search relevance hit used to resolve the coin id ...},
        "spot": {                         # /coins/<id>
          "market_cap_rank": 6,
          "last_updated": "2026-05-27T15:21:58.765Z",
          "market_data": {
            "current_price": {"usd": 0.999729, ...},
            "market_cap":    {"usd": 76386528510, ...},
            "total_volume":  {"usd": 18029185308, ...},
            "total_supply": 76378239615.98817,
            "circulating_supply": 76393215522.45195,
            "market_cap_rank": 6,
            "last_updated": "2026-05-27T15:21:58.765Z"
          }
        },
        "history": {                      # /coins/<id>/market_chart
          "prices":        [[ts_ms, price], ...],   # 721 points for a 30d window
          "market_caps":   [[ts_ms, mcap],  ...],
          "total_volumes": [[ts_ms, vol],   ...]
        }
      }
    }

All functions here are pure (rule 3): envelope in, typed value out, no I/O.
Every hop is null-guarded (rule 1): a missing market_data / nested field
returns None (scalars) or [] (series), never throws.

----------------------------------------------------------------------------
TD-023 notes
----------------------------------------------------------------------------
* SCOPE — CoinGecko is a multi-chain aggregator: its market_cap / total_supply
  are the *cross-chain* total (~$76.4B USDC), NOT the Ethereum-only on-chain
  read (~$52.6B from Alchemy/Etherscan). We tag ``provenance["scope"] =
  "multi_chain"`` so the aggregator's scope rule (README) never reconciles this
  against a single-chain supply — they are different metrics.

* SELF-INCONSISTENCY — in the real USDC envelope CoinGecko reports
  ``circulating_supply`` (76.393B) > ``total_supply`` (76.378B), which is
  nonsensical (circulating can never exceed total). We extract FAITHFULLY and
  do NOT correct it; surfacing the oddity is the aggregator/report's job.

* SERIES — ``extract_history_series`` returns ONE ``ExtractedValue`` per data
  point, the agreed series representation: each point is a normal
  ``ExtractedValue`` (so the series extends the scalar contract without forking
  it), differing only in ``as_of`` (that point's timestamp) and ``value``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional

from analysis_layer.contract import ExtractedValue

SOURCE = "coingecko"

# CoinGecko aggregates many chains; tag every value so the aggregator's scope
# rule keeps it apart from single-chain on-chain reads (see module docstring).
_SCOPE = "multi_chain"


# --------------------------------------------------------------------------- #
# envelope navigation helpers (each hop null-guarded — rule 1)
# --------------------------------------------------------------------------- #
def _spot(envelope: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return ``raw_response.spot`` or None if any hop is missing/malformed."""
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return None
    spot = raw.get("spot")
    return spot if isinstance(spot, Mapping) else None


def _market_data(envelope: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return ``raw_response.spot.market_data`` or None if absent/malformed."""
    spot = _spot(envelope)
    if spot is None:
        return None
    md = spot.get("market_data")
    return md if isinstance(md, Mapping) else None


def _usd(md: Mapping[str, Any], key: str) -> Optional[float]:
    """Return ``md[key]["usd"]`` as a float, or None if any hop is missing.

    CoinGecko nests currency metrics one level deep under the vs-currency
    (``current_price``/``market_cap``/``total_volume`` -> ``{"usd": ...}``).
    """
    block = md.get(key)
    if not isinstance(block, Mapping):
        return None
    val = block.get("usd")
    return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None


def _number(md: Mapping[str, Any], key: str) -> Optional[float]:
    """Return ``md[key]`` as a float when it is a real number, else None."""
    val = md.get(key)
    return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None


def _as_of(envelope: Mapping[str, Any], md: Mapping[str, Any]) -> Optional[str]:
    """Timestamp the spot values reflect: ``market_data.last_updated`` if
    present, else the envelope's ``fetched_at`` (the read time)."""
    last = md.get("last_updated")
    if isinstance(last, str) and last:
        return last
    fetched = envelope.get("fetched_at")
    return fetched if isinstance(fetched, str) else None


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def extract_spot_metrics(envelope: Mapping[str, Any]) -> List[ExtractedValue]:
    """Extract the spot scalars CoinGecko reports for the subject.

    Returns a list of ``ExtractedValue`` — one per metric that is actually
    present in the envelope (price, market_cap, total_supply, volume_24h,
    market_cap_rank). A missing metric is simply omitted (rule 1: never throw);
    if ``market_data`` is absent entirely the list is empty.

    All values carry ``provenance["scope"] = "multi_chain"`` and an ``as_of``
    of ``market_data.last_updated`` (fallback: envelope ``fetched_at``). See the
    module docstring for the scope rationale and the circulating>total oddity,
    which is extracted faithfully and NOT corrected.
    """
    md = _market_data(envelope)
    if md is None:
        return []

    subject = envelope.get("subject")
    as_of = _as_of(envelope, md)

    # (metric, unit, value) — each value is None when its sub-field is absent.
    candidates = [
        ("price", "USD", _usd(md, "current_price")),
        ("market_cap", "USD", _usd(md, "market_cap")),
        ("total_supply", "tokens", _number(md, "total_supply")),
        ("volume_24h", "USD", _usd(md, "total_volume")),
        ("market_cap_rank", "count", _rank(envelope, md)),
    ]

    out: List[ExtractedValue] = []
    for metric, unit, value in candidates:
        if value is None:
            continue
        # rank is an ordinal count -> int; the rest are float amounts.
        typed = int(value) if metric == "market_cap_rank" else value
        out.append(
            ExtractedValue(
                metric=metric,
                value=typed,
                unit=unit,
                source=SOURCE,
                subject=subject,
                as_of=as_of,
                provenance={
                    "scope": _SCOPE,
                    "endpoint": envelope.get("endpoint"),
                    "fetched_at": envelope.get("fetched_at"),
                    "vs_currency": "usd" if unit == "USD" else None,
                    # Faithful echo of the (self-inconsistent) supply pair so a
                    # human/audit layer can see circulating>total without us
                    # silently correcting it (see module docstring).
                    "circulating_supply": md.get("circulating_supply"),
                    "total_supply": md.get("total_supply"),
                },
            )
        )
    return out


def _rank(
    envelope: Mapping[str, Any], md: Mapping[str, Any]
) -> Optional[float]:
    """market_cap_rank — prefer the ``market_data`` copy, fall back to the
    top-level ``spot`` copy (CoinGecko carries it in both). None if neither
    is a real number."""
    rank = _number(md, "market_cap_rank")
    if rank is not None:
        return rank
    spot = _spot(envelope)
    if spot is None:
        return None
    val = spot.get("market_cap_rank")
    return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None


def _ms_to_iso(ts_ms: Any) -> Optional[str]:
    """Epoch-milliseconds -> ISO-8601 UTC string, or None if not a number.

    CoinGecko's market_chart timestamps are epoch milliseconds; the series
    contract carries each point's own timestamp in ``as_of``.
    """
    if not isinstance(ts_ms, (int, float)) or isinstance(ts_ms, bool):
        return None
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()


def extract_history_series(
    envelope: Mapping[str, Any], series: str = "prices"
) -> List[ExtractedValue]:
    """Extract a historical series as one ``ExtractedValue`` per data point.

    ``series`` selects which market_chart array to walk: ``"prices"`` (default,
    unit USD), ``"market_caps"`` (USD), or ``"total_volumes"`` (USD). Each point
    is ``[ts_ms, value]``; we emit a normal ``ExtractedValue`` whose ``as_of``
    is that point's timestamp (ms->ISO-8601 UTC) and whose ``value`` is the
    point value. Malformed individual points are skipped, not fatal.

    Returns ``[]`` (rule 1) when the envelope carries no real history series for
    the requested key — we never fabricate points.
    """
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return []
    history = raw.get("history")
    if not isinstance(history, Mapping):
        return []
    points = history.get(series)
    if not isinstance(points, list):
        return []

    # All three market_chart arrays are USD-denominated in our envelopes.
    metric = {"prices": "price", "market_caps": "market_cap",
              "total_volumes": "volume_24h"}.get(series, series)
    subject = envelope.get("subject")

    out: List[ExtractedValue] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        as_of = _ms_to_iso(point[0])
        value = point[1]
        if as_of is None or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        out.append(
            ExtractedValue(
                metric=metric,
                value=float(value),
                unit="USD",
                source=SOURCE,
                subject=subject,
                as_of=as_of,
                provenance={
                    "scope": _SCOPE,
                    "series": series,
                    "ts_ms": point[0],
                    "endpoint": envelope.get("endpoint"),
                },
            )
        )
    return out
