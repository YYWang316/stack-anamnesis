"""Extractor for Etherscan V2 envelopes (tools/fetchers/etherscan_fetch.py).

Envelope shape (per the fetcher's output contract; the fetcher docstring is the
source of truth — no envelope was on disk at build time, see test module's
TD-023 note):

    {
      "subject": "USDC",
      "subject_type": "stablecoin",
      "freshness_window": "30d",
      "endpoint": "https://api.etherscan.io/v2/api?chainid=1",  # apikey stripped
      "fetched_at": "2026-05-27T15:23:26.998418+00:00",
      "raw_response": {
        "tokensupply": {"status": "1", "message": "OK", "result": "52570..."},
        "tokeninfo":   null | {...},        # free-tier Pro endpoint -> soft null
        "tokentx":     {"status": "1", "message": "OK", "result": [ ... ]}
      }
    }

Contrast with Alchemy (analysis_layer/extractors/alchemy.py): the supply here is
a DECIMAL STRING in token base units (``int(result)``), NOT a hex string
(``int(result, 16)``). Decimal scaling is otherwise identical: divide by
``10 ** decimals``.

All functions are pure (rule 3): envelope in, typed value out, no I/O. Every hop
is null-guarded (rule 1): a missing ``tokensupply`` / ``result`` returns None,
never throws.

----------------------------------------------------------------------------
Scope: Etherscan reads are SINGLE-CHAIN (one chainid per envelope)
----------------------------------------------------------------------------
The supply value reflects exactly one EVM chain (Ethereum mainnet = chainid 1
for the USDC contract). We tag the chain into ``provenance`` so the aggregator
keeps this reading in the *single-chain* scope bucket and never reconciles it
against a *multi-chain aggregator total* (CoinGecko / CMC / DefiLlama), which is
a different metric (README "Scope rule": Ethereum-only ~$52.6B vs cross-chain
~$76.4B are not comparable). Because ``metric`` is the SAME canonical
``"total_supply"`` as Alchemy emits, the aggregator CAN reconcile this against
the Alchemy on-chain read — the two single-chain Ethereum readings of the same
contract are the intended cross-check.

----------------------------------------------------------------------------
Transfer aggregation is DEFERRED to a fetcher fix
----------------------------------------------------------------------------
``aggregate_transfers`` is a documented stub returning None. The current
envelope's ``tokentx`` carries only a SINGLE page (offset=100, sort=desc) of
recent transfers — that is a fetcher limitation, NOT a 30d window. Computing a
"30d transfer volume / count" from one page would silently fabricate an
aggregate that under-counts by orders of magnitude. The real fix belongs in the
fetcher (paginate-by-window: walk pages until the 30d boundary, or use a
block-range query), after which a faithful aggregator can be written here.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from analysis_layer.contract import ExtractedValue

SOURCE = "etherscan"

# Known EVM chainids the fetcher supports (etherscan_fetch.CHAIN_IDS) -> human
# chain name for the scope tag. The fetcher is multi-chain capable, so we read
# the ACTUAL chainid from the envelope's endpoint rather than hard-coding
# "ethereum": a chain-137 USDC envelope must NOT be mislabelled. For the B.1.3
# USDC / chainid=1 envelope this resolves to "ethereum" as expected.
_CHAIN_NAMES = {
    1: "ethereum",
    137: "polygon",
    56: "bnb-smart-chain",
    42161: "arbitrum-one",
    10: "optimism",
    8453: "base",
}


def _chain_scope(envelope: Mapping[str, Any]) -> tuple[Optional[int], str]:
    """Parse the chainid from the envelope's ``endpoint`` -> (chainid, name).

    The persisted endpoint looks like ``...?chainid=1`` (apikey stripped). Falls
    back to ``(None, "unknown")`` if absent/unparsable, and to ``chainid:<n>``
    for a chainid not in the known map. Never throws.
    """
    endpoint = envelope.get("endpoint")
    if not isinstance(endpoint, str):
        return None, "unknown"
    m = re.search(r"chainid=(\d+)", endpoint)
    if m is None:
        return None, "unknown"
    chainid = int(m.group(1))
    return chainid, _CHAIN_NAMES.get(chainid, f"chainid:{chainid}")


def _tokensupply_result(envelope: Mapping[str, Any]) -> Optional[Any]:
    """Return ``raw_response.tokensupply.result`` or None if any hop is missing.

    Defensive at every level (rule 1): envelope, raw_response, the tokensupply
    block, and the result key can each be absent or non-Mapping in a real
    envelope (e.g. an error response where ``result`` is missing).
    """
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return None
    block = raw.get("tokensupply")
    if not isinstance(block, Mapping):
        return None
    return block.get("result")


def extract_supply(
    envelope: Mapping[str, Any], decimals: int
) -> Optional[ExtractedValue]:
    """Decode Etherscan ``tokensupply`` into a human-scale total supply.

    ``decimals`` is passed IN, not read from the envelope: the Etherscan
    envelope does not carry the token's decimals (USDC = 6). This is the
    subject_ref dependency — same contract as Alchemy
    (``decode_total_supply``) — that the future subject_ref resolver
    (subject -> decimals) will satisfy. Until then the caller supplies it.

    Returns None (rule 1) if ``tokensupply`` / ``result`` is absent, or if the
    result is not a parseable decimal integer string.
    """
    result = _tokensupply_result(envelope)
    if result is None:
        return None
    try:
        # Decimal string of base units (e.g. "52570793270161"), NOT hex —
        # contrast Alchemy's int(hex, 16). int() also tolerates a raw int.
        raw_uint = int(result)
    except (ValueError, TypeError):
        return None

    supply = raw_uint / 10 ** decimals
    chainid, chain = _chain_scope(envelope)
    return ExtractedValue(
        metric="total_supply",  # SAME canonical name as alchemy -> reconcilable
        value=supply,
        unit="tokens",  # token-denominated; subject identifies which token
        source=SOURCE,
        subject=envelope.get("subject"),
        as_of=envelope.get("fetched_at"),
        provenance={
            "endpoint_action": "stats/tokensupply",
            "raw_result": str(result),
            "raw_uint256": raw_uint,
            "decimals": decimals,
            # single-chain scope tag (see module docstring): keeps this reading
            # out of the multi-chain-aggregator-total bucket.
            "chain": chain,
            "chainid": chainid,
            "scope": "single-chain",
        },
    )


def aggregate_transfers(envelope: Mapping[str, Any]) -> None:
    """DEFERRED stub — always returns None. See module docstring.

    The envelope's ``tokentx`` holds only ONE page (~100) of recent transfers,
    not a freshness-window-bounded set, so no faithful 30d aggregate can be
    derived here. The fix is a fetcher change (paginate-by-window); a real
    aggregator lands afterwards. Returning None keeps the "no data" contract
    (rule 1) honest rather than fabricating an under-counted total.
    """
    return None
