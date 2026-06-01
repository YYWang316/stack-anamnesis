"""Extractor for Alchemy JSON-RPC envelopes (tools/fetchers/alchemy_fetch.py).

Envelope shape (verified against meta/raw/alchemy/*.json, TD-023):

    {
      "subject": "0xA0b8...eB48",          # USDC contract for token reads
      "subject_type": "stablecoin_issuer",
      "freshness_window": "30d",
      "endpoint": "https://eth-mainnet.g.alchemy.com/v2/<REDACTED>",
      "fetched_at": "2026-05-27T15:23:26.998418+00:00",
      "raw_response": {
        "eth_getCode": {"id": 1, "jsonrpc": "2.0", "result": "0x6080..."},
        "eth_call":    {"id": 2, "jsonrpc": "2.0", "result": "0x...hex"}
      }
    }

NB: which sub-calls are present depends on subject_type. A ``chain`` envelope
carries ``eth_blockNumber``/``eth_gasPrice`` and NO ``eth_call`` — hence the
null-guards below (rule 1: missing sub-fields return None, never throw).

All functions here are pure (rule 3): envelope in, typed value out.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from analysis_layer.contract import ExtractedValue

SOURCE = "alchemy"


def _rpc_result(envelope: Mapping[str, Any], method: str) -> Optional[str]:
    """Return ``raw_response.<method>.result`` or None if any hop is missing.

    Defensive at every level: envelope, raw_response, the method block, and the
    result key can each be absent or non-dict in a real envelope.
    """
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return None
    block = raw.get(method)
    if not isinstance(block, Mapping):
        return None
    result = block.get("result")
    return result if isinstance(result, str) else None


def decode_total_supply(
    envelope: Mapping[str, Any], decimals: int
) -> Optional[ExtractedValue]:
    """Decode an ``eth_call`` totalSupply() return into a human-scale amount.

    ``decimals`` is passed IN, not read from the envelope: the Alchemy envelope
    does not carry the token's decimals (USDC = 6). This is precisely why a
    subject_ref resolver exists in the roadmap — it maps subject -> decimals so
    callers don't have to hard-code. Until then the caller supplies it.

    Returns None (rule 1) if ``eth_call`` is absent, e.g. a chain-level
    envelope, or if the hex result can't be parsed.
    """
    hex_result = _rpc_result(envelope, "eth_call")
    if hex_result is None:
        return None
    try:
        raw_uint = int(hex_result, 16)
    except (ValueError, TypeError):
        return None

    supply = raw_uint / 10 ** decimals
    return ExtractedValue(
        metric="total_supply",
        value=supply,
        unit="tokens",  # token-denominated; subject identifies which token
        source=SOURCE,
        subject=envelope.get("subject"),
        as_of=envelope.get("fetched_at"),
        provenance={
            "rpc_method": "eth_call",
            "raw_hex": hex_result,
            "raw_uint256": raw_uint,
            "decimals": decimals,
        },
    )


def is_contract(envelope: Mapping[str, Any]) -> Optional[bool]:
    """True if ``eth_getCode`` returned bytecode (a deployed contract).

    An EOA returns ``"0x"`` (length 2); a contract returns long bytecode.
    Returns None (rule 1) when ``eth_getCode`` is absent — None means "unknown",
    which is honest; False would falsely assert "not a contract".
    """
    code = _rpc_result(envelope, "eth_getCode")
    if code is None:
        return None
    return len(code) > 2
