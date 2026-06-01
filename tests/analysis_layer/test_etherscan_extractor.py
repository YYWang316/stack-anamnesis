"""Unit + real-envelope tests for analysis_layer/extractors/etherscan.py (B.2.3).

Covers the extractor contract: typed value on success, None on missing
sub-fields (null-guard), the decimal-string decode (contrast Alchemy's hex),
the single-chain scope tag, the deferred transfer stub, and a decode against an
ACTUAL on-disk envelope when one exists.

TD-023 note: at build time NO Etherscan envelope was present under
``meta/raw/etherscan/`` (``meta/raw/`` held only ``.gitkeep`` — the Alchemy and
SEC envelopes were likewise absent). The real-envelope test therefore mirrors
the sibling test pattern (test_alchemy_extractor / test_sec_edgar_extractor):
glob the directory and ``pytest.skip`` when empty, so it auto-activates and
asserts the ~52.6B USDC value once a fetcher run lands an envelope on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue
from analysis_layer.extractors import etherscan

ROOT = Path(__file__).resolve().parents[2]
ETHERSCAN_RAW = ROOT / "meta" / "raw" / "etherscan"

# A real USDC totalSupply in 6-decimal base units (decimal STRING as Etherscan
# returns it). Same supply the Alchemy test decodes from hex, so the two
# extractors are provably cross-checkable: /1e6 -> ~52.571B USDC.
USDC_SUPPLY_DEC = "52571079327016136"


def _envelope(raw_response: dict, **top) -> dict:
    env = {
        "subject": "USDC",
        "subject_type": "stablecoin",
        "freshness_window": "30d",
        "endpoint": "https://api.etherscan.io/v2/api?chainid=1",
        "fetched_at": "2026-05-27T15:23:26.998418+00:00",
        "raw_response": raw_response,
    }
    env.update(top)
    return env


def _supply_block(result) -> dict:
    return {"tokensupply": {"status": "1", "message": "OK", "result": result}}


# --- extract_supply ---------------------------------------------------------

def test_extract_supply_typed_value():
    env = _envelope(_supply_block(USDC_SUPPLY_DEC))
    ev = etherscan.extract_supply(env, decimals=6)

    assert isinstance(ev, ExtractedValue)
    assert ev.metric == "total_supply"  # SAME canonical name as alchemy
    assert ev.value == pytest.approx(52_571_079_327.016136, rel=1e-9)
    assert ev.unit == "tokens"
    assert ev.source == "etherscan"
    assert ev.subject == "USDC"
    assert ev.as_of == env["fetched_at"]
    # provenance carries the derivation trail (rule 2)
    assert ev.provenance["decimals"] == 6
    assert ev.provenance["raw_result"] == USDC_SUPPLY_DEC
    assert ev.provenance["raw_uint256"] == 52_571_079_327_016_136
    assert ev.provenance["endpoint_action"] == "stats/tokensupply"


def test_extract_supply_single_chain_scope_tag():
    # Scope tag keeps this reading out of the multi-chain-aggregator bucket.
    ev = etherscan.extract_supply(_envelope(_supply_block(USDC_SUPPLY_DEC)), decimals=6)
    assert ev.provenance["scope"] == "single-chain"
    assert ev.provenance["chain"] == "ethereum"
    assert ev.provenance["chainid"] == 1


def test_extract_supply_chain_derived_from_endpoint():
    # Multi-chain fetcher: chain is read from the endpoint, not hard-coded.
    env = _envelope(
        _supply_block(USDC_SUPPLY_DEC),
        endpoint="https://api.etherscan.io/v2/api?chainid=137",
    )
    ev = etherscan.extract_supply(env, decimals=6)
    assert ev.provenance["chain"] == "polygon"
    assert ev.provenance["chainid"] == 137


def test_extract_supply_decimal_string_not_hex():
    # Decimal "0x..."-looking input would be wrong here: the value is a plain
    # decimal string. "1000000" -> 1.0 at 6 decimals (NOT int(x, 16)).
    env = _envelope(_supply_block("1000000"))
    assert etherscan.extract_supply(env, decimals=6).value == pytest.approx(1.0)
    assert etherscan.extract_supply(env, decimals=0).value == pytest.approx(1_000_000.0)


def test_extract_supply_tolerates_raw_int_result():
    # Defensive: a JSON int (not string) still decodes.
    env = _envelope(_supply_block(1_000_000))
    assert etherscan.extract_supply(env, decimals=6).value == pytest.approx(1.0)


def test_extract_supply_missing_tokensupply_returns_none():
    # Null-guard (rule 1).
    env = _envelope({"tokentx": {"status": "1", "result": []}})
    assert etherscan.extract_supply(env, decimals=6) is None


def test_extract_supply_missing_result_returns_none():
    env = _envelope({"tokensupply": {"status": "0", "message": "NOTOK"}})
    assert etherscan.extract_supply(env, decimals=6) is None


def test_extract_supply_missing_raw_response_returns_none():
    assert etherscan.extract_supply({"subject": "USDC"}, decimals=6) is None


def test_extract_supply_unparsable_result_returns_none():
    env = _envelope(_supply_block("not-a-number"))
    assert etherscan.extract_supply(env, decimals=6) is None


# --- aggregate_transfers (deferred stub) ------------------------------------

def test_aggregate_transfers_is_deferred_none():
    # Single-page tokentx cannot yield a faithful 30d aggregate (fetcher fix).
    env = _envelope(
        {"tokentx": {"status": "1", "result": [{"hash": "0x1"}, {"hash": "0x2"}]}}
    )
    assert etherscan.aggregate_transfers(env) is None


# --- real envelope ----------------------------------------------------------

def _latest_etherscan_envelope() -> dict:
    """Most-recent Etherscan envelope carrying a tokensupply result on disk."""
    candidates = sorted(ETHERSCAN_RAW.glob("*.json"), reverse=True)
    for path in candidates:
        env = json.loads(path.read_text())
        if etherscan._tokensupply_result(env) is not None:
            return env
    pytest.skip("no Etherscan envelope with a tokensupply result found on disk")


def test_real_envelope_decodes_usdc_supply():
    env = _latest_etherscan_envelope()
    ev = etherscan.extract_supply(env, decimals=6)  # USDC = 6 decimals

    assert ev is not None
    # ~52.6B USDC. Loose band so normal mint/burn between fetches doesn't break it.
    assert ev.value == pytest.approx(52.6e9, rel=5e-2)
    assert ev.source == "etherscan"
    assert ev.metric == "total_supply"
    assert ev.as_of == env["fetched_at"]
    assert ev.provenance["scope"] == "single-chain"
