"""Unit + real-envelope tests for analysis_layer/extractors/coinmarketcap.py (B.2.4).

Covers the CMC latest-quote extractor contract: typed scalars on success,
graceful ``[]`` on missing data/coin/field (null-guard, rule 1), the
keyed-by-CMC-id ``data`` structure (the id is a subject_ref dependency, not
hard-coded — TD-023), ``scope="multi_chain"`` provenance, ``as_of`` derived
from the quote's ``last_updated``, the free-tier ``quotes_historical: null``
soft-skip, and a real USDC envelope decode.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue
from analysis_layer.extractors import coinmarketcap

ROOT = Path(__file__).resolve().parents[2]
# Canonical sibling convention (cf. alchemy/sec_edgar tests). In this worktree
# the raw store is reached through a nested ``raw`` symlink (meta/raw/raw/...),
# so the real-envelope helper also probes that path — see _real_usdc_envelope.
CMC_RAW = ROOT / "meta" / "raw" / "coinmarketcap"
CMC_RAW_NESTED = ROOT / "meta" / "raw" / "raw" / "coinmarketcap"


# --------------------------------------------------------------------------- #
# inline-mock envelope builders (keyed-by-id structure)
# --------------------------------------------------------------------------- #
def _coin(
    cmc_id: str = "3408",
    *,
    price=0.9993,
    market_cap=76_340_305_187.0,
    circulating=76_395_675_503.8,
    total=76_395_675_503.8,
    quote_last_updated="2026-05-27T15:22:04.000Z",
    coin_last_updated="2026-05-27T15:21:00.000Z",
) -> dict:
    return {
        cmc_id: {
            "id": int(cmc_id),
            "name": "USDC",
            "symbol": "USDC",
            "circulating_supply": circulating,
            "total_supply": total,
            "last_updated": coin_last_updated,
            "quote": {
                "USD": {
                    "price": price,
                    "market_cap": market_cap,
                    "volume_24h": 1.0,
                    "last_updated": quote_last_updated,
                }
            },
        }
    }


def _envelope(data: dict, *, historical=None, subject="USDC") -> dict:
    return {
        "subject": subject,
        "subject_type": "stablecoin",
        "freshness_window": "30d",
        "endpoint": "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=3408",
        "fetched_at": "2026-05-27T15:23:39.899229+00:00",
        "raw_response": {
            "resolve": {},
            "quotes_latest": {"status": {}, "data": data},
            "quotes_historical": historical,
        },
    }


def _by_metric(values):
    return {v.metric: v for v in values}


# --------------------------------------------------------------------------- #
# extract_latest_quote — happy path
# --------------------------------------------------------------------------- #
def test_latest_quote_emits_four_scalars():
    out = coinmarketcap.extract_latest_quote(_envelope(_coin()))
    by = _by_metric(out)
    assert set(by) == {"price", "market_cap", "circulating_supply", "total_supply"}
    assert all(isinstance(v, ExtractedValue) for v in out)


def test_latest_quote_units_and_source():
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(_coin())))
    assert by["price"].unit == "USD"
    assert by["market_cap"].unit == "USD"
    assert by["circulating_supply"].unit == "tokens"
    assert by["total_supply"].unit == "tokens"
    assert all(v.source == "coinmarketcap" for v in by.values())
    assert all(v.subject == "USDC" for v in by.values())


def test_latest_quote_values_are_typed_floats():
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(_coin())))
    assert by["price"].value == pytest.approx(0.9993)
    assert by["market_cap"].value == pytest.approx(76_340_305_187.0)
    assert isinstance(by["price"].value, float)


def test_latest_quote_scope_is_multi_chain():
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(_coin())))
    assert all(v.provenance["scope"] == "multi_chain" for v in by.values())


def test_latest_quote_carries_cmc_id_provenance_not_hardcoded():
    # data keyed by an arbitrary id -> extractor must read it, never assume 3408.
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(_coin("1027"))))
    assert by["price"].provenance["cmc_id"] == 1027


def test_latest_quote_as_of_prefers_quote_last_updated():
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(_coin())))
    assert by["price"].as_of == "2026-05-27T15:22:04.000Z"


def test_latest_quote_as_of_falls_back_to_coin_then_fetched_at():
    # No quote.last_updated -> coin.last_updated; price still uses coin ts.
    env = _envelope(_coin(quote_last_updated=None))
    by = _by_metric(coinmarketcap.extract_latest_quote(env))
    assert by["price"].as_of == "2026-05-27T15:21:00.000Z"

    env2 = _envelope(_coin(quote_last_updated=None, coin_last_updated=None))
    by2 = _by_metric(coinmarketcap.extract_latest_quote(env2))
    assert by2["price"].as_of == "2026-05-27T15:23:39.899229+00:00"  # fetched_at


# --------------------------------------------------------------------------- #
# keyed-by-id selection
# --------------------------------------------------------------------------- #
def test_single_entry_inferred_without_subject_id():
    out = coinmarketcap.extract_latest_quote(_envelope(_coin("3408")))
    assert _by_metric(out)["price"].provenance["cmc_id"] == 3408


def test_subject_id_selects_among_multiple_entries():
    data = {**_coin("3408", price=0.9993), **_coin("1027", price=2500.0)}
    # id passed as int; data keys are strings -> extractor must stringify.
    out = coinmarketcap.extract_latest_quote(_envelope(data), subject_id=1027)
    assert _by_metric(out)["price"].value == pytest.approx(2500.0)


def test_ambiguous_multiple_entries_without_id_returns_empty():
    data = {**_coin("3408"), **_coin("1027")}
    assert coinmarketcap.extract_latest_quote(_envelope(data)) == []


def test_subject_id_absent_returns_empty():
    assert coinmarketcap.extract_latest_quote(_envelope(_coin("3408")), subject_id=9999) == []


# --------------------------------------------------------------------------- #
# null-guards (rule 1: missing hop -> [], never throw)
# --------------------------------------------------------------------------- #
def test_missing_raw_response_returns_empty():
    assert coinmarketcap.extract_latest_quote({"subject": "USDC"}) == []


def test_missing_quotes_latest_returns_empty():
    assert coinmarketcap.extract_latest_quote({"raw_response": {}}) == []


def test_missing_data_returns_empty():
    env = {"raw_response": {"quotes_latest": {"status": {}}}}
    assert coinmarketcap.extract_latest_quote(env) == []


def test_missing_usd_quote_still_yields_supply_only():
    coin = _coin()
    coin["3408"]["quote"] = {}  # no USD block -> price/market_cap omitted
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(coin)))
    assert set(by) == {"circulating_supply", "total_supply"}


def test_non_numeric_field_is_omitted():
    coin = _coin()
    coin["3408"]["quote"]["USD"]["price"] = None
    coin["3408"]["total_supply"] = "n/a"
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(coin)))
    assert set(by) == {"market_cap", "circulating_supply"}


def test_bool_is_not_treated_as_numeric():
    coin = _coin()
    coin["3408"]["quote"]["USD"]["price"] = True  # bool is an int in Python
    by = _by_metric(coinmarketcap.extract_latest_quote(_envelope(coin)))
    assert "price" not in by


# --------------------------------------------------------------------------- #
# historical helper — free-tier null soft-skip + present-data path
# --------------------------------------------------------------------------- #
def test_historical_null_returns_empty_no_throw():
    # The free-tier reality: quotes_historical is null.
    assert coinmarketcap.extract_historical_quotes(_envelope(_coin(), historical=None)) == []


def test_historical_missing_raw_response_returns_empty():
    assert coinmarketcap.extract_historical_quotes({"subject": "USDC"}) == []


def test_historical_present_emits_price_points():
    historical = {
        "data": {
            "3408": {
                "id": 3408,
                "quotes": [
                    {"timestamp": "2026-05-20T00:00:00.000Z", "quote": {"USD": {"price": 0.999}}},
                    {"timestamp": "2026-05-21T00:00:00.000Z", "quote": {"USD": {"price": 1.0001}}},
                ],
            }
        }
    }
    out = coinmarketcap.extract_historical_quotes(_envelope(_coin(), historical=historical))
    assert [v.value for v in out] == pytest.approx([0.999, 1.0001])
    assert all(v.metric == "price" and v.unit == "USD" for v in out)
    assert out[0].as_of == "2026-05-20T00:00:00.000Z"
    assert all(v.provenance["scope"] == "multi_chain" for v in out)


# --------------------------------------------------------------------------- #
# real envelope
# --------------------------------------------------------------------------- #
def _real_usdc_envelope() -> dict:
    """The most-recent real CMC USDC envelope on disk, or skip if none.

    Probes the canonical ``meta/raw/coinmarketcap`` path first, then the nested
    ``meta/raw/raw/coinmarketcap`` (this worktree reaches the shared raw store
    through a nested ``raw`` symlink). Picks the newest ``usdc_*`` file.
    """
    for base in (CMC_RAW, CMC_RAW_NESTED):
        if not base.exists():
            continue
        candidates = sorted(base.glob("usdc_*.json"), reverse=True)
        if candidates:
            return json.loads(candidates[0].read_text())
    pytest.skip("no real CoinMarketCap USDC envelope found on disk")


def test_real_envelope_usdc_price_and_market_cap():
    env = _real_usdc_envelope()
    by = _by_metric(coinmarketcap.extract_latest_quote(env))

    # Real values from usdc_20260527T152339Z.json (verified manually, TD-023).
    assert by["price"].value == pytest.approx(0.9993, abs=1e-3)   # ~$0.9993
    assert by["market_cap"].value == pytest.approx(76.34e9, rel=1e-3)  # ~$76.34B
    assert by["price"].unit == "USD"
    assert by["price"].source == "coinmarketcap"
    assert by["price"].provenance["scope"] == "multi_chain"
    # id resolved from the keyed data dict, not hard-coded.
    assert by["price"].provenance["cmc_id"] == 3408
    assert by["price"].as_of == "2026-05-27T15:22:04.000Z"


def test_real_envelope_supply_and_historical_null():
    env = _real_usdc_envelope()
    by = _by_metric(coinmarketcap.extract_latest_quote(env))
    assert by["circulating_supply"].value == pytest.approx(76.4e9, rel=1e-2)
    assert by["circulating_supply"].unit == "tokens"
    # Free tier -> quotes_historical is null -> helper degrades to [], no throw.
    assert coinmarketcap.extract_historical_quotes(env) == []
