"""Unit + real-envelope tests for analysis_layer/extractors/coingecko.py (B.2.2).

Covers the extractor contract: typed values on success, None/[] on missing
sub-fields (null-guard), the multi_chain scope tag, the series representation
(one ExtractedValue per point), and a decode against the ACTUAL on-disk
envelope (real USDC price ~$0.9997, market cap ~$76.39B).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue
from analysis_layer.extractors import coingecko

ROOT = Path(__file__).resolve().parents[2]
COINGECKO_RAW = ROOT / "meta" / "raw" / "coingecko"


def _envelope(raw_response: dict, **top) -> dict:
    env = {
        "subject": "USDC",
        "subject_type": "stablecoin",
        "freshness_window": "30d",
        "endpoint": "https://api.coingecko.com/api/v3/coins/usd-coin",
        "fetched_at": "2026-05-27T15:23:04.309098+00:00",
        "raw_response": raw_response,
    }
    env.update(top)
    return env


def _spot_envelope(market_data: dict, **spot) -> dict:
    spot_block = {"market_cap_rank": 6, **spot, "market_data": market_data}
    return _envelope({"spot": spot_block})


def _by_metric(values):
    return {ev.metric: ev for ev in values}


# --- extract_spot_metrics ---------------------------------------------------

def test_spot_metrics_typed_values():
    md = {
        "current_price": {"usd": 0.999729},
        "market_cap": {"usd": 76386528510},
        "total_volume": {"usd": 18029185308},
        "total_supply": 76378239615.98817,
        "circulating_supply": 76393215522.45195,
        "market_cap_rank": 6,
        "last_updated": "2026-05-27T15:21:58.765Z",
    }
    values = coingecko.extract_spot_metrics(_spot_envelope(md))
    assert all(isinstance(v, ExtractedValue) for v in values)
    by = _by_metric(values)

    assert by["price"].value == pytest.approx(0.999729)
    assert by["price"].unit == "USD"
    assert by["market_cap"].value == pytest.approx(76386528510)
    assert by["market_cap"].unit == "USD"
    assert by["total_supply"].value == pytest.approx(76378239615.98817)
    assert by["total_supply"].unit == "tokens"
    assert by["volume_24h"].value == pytest.approx(18029185308)
    assert by["volume_24h"].unit == "USD"

    # rank is an ordinal count -> int.
    assert by["market_cap_rank"].value == 6
    assert isinstance(by["market_cap_rank"].value, int)
    assert by["market_cap_rank"].unit == "count"


def test_spot_metrics_carry_source_subject_scope_and_as_of():
    md = {
        "current_price": {"usd": 1.0},
        "last_updated": "2026-05-27T15:21:58.765Z",
    }
    ev = _by_metric(coingecko.extract_spot_metrics(_spot_envelope(md)))["price"]
    assert ev.source == "coingecko"
    assert ev.subject == "USDC"
    # as_of prefers market_data.last_updated over the envelope fetched_at.
    assert ev.as_of == "2026-05-27T15:21:58.765Z"
    # scope tag keeps the multi-chain total apart from single-chain reads.
    assert ev.provenance["scope"] == "multi_chain"


def test_spot_metrics_as_of_falls_back_to_fetched_at():
    md = {"current_price": {"usd": 1.0}}  # no last_updated
    ev = _by_metric(coingecko.extract_spot_metrics(_spot_envelope(md)))["price"]
    assert ev.as_of == "2026-05-27T15:23:04.309098+00:00"


def test_spot_metrics_extracts_self_inconsistency_faithfully():
    # circulating_supply > total_supply is nonsensical but we extract as-is and
    # surface both in provenance — we do NOT correct it.
    md = {
        "total_supply": 76378239615.98817,
        "circulating_supply": 76393215522.45195,
    }
    ev = _by_metric(coingecko.extract_spot_metrics(_spot_envelope(md)))["total_supply"]
    assert ev.value == pytest.approx(76378239615.98817)
    assert ev.provenance["circulating_supply"] > ev.provenance["total_supply"]


def test_spot_metrics_rank_falls_back_to_spot_level():
    # market_data lacks the rank but the spot block carries it.
    md = {"current_price": {"usd": 1.0}}
    values = coingecko.extract_spot_metrics(_spot_envelope(md, market_cap_rank=6))
    assert _by_metric(values)["market_cap_rank"].value == 6


def test_spot_metrics_omits_absent_metrics():
    md = {"current_price": {"usd": 1.0}}  # only price present
    metrics = {ev.metric for ev in coingecko.extract_spot_metrics(_spot_envelope(md))}
    assert "price" in metrics
    assert "market_cap" not in metrics
    assert "total_supply" not in metrics


def test_spot_metrics_missing_market_data_returns_empty():
    # Null-guard (rule 1): no market_data -> [] not a throw.
    assert coingecko.extract_spot_metrics(_envelope({"spot": {}})) == []


def test_spot_metrics_missing_raw_response_returns_empty():
    assert coingecko.extract_spot_metrics({"subject": "x"}) == []


def test_spot_metrics_malformed_nested_usd_returns_empty():
    # current_price present but not a mapping -> price omitted, no throw. Build
    # the spot block directly (no spot-level rank) so nothing else survives.
    env = _envelope({"spot": {"market_data": {"current_price": "oops"}}})
    assert coingecko.extract_spot_metrics(env) == []


# --- extract_history_series -------------------------------------------------

def test_history_series_one_value_per_point():
    history = {"prices": [[1777305677967, 0.9998302489751031],
                          [1779895346000, 0.9996911778182359]]}
    series = coingecko.extract_history_series(_envelope({"history": history}))
    assert len(series) == 2
    assert all(isinstance(v, ExtractedValue) for v in series)

    first = series[0]
    assert first.metric == "price"
    assert first.value == pytest.approx(0.9998302489751031)
    assert first.unit == "USD"
    assert first.source == "coingecko"
    assert first.provenance["scope"] == "multi_chain"
    # ms timestamp converted to ISO-8601 UTC as_of.
    assert first.as_of.startswith("2026-")
    assert first.provenance["ts_ms"] == 1777305677967


def test_history_series_other_series_keys():
    history = {"market_caps": [[1777305677967, 77694019412.84537]]}
    series = coingecko.extract_history_series(
        _envelope({"history": history}), series="market_caps"
    )
    assert len(series) == 1
    assert series[0].metric == "market_cap"
    assert series[0].value == pytest.approx(77694019412.84537)


def test_history_series_skips_malformed_points():
    history = {"prices": [[1777305677967, 1.0], "bad", [123], [None, 2.0]]}
    series = coingecko.extract_history_series(_envelope({"history": history}))
    assert len(series) == 1  # only the first point is well-formed


def test_history_series_absent_returns_empty():
    # No history key at all.
    assert coingecko.extract_history_series(_envelope({"spot": {}})) == []
    # history present but requested series key absent.
    assert coingecko.extract_history_series(
        _envelope({"history": {"prices": []}}), series="total_volumes"
    ) == []
    # missing raw_response entirely.
    assert coingecko.extract_history_series({"subject": "x"}) == []


# --- real envelope ----------------------------------------------------------

def _latest_usdc_envelope() -> dict:
    """The most-recent CoinGecko USDC envelope on disk."""
    candidates = sorted(COINGECKO_RAW.glob("usdc_*.json"), reverse=True)
    for path in candidates:
        return json.loads(path.read_text())
    pytest.skip("no CoinGecko USDC envelope found on disk")


def test_real_envelope_spot_price_and_market_cap():
    env = _latest_usdc_envelope()
    by = _by_metric(coingecko.extract_spot_metrics(env))

    # Real values identified from the on-disk envelope.
    assert by["price"].value == pytest.approx(0.9997, abs=2e-3)   # ~$0.9997
    assert by["market_cap"].value == pytest.approx(76.39e9, rel=1e-3)  # ~$76.39B
    assert by["price"].source == "coingecko"
    assert by["price"].provenance["scope"] == "multi_chain"


def test_real_envelope_surfaces_circulating_over_total():
    env = _latest_usdc_envelope()
    ev = _by_metric(coingecko.extract_spot_metrics(env)).get("total_supply")
    assert ev is not None
    # The real envelope is self-inconsistent: circulating > total. Faithful.
    assert ev.provenance["circulating_supply"] > ev.provenance["total_supply"]


def test_real_envelope_history_series_populated():
    env = _latest_usdc_envelope()
    series = coingecko.extract_history_series(env)
    assert len(series) > 100  # 30d window ~721 points
    assert all(p.unit == "USD" and p.source == "coingecko" for p in series)
    # Points are ordered as stored; each carries its own as_of timestamp.
    assert series[0].as_of != series[-1].as_of
