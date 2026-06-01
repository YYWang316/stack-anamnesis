"""source_authority resolver (TD-031) — per-metric source authority lookup.

Second resolver in the analysis-layer trunk
(extractor -> resolver -> aggregator -> filler). When several sources report the
SAME metric, the B.2.7 aggregator needs to know which source is authoritative
and in what order to cross-check it. ``authority_for`` answers exactly that and
NOTHING more:

* It is a LOOKUP, not a reconciler. It does not compare values, apply tolerance
  bands, or flag divergence — that is the aggregator (OUT OF SCOPE here).
* It is PURE — an in-module table lookup, no I/O, no network (rule 3).
* Unknown (metric, scope) -> ``None``, never throws (rule 1), mirroring the
  sibling ``subject_ref`` resolver.

The rankings are DERIVED from ground truth, not invented:

  references/data_source_registry.md and analysis_layer/README.md
  "Source authority":
    * CoinGecko = primary price / market cap; CMC = cross-check (registry §4/§13,
      README).
    * On-chain (Alchemy / Etherscan) = supply truth for a SINGLE chain
      (README; registry §5 "Prefer Alchemy as default", and an ``eth_call
      totalSupply`` is the direct contract-state read — registry §5 calls it the
      way to ground-truth the issuer's own numbers — so Alchemy leads, Etherscan
      (explorer-indexed ``tokensupply``) corroborates).
    * DefiLlama = primary TVL, and the specialist for stablecoin circulating
      supply (registry §1 ``/stablecoins``); CMC cross-checks.
    * SEC EDGAR = sole source for XBRL financial concepts (registry §6).

----------------------------------------------------------------------------
★ SCOPE SPLIT (README scope rule) — do NOT collapse
----------------------------------------------------------------------------
A single-chain on-chain supply (~$52.6B USDC on Ethereum) and a multi-chain
aggregate supply (~$76.4B across all chains) are DIFFERENT metrics and must
never be reconciled across scopes. ``total_supply`` therefore carries TWO
authorities keyed by ``scope`` — ``"single-chain"`` (on-chain truth: Alchemy
primary, Etherscan cross-check) and ``"multi_chain"`` (aggregate: CoinGecko
primary, CMC cross-check). The ``scope`` strings match the extractors'
``provenance["scope"]`` tags EXACTLY (``"single-chain"`` hyphen,
``"multi_chain"`` underscore) so the aggregator joins with no translation.

Calling ``authority_for("total_supply")`` WITHOUT a scope returns ``None`` on
purpose: a scoped metric must be asked about within a scope, never collapsed.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from analysis_layer.contract import MetricAuthority

# Source slugs — kept identical to each extractor's ``SOURCE`` constant so the
# aggregator joins authority to ``ExtractedValue.source`` without translation.
_COINGECKO = "coingecko"
_COINMARKETCAP = "coinmarketcap"
_ALCHEMY = "alchemy"
_ETHERSCAN = "etherscan"
_DEFILLAMA = "defillama"
_SEC_EDGAR = "sec_edgar"

# Scope strings — must match the extractors' ``provenance["scope"]`` verbatim.
_SINGLE_CHAIN = "single-chain"
_MULTI_CHAIN = "multi_chain"


def _entry(
    metric: str,
    primary: str,
    *,
    scope: Optional[str] = None,
    cross_checks: Tuple[str, ...] = (),
) -> MetricAuthority:
    return MetricAuthority(
        metric=metric, primary=primary, scope=scope, cross_checks=cross_checks
    )


# Authority table, keyed by (metric_lower, scope). Adding/changing a ranking is
# a DATA edit here. Each entry's derivation is cited in the comment.
_AUTHORITY: Dict[Tuple[str, Optional[str]], MetricAuthority] = {
    # --- market data: CoinGecko primary, CMC cross-check (README; §4/§13) ---
    ("price", None): _entry("price", _COINGECKO, cross_checks=(_COINMARKETCAP,)),
    ("market_cap", None): _entry("market_cap", _COINGECKO, cross_checks=(_COINMARKETCAP,)),
    # CMC reports 24h volume too (registry §13) — it is the cross-check source
    # even though the current CMC extractor doesn't yet emit volume_24h.
    ("volume_24h", None): _entry("volume_24h", _COINGECKO, cross_checks=(_COINMARKETCAP,)),
    # market_cap_rank: only CoinGecko emits it -> sole source, no cross-check.
    ("market_cap_rank", None): _entry("market_cap_rank", _COINGECKO),

    # --- supply: SCOPE SPLIT (★) — never collapse the two scopes ---
    # single-chain on-chain read: Alchemy (direct eth_call) primary, Etherscan
    # (explorer tokensupply) cross-check (README on-chain = supply truth; §5).
    ("total_supply", _SINGLE_CHAIN): _entry(
        "total_supply", _ALCHEMY, scope=_SINGLE_CHAIN, cross_checks=(_ETHERSCAN,)
    ),
    # multi-chain aggregate total_supply: CoinGecko primary, CMC cross-check
    # (DefiLlama emits circulating_supply, not total_supply — see below).
    ("total_supply", _MULTI_CHAIN): _entry(
        "total_supply", _COINGECKO, scope=_MULTI_CHAIN, cross_checks=(_COINMARKETCAP,)
    ),
    # multi-chain circulating supply of a stablecoin: DefiLlama's stablecoin
    # module is the specialist (registry §1 /stablecoins), CMC cross-checks (§13).
    ("circulating_supply", _MULTI_CHAIN): _entry(
        "circulating_supply", _DEFILLAMA, scope=_MULTI_CHAIN, cross_checks=(_COINMARKETCAP,)
    ),

    # --- TVL: DefiLlama primary (README "DefiLlama = primary TVL"; §1) ---
    # No extractor emits a "tvl" metric yet (the DefiLlama extractor currently
    # does the stablecoin-supply path); the authority is the documented one.
    ("tvl", None): _entry("tvl", _DEFILLAMA),

    # --- SEC EDGAR XBRL financial concepts: sole source (registry §6) ---
    # The extractor keys metric on the requested concept name; "revenue"/"assets"
    # are the representative single-source entries the mandate names.
    ("revenue", None): _entry("revenue", _SEC_EDGAR),
    ("assets", None): _entry("assets", _SEC_EDGAR),
}


def authority_for(metric: str, scope: Optional[str] = None) -> Optional[MetricAuthority]:
    """Return the ``MetricAuthority`` for ``metric`` (within ``scope``), or None.

    Resolution:
      * exact ``(metric, scope)`` match first;
      * if absent and ``scope`` was given, fall back to the scope-agnostic
        ``(metric, None)`` entry — a metric with no scope split (price, …)
        answers regardless of an irrelevant scope.

    A SCOPED metric (``total_supply``) has NO ``(metric, None)`` entry by design,
    so ``authority_for("total_supply")`` returns ``None``: the README scope rule
    forbids collapsing single-chain and multi-chain supply into one ranking —
    the caller must ask within a scope. Unknown metric -> ``None`` (rule 1).
    """
    if not isinstance(metric, str):
        return None
    key = metric.strip().lower()
    hit = _AUTHORITY.get((key, scope))
    if hit is not None:
        return hit
    if scope is not None:
        return _AUTHORITY.get((key, None))
    return None
