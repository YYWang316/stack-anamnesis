"""Extractor for CoinMarketCap quotes envelopes (tools/fetchers/coinmarketcap_fetch.py).

Envelope shape (verified against meta/raw/coinmarketcap/*.json, TD-023):

    {
      "subject": "USDC",
      "subject_type": "stablecoin",
      "freshness_window": "30d",
      "endpoint": "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=3408",
      "fetched_at": "2026-05-27T15:23:39.899229+00:00",
      "raw_response": {
        "resolve":          {... slug or symbol lookup that resolved the id ...},
        "quotes_latest": {
          "status": {...},
          "data": {                       # KEYED BY CMC NUMERIC ID, not symbol
            "3408": {
              "name": "USDC", "symbol": "USDC",
              "circulating_supply": 76395675503.82164,
              "total_supply":       76395675503.82164,
              "last_updated": "2026-05-27T15:21:00.000Z",
              "quote": {"USD": {
                "price":       0.9992752166125525,
                "market_cap":  76340305187.34364,
                "volume_24h":  16428003746.269669,
                "last_updated": "2026-05-27T15:22:04.000Z"
              }}
            }
          }
        },
        "quotes_historical": null         # Pro-gated -> null on the Basic free tier
      }
    }

Two structural facts drive this extractor:

1. ``quotes_latest.data`` is KEYED BY CMC NUMERIC ID (USDC = "3408"), not by
   symbol or name. The numeric id is therefore a *subject_ref dependency* — the
   same kind of out-of-envelope binding that ``decimals`` is for the Alchemy
   supply decode or the contract address is for an Etherscan read. We do NOT
   hard-code "3408": the caller may pass the resolved id, and when the envelope
   holds exactly one entry (the single-subject free-tier fetch) we take it.

2. ``quotes_historical`` is Pro-gated and comes back ``null`` on our Basic free
   tier (the fetcher soft-skips the 401). The historical helper must degrade to
   ``[]`` gracefully and NEVER throw on that null.

CMC is a multi-chain aggregator: a quote reflects supply/price across every
chain the token lives on, not a single deployment. Every value is therefore
tagged ``scope="multi_chain"`` in provenance so the aggregator never silently
reconciles it against a single-chain on-chain read (e.g. Alchemy) as if the two
measured the same thing.

All functions here are pure (rule 3): envelope in, typed values out, no I/O.
Every hop is null-guarded (rule 1): a missing data dict / coin / nested field
returns ``[]`` (a quote naturally degrades to "no values"), never throws.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional, Union

from analysis_layer.contract import ExtractedValue

SOURCE = "coinmarketcap"

# CMC aggregates across every chain a token lives on — provenance flag so the
# aggregator never reconciles a multi-chain quote against a single-chain read.
SCOPE = "multi_chain"

# Quote currency. CMC can return multiple convert currencies; our fetcher takes
# the API default (USD). Pinned here so the unit we emit is never ambiguous.
_QUOTE_CCY = "USD"


# --------------------------------------------------------------------------- #
# envelope navigation helpers (each hop null-guarded — rule 1)
# --------------------------------------------------------------------------- #
def _quotes_latest_data(envelope: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return ``raw_response.quotes_latest.data`` or None if any hop missing."""
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return None
    latest = raw.get("quotes_latest")
    if not isinstance(latest, Mapping):
        return None
    data = latest.get("data")
    return data if isinstance(data, Mapping) else None


def _select_coin(
    data: Mapping[str, Any], subject_id: Optional[Union[str, int]]
) -> Optional[Mapping[str, Any]]:
    """Pick the one coin block out of the id-keyed ``data`` dict.

    The data dict is keyed by CMC numeric id (a subject_ref dependency, see
    module docstring). Resolution:
      * ``subject_id`` given -> look it up by string key (ids are stringified
        in JSON), return None if absent.
      * else exactly one entry -> take it (the single-subject free-tier fetch).
      * else (ambiguous: 0 or >1 entries, no id) -> None. We refuse to guess
        which subject the caller meant rather than silently pick the first.
    """
    if subject_id is not None:
        coin = data.get(str(subject_id))
        return coin if isinstance(coin, Mapping) else None
    if len(data) == 1:
        coin = next(iter(data.values()))
        return coin if isinstance(coin, Mapping) else None
    return None


def _as_of(coin: Mapping[str, Any], quote: Mapping[str, Any], envelope: Mapping[str, Any]) -> Optional[str]:
    """ISO timestamp the value reflects.

    Preference order: the quote's own ``last_updated`` (per-currency, the most
    specific freshness CMC reports for a price/market-cap), then the coin-level
    ``last_updated`` (the freshness anchor for supply, which lives outside the
    quote), then the envelope's ``fetched_at`` (the snapshot read time) as the
    final honest fallback. Mirrors the live-snapshot ``as_of`` of Alchemy
    (fetched_at) while preferring CMC's richer per-quote timestamp when present.
    """
    for ts in (quote.get("last_updated"), coin.get("last_updated"), envelope.get("fetched_at")):
        if isinstance(ts, str) and ts:
            return ts
    return None


def _numeric(value: Any) -> Optional[float]:
    """Return ``value`` as a float if it is a real number, else None.

    Bools are ints in Python; reject them so a stray ``True`` never becomes 1.0.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def extract_latest_quote(
    envelope: Mapping[str, Any], subject_id: Optional[Union[str, int]] = None
) -> List[ExtractedValue]:
    """Extract the latest-quote scalars for one subject.

    Emits up to four ``ExtractedValue``s — ``price`` (USD), ``market_cap``
    (USD), ``circulating_supply`` (tokens), ``total_supply`` (tokens). A metric
    whose source field is absent or non-numeric is simply omitted (rule 1: the
    quote degrades to fewer values, never throws). Returns ``[]`` if the data
    dict / coin / USD quote can't be located.

    Parameters
    ----------
    subject_id : optional CMC numeric id (the subject_ref dependency). When the
        envelope holds a single subject (our free-tier fetch) it is inferred;
        pass it explicitly to disambiguate a multi-subject envelope.

    ``price`` / ``market_cap`` come from ``quote.USD``; ``circulating_supply`` /
    ``total_supply`` are coin-level (chain-agnostic, hence ``unit="tokens"`` —
    the subject identifies which token). All carry ``scope="multi_chain"``.
    """
    data = _quotes_latest_data(envelope)
    if data is None:
        return []
    coin = _select_coin(data, subject_id)
    if coin is None:
        return []

    quote_block = coin.get("quote")
    quote = quote_block.get(_QUOTE_CCY) if isinstance(quote_block, Mapping) else None
    if not isinstance(quote, Mapping):
        quote = {}

    cmc_id = coin.get("id")
    subject = envelope.get("subject")
    as_of = _as_of(coin, quote, envelope)

    def _base_provenance(extra: Mapping[str, Any]) -> dict:
        prov = {
            "scope": SCOPE,  # multi-chain aggregate — never a single-chain read
            "cmc_id": cmc_id,  # subject_ref dependency (data is keyed by this id)
            "symbol": coin.get("symbol"),
            "name": coin.get("name"),
            "endpoint": envelope.get("endpoint"),
            "fetched_at": envelope.get("fetched_at"),
        }
        prov.update(extra)
        return prov

    # (metric, raw value, unit, source-field provenance) — USD quote first,
    # then the coin-level supply fields.
    specs = (
        ("price", quote.get("price"), _QUOTE_CCY, {"field": "quote.USD.price", "quote_last_updated": quote.get("last_updated")}),
        ("market_cap", quote.get("market_cap"), _QUOTE_CCY, {"field": "quote.USD.market_cap", "quote_last_updated": quote.get("last_updated")}),
        ("circulating_supply", coin.get("circulating_supply"), "tokens", {"field": "circulating_supply", "coin_last_updated": coin.get("last_updated")}),
        ("total_supply", coin.get("total_supply"), "tokens", {"field": "total_supply", "coin_last_updated": coin.get("last_updated")}),
    )

    out: List[ExtractedValue] = []
    for metric, raw_value, unit, extra in specs:
        num = _numeric(raw_value)
        if num is None:
            continue  # rule 1: missing/non-numeric field -> omit, don't throw
        out.append(
            ExtractedValue(
                metric=metric,
                value=num,
                unit=unit,
                source=SOURCE,
                subject=subject,
                as_of=as_of,
                provenance=_base_provenance(extra),
            )
        )
    return out


def extract_historical_quotes(
    envelope: Mapping[str, Any], subject_id: Optional[Union[str, int]] = None
) -> List[ExtractedValue]:
    """Extract historical price points from ``raw_response.quotes_historical``.

    Pro-gated: on our Basic free tier the fetcher soft-skips the 401 and writes
    ``quotes_historical: null``. This helper MUST return ``[]`` on that null (and
    on any missing hop) and NEVER throw — the absence of history is the normal,
    expected state, not an error.

    When history IS present (a Pro-tier envelope) the shape is
    ``data[<id>].quotes`` -> a list of ``{timestamp, quote: {USD: {price, ...}}}``
    points; we emit one ``price`` ExtractedValue per point with ``as_of`` set to
    that point's timestamp. Every value carries ``scope="multi_chain"``.
    """
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return []
    historical = raw.get("quotes_historical")
    if not isinstance(historical, Mapping):
        # Includes the free-tier null (None) — the primary degradation path.
        return []
    data = historical.get("data")
    if not isinstance(data, Mapping):
        return []
    coin = _select_coin(data, subject_id)
    if coin is None:
        return []
    points = coin.get("quotes")
    if not isinstance(points, list):
        return []

    subject = envelope.get("subject")
    cmc_id = coin.get("id")
    out: List[ExtractedValue] = []
    for point in points:
        if not isinstance(point, Mapping):
            continue
        quote_block = point.get("quote")
        usd = quote_block.get(_QUOTE_CCY) if isinstance(quote_block, Mapping) else None
        if not isinstance(usd, Mapping):
            continue
        price = _numeric(usd.get("price"))
        if price is None:
            continue
        ts = point.get("timestamp")
        as_of = ts if isinstance(ts, str) and ts else usd.get("last_updated")
        out.append(
            ExtractedValue(
                metric="price",
                value=price,
                unit=_QUOTE_CCY,
                source=SOURCE,
                subject=subject,
                as_of=as_of if isinstance(as_of, str) else None,
                provenance={
                    "scope": SCOPE,
                    "cmc_id": cmc_id,
                    "field": "quotes_historical.quote.USD.price",
                    "endpoint": envelope.get("endpoint"),
                    "fetched_at": envelope.get("fetched_at"),
                },
            )
        )
    return out
