"""Unit + real-envelope tests for analysis_layer/extractors/defillama.py (B.2.5).

Covers the series contract: one ExtractedValue per daily point, the SUPPLY
field (totalCirculating, not the market-value totalCirculatingUSD) chosen,
unix->ISO ``as_of`` per point, multi_chain provenance scope, and the
``[]``-on-malformed null-guard. The real-envelope test decodes the actual
on-disk USDC chart.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue
from analysis_layer.extractors import defillama

ROOT = Path(__file__).resolve().parents[2]
DEFILLAMA_RAW = ROOT / "meta" / "raw" / "defillama"


def _envelope(raw_response, **top) -> dict:
    env = {
        "subject": "USDC",
        "subject_type": "stablecoin",
        "freshness_window": "30d",
        "endpoint": "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=2",
        "fetched_at": "2026-06-01T16:27:13.870016+00:00",
        "raw_response": raw_response,
    }
    env.update(top)
    return env


# A tiny hand-built series: 3 daily points. The supply (totalCirculating) is
# deliberately distinct from the market-value (totalCirculatingUSD) so the test
# proves the extractor picks the SUPPLY field.
_MOCK_SERIES = [
    {"date": "1536624000",
     "totalCirculating": {"peggedUSD": 2.0},
     "totalCirculatingUSD": {"peggedUSD": 2.0}},
    {"date": "1536710400",
     "totalCirculating": {"peggedUSD": 1000.5},
     "totalCirculatingUSD": {"peggedUSD": 999.4}},
    {"date": "1780272000",
     "totalCirculating": {"peggedUSD": 75898768744.57},
     "totalCirculatingUSD": {"peggedUSD": 75869226873.40}},
]


# --- extract_stablecoin_supply_series: inline mock --------------------------

def test_series_one_value_per_point():
    series = defillama.extract_stablecoin_supply_series(_envelope(_MOCK_SERIES))
    assert len(series) == 3
    assert all(isinstance(ev, ExtractedValue) for ev in series)


def test_series_picks_supply_not_market_value():
    # totalCirculating (1000.5), NOT totalCirculatingUSD (999.4).
    series = defillama.extract_stablecoin_supply_series(_envelope(_MOCK_SERIES))
    mid = series[1]
    assert mid.value == pytest.approx(1000.5)
    assert mid.provenance["market_value_usd"] == pytest.approx(999.4)
    assert mid.provenance["field"] == "totalCirculating.peggedUSD"


def test_series_value_contract_fields():
    series = defillama.extract_stablecoin_supply_series(_envelope(_MOCK_SERIES))
    ev = series[0]
    assert ev.metric == "circulating_supply"
    assert ev.unit == "USD"
    assert ev.source == "defillama"
    assert ev.subject == "USDC"
    # multi-chain aggregate provenance (scope rule)
    assert ev.provenance["scope"] == "multi_chain"
    assert ev.provenance["fetched_at"] == "2026-06-01T16:27:13.870016+00:00"


def test_series_as_of_is_iso_from_unix():
    series = defillama.extract_stablecoin_supply_series(_envelope(_MOCK_SERIES))
    # 1536624000 -> 2018-09-11T00:00:00+00:00
    assert series[0].as_of == "2018-09-11T00:00:00+00:00"
    # newest point lands on the expected day
    assert series[-1].as_of == "2026-06-01T00:00:00+00:00"
    # every as_of round-trips back to its raw unix date
    for ev in series:
        ts = int(datetime.fromisoformat(ev.as_of).timestamp())
        assert str(ts) == ev.provenance["raw_date"]


def test_series_order_is_chronological_and_latest_is_last():
    env = _envelope(_MOCK_SERIES)
    series = defillama.extract_stablecoin_supply_series(env)
    assert series[-1].value == pytest.approx(75898768744.57)
    # latest() is just the last point of the series
    assert defillama.latest(env) == series[-1]


def test_series_skips_malformed_points_without_throwing():
    raw = [
        {"date": "1536624000", "totalCirculating": {"peggedUSD": 5.0}},
        {"date": "1536710400", "totalCirculating": {"peggedUSD": None}},   # bad value
        {"date": "1536796800", "totalCirculating": {}},                    # no peggedUSD
        {"date": "bad", "totalCirculating": {"peggedUSD": 9.0}},           # bad date
        "not-a-dict",                                                       # not a point
        {"date": "1536883200", "totalCirculating": {"peggedUSD": 7.0}},
    ]
    series = defillama.extract_stablecoin_supply_series(_envelope(raw))
    # only the two well-formed points survive
    assert [ev.value for ev in series] == [5.0, 7.0]


# --- null-guards (rule 1) ---------------------------------------------------

def test_empty_list_returns_empty():
    assert defillama.extract_stablecoin_supply_series(_envelope([])) == []


def test_missing_raw_response_returns_empty():
    assert defillama.extract_stablecoin_supply_series({"subject": "USDC"}) == []


def test_non_list_raw_response_returns_empty():
    # A dict (or string) raw_response is malformed for this series extractor.
    assert defillama.extract_stablecoin_supply_series(_envelope({"oops": 1})) == []
    assert defillama.extract_stablecoin_supply_series(_envelope("abc")) == []


def test_latest_empty_returns_none():
    assert defillama.latest(_envelope([])) is None
    assert defillama.latest({"subject": "USDC"}) is None


# --- real envelope ----------------------------------------------------------

def _latest_stablecoin_envelope() -> dict:
    # pinned to USDC's own slug so a second subject's envelopes (e.g. usdt_*.json)
    # in the shared raw dir are not picked (multi-subject isolation, TD-046).
    candidates = sorted(DEFILLAMA_RAW.glob("usdc_*.json"), reverse=True)
    for path in candidates:
        env = json.loads(path.read_text())
        if isinstance(env.get("raw_response"), list) and env["raw_response"]:
            return env
    pytest.skip("no DefiLlama stablecoin envelope (non-empty list) found on disk")


def test_real_envelope_series_length_and_latest():
    env = _latest_stablecoin_envelope()
    series = defillama.extract_stablecoin_supply_series(env)

    # ~2821 daily points as of this envelope; loose band tolerates a fresher
    # re-fetch adding more days. (Mandate said ~2817; live reality is larger.)
    assert len(series) > 2500
    assert len(series) == len(env["raw_response"])  # every real point is well-formed

    ev = defillama.latest(env)
    assert ev is not None
    assert ev.metric == "circulating_supply"
    assert ev.source == "defillama"
    assert ev.unit == "USD"
    # ~$75.9B USDC circulating. Wide band so normal mint/burn between fetches
    # (or a fresher envelope) doesn't break it.
    assert ev.value == pytest.approx(76e9, rel=0.05)
    # the supply is the larger of the two pegged figures (USDC trades <= $1)
    assert ev.value >= ev.provenance["market_value_usd"]
    # as_of is a valid ISO timestamp at the per-day granularity
    assert datetime.fromisoformat(ev.as_of).tzinfo == timezone.utc
