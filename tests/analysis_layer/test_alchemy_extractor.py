"""Unit + real-envelope tests for analysis_layer/extractors/alchemy.py (B.2.0).

Covers the extractor contract: typed value on success, None on missing
sub-fields (null-guard), and a decode against the ACTUAL on-disk envelope.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue
from analysis_layer.extractors import alchemy

ROOT = Path(__file__).resolve().parents[2]
ALCHEMY_RAW = ROOT / "meta" / "raw" / "alchemy"

# A real USDC totalSupply() hex return decodes to ~52.571B at 6 decimals.
USDC_SUPPLY_HEX = "0x00000000000000000000000000000000000000000000000000bac51e3cbee4cb"


def _envelope(raw_response: dict, **top) -> dict:
    env = {
        "subject": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "subject_type": "stablecoin_issuer",
        "fetched_at": "2026-05-27T15:23:26.998418+00:00",
        "raw_response": raw_response,
    }
    env.update(top)
    return env


# --- decode_total_supply ----------------------------------------------------

def test_decode_total_supply_typed_value():
    env = _envelope({"eth_call": {"id": 2, "jsonrpc": "2.0", "result": USDC_SUPPLY_HEX}})
    ev = alchemy.decode_total_supply(env, decimals=6)

    assert isinstance(ev, ExtractedValue)
    assert ev.metric == "total_supply"
    assert ev.value == pytest.approx(52_571_079_327.016136, rel=1e-9)
    assert ev.unit == "tokens"
    assert ev.source == "alchemy"
    assert ev.subject == env["subject"]
    assert ev.as_of == env["fetched_at"]
    # provenance carries the derivation trail (rule 2)
    assert ev.provenance["decimals"] == 6
    assert ev.provenance["raw_hex"] == USDC_SUPPLY_HEX
    assert ev.provenance["rpc_method"] == "eth_call"


def test_decode_total_supply_decimals_scale():
    # Same raw uint, different decimals -> different human value (decimals is
    # passed in precisely because the envelope doesn't carry it).
    env = _envelope({"eth_call": {"result": "0x0f4240"}})  # 1_000_000
    assert alchemy.decode_total_supply(env, decimals=6).value == pytest.approx(1.0)
    assert alchemy.decode_total_supply(env, decimals=0).value == pytest.approx(1_000_000.0)


def test_decode_total_supply_missing_eth_call_returns_none():
    # Null-guard (rule 1): a chain-level envelope has no eth_call.
    env = _envelope({"eth_blockNumber": {"result": "0x12d687"}})
    assert alchemy.decode_total_supply(env, decimals=6) is None


def test_decode_total_supply_missing_raw_response_returns_none():
    assert alchemy.decode_total_supply({"subject": "x"}, decimals=6) is None


def test_decode_total_supply_unparsable_hex_returns_none():
    env = _envelope({"eth_call": {"result": "not-hex"}})
    assert alchemy.decode_total_supply(env, decimals=6) is None


# --- is_contract ------------------------------------------------------------

def test_is_contract_true_for_bytecode():
    env = _envelope({"eth_getCode": {"result": "0x60806040526004361061006d"}})
    assert alchemy.is_contract(env) is True


def test_is_contract_false_for_eoa():
    env = _envelope({"eth_getCode": {"result": "0x"}})
    assert alchemy.is_contract(env) is False


def test_is_contract_missing_returns_none():
    # Null-guard (rule 1): None means "unknown", not False.
    env = _envelope({"eth_call": {"result": USDC_SUPPLY_HEX}})
    assert alchemy.is_contract(env) is None


# --- real envelope ----------------------------------------------------------

def _latest_token_envelope() -> dict:
    """The most-recent Alchemy envelope that actually carries an eth_call read
    (i.e. a token/issuer envelope, not a chain-level one)."""
    candidates = sorted(ALCHEMY_RAW.glob("*.json"), reverse=True)
    for path in candidates:
        env = json.loads(path.read_text())
        if "eth_call" in env.get("raw_response", {}):
            return env
    pytest.skip("no Alchemy envelope with an eth_call found on disk")


def test_real_envelope_decodes_usdc_supply():
    env = _latest_token_envelope()
    ev = alchemy.decode_total_supply(env, decimals=6)  # USDC = 6 decimals

    assert ev is not None
    # ~52.571B USDC. Loose band so normal mint/burn between fetches doesn't break it.
    assert ev.value == pytest.approx(52.571e9, rel=1e-3)
    assert ev.source == "alchemy"
    assert ev.as_of == env["fetched_at"]


def test_real_envelope_subject_is_a_contract():
    env = _latest_token_envelope()
    # The USDC proxy is a deployed contract.
    assert alchemy.is_contract(env) is True
