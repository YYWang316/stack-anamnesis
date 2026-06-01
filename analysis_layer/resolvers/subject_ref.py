"""subject_ref resolver (TD-030) — canonical subject -> out-of-envelope bindings.

The extractors take certain values as manual args because no envelope carries
them: Alchemy/Etherscan supply decodes need ``decimals``; CMC keys its data by a
numeric id; each source addresses the same subject by its OWN id (CoinGecko
slug, CMC id, DefiLlama stablecoin id); on-chain reads need a contract address +
chain; SEC reads need a CIK. ``resolve_subject`` maps a canonical name to all of
those, so callers stop hard-coding them.

This is the FIRST resolver in the analysis-layer trunk
(extractor -> resolver -> aggregator -> filler). It mirrors the extractors'
discipline:

* PURE — an in-module registry lookup. No I/O, no network (rule 3).
* NEVER throws — an unknown subject returns ``None`` (rule 1), the same uniform
  "no data" signal the extractors use.

OUT OF SCOPE (deliberately not built here, TD-030): the "PayPal -> PYPL vs
PYUSD" disambiguation and the front-door subject-confirm gate. subject_ref is
only the lookup; ambiguity handling lands later with the gate.

----------------------------------------------------------------------------
How the registry was grounded (TD-023: verify reality)
----------------------------------------------------------------------------
Every USDC binding below was harvested from the real envelopes on disk under
``meta/raw/<source>/`` — each envelope's ``endpoint`` (or ``subject`` /
``companyfacts.cik``) encodes the id that source actually used. Nothing here is
guessed; the test module cross-checks each binding against the envelope it came
from:

    decimals      6        etherscan tokensupply 52708308943858656 / 1e6 ~= $52.7B
                           (and Alchemy eth_call decodes to ~$52.6B) — Ethereum-only
    eth_contract  0xA0b8…  alchemy & etherscan envelope ``subject`` (the 0x form)
    eth_chain     ethereum etherscan endpoint ``?chainid=1``
    coingecko     usd-coin coingecko endpoint ``/coins/usd-coin``
    coinmarketcap 3408     cmc endpoint ``?id=3408`` (the data dict's key)
    defillama     2        defillama endpoint ``?stablecoin=2``
    sec_cik       0001876042  sec_edgar ``companyfacts.cik`` (Circle)
"""
from __future__ import annotations

from typing import Dict, Optional

from analysis_layer.contract import SubjectRef

# --------------------------------------------------------------------------- #
# Registry — adding a subject is a DATA edit (a new entry), not a code change.
# Keyed by lowercased canonical name; values are the SubjectRef fields. Start
# with USDC ONLY, populated from the verified real envelopes (see module
# docstring / TD-023).
# --------------------------------------------------------------------------- #
_REGISTRY: Dict[str, SubjectRef] = {
    "usdc": SubjectRef(
        subject="USDC",
        subject_type="stablecoin",
        decimals=6,
        issuer="Circle",
        identifiers={
            # per-source ids (the same id each source's endpoint used)
            "coingecko": "usd-coin",          # /coins/usd-coin
            "coinmarketcap": "3408",          # ?id=3408
            "defillama": "2",                 # ?stablecoin=2
            # on-chain: the canonical Ethereum-mainnet USDC contract + chain
            "eth_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "eth_chain": "ethereum",          # etherscan ?chainid=1
            # regulatory: Circle's zero-padded-10 CIK
            "sec_cik": "0001876042",
        },
    ),
}


def resolve_subject(name: str) -> Optional[SubjectRef]:
    """Resolve a canonical subject name to its ``SubjectRef``, or ``None``.

    Case-insensitive (``"usdc"``, ``"USDC"``, ``"Usdc"`` all resolve). An
    unknown subject returns ``None`` — never throws (rule 1). Pure lookup: no
    I/O, no network (rule 3).
    """
    if not isinstance(name, str):
        return None
    return _REGISTRY.get(name.strip().lower())
