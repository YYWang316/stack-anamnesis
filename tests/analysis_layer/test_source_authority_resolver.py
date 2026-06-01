"""Unit tests for analysis_layer/resolvers/source_authority.py (B.2.6b, TD-031).

source_authority is the second resolver in the analysis-layer trunk (extractor
-> resolver -> aggregator -> filler). It answers, per metric, which source is
authoritative (``primary``) and in what order to cross-check it
(``cross_checks``). It is a LOOKUP only — no reconciliation (that is the B.2.7
aggregator).

Coverage:
* the known rankings resolve correctly (price/market_cap/volume_24h ->
  CoinGecko primary + CMC cross-check; the supply SCOPE SPLIT; TVL -> DefiLlama);
* the scope rule is enforced — ``total_supply`` requires a scope and is never
  collapsed into one ranking;
* unknown metric -> None, no throw;
* ★ every slug the resolver returns matches an extractor ``SOURCE`` constant
  exactly, so the aggregator joins authority to ``ExtractedValue.source`` with
  no translation.
"""
from __future__ import annotations

import pytest

from analysis_layer.contract import MetricAuthority
from analysis_layer.resolvers import source_authority
from analysis_layer.resolvers.source_authority import authority_for

# The extractors' real SOURCE constants — the join keys the aggregator uses.
# (Read-only import; the test grounds the resolver's slugs against these.)
from analysis_layer.extractors import (
    alchemy,
    coingecko,
    coinmarketcap,
    defillama,
    etherscan,
    sec_edgar,
)

EXTRACTOR_SOURCES = {
    alchemy.SOURCE,
    coingecko.SOURCE,
    coinmarketcap.SOURCE,
    defillama.SOURCE,
    etherscan.SOURCE,
    sec_edgar.SOURCE,
}


# --------------------------------------------------------------------------- #
# market-data metrics: CoinGecko primary, CMC cross-check
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("metric", ["price", "market_cap", "volume_24h"])
def test_market_data_metrics_coingecko_primary_cmc_crosscheck(metric):
    auth = authority_for(metric)
    assert isinstance(auth, MetricAuthority)
    assert auth.metric == metric
    assert auth.primary == "coingecko"
    assert auth.cross_checks == ("coinmarketcap",)
    assert auth.scope is None


def test_market_cap_rank_is_sole_source():
    auth = authority_for("market_cap_rank")
    assert auth.primary == "coingecko"
    assert auth.cross_checks == ()


# --------------------------------------------------------------------------- #
# ★ supply SCOPE SPLIT — single-chain on-chain truth vs multi-chain aggregate
# --------------------------------------------------------------------------- #
def test_total_supply_single_chain_is_onchain_truth():
    auth = authority_for("total_supply", scope="single-chain")
    assert auth.primary == "alchemy"          # direct eth_call read
    assert auth.cross_checks == ("etherscan",)  # explorer tokensupply
    assert auth.scope == "single-chain"


def test_total_supply_multi_chain_is_aggregator():
    auth = authority_for("total_supply", scope="multi_chain")
    assert auth.primary == "coingecko"
    assert auth.cross_checks == ("coinmarketcap",)
    assert auth.scope == "multi_chain"


def test_single_and_multi_chain_supply_are_different_authorities():
    single = authority_for("total_supply", scope="single-chain")
    multi = authority_for("total_supply", scope="multi_chain")
    assert single != multi
    assert single.primary != multi.primary


def test_total_supply_without_scope_is_not_collapsed():
    # README scope rule: a scoped metric must be asked within a scope; the
    # resolver refuses to collapse the two into one ranking.
    assert authority_for("total_supply") is None


def test_circulating_supply_multi_chain_defillama_primary():
    auth = authority_for("circulating_supply", scope="multi_chain")
    assert auth.primary == "defillama"          # stablecoin specialist (§1)
    assert auth.cross_checks == ("coinmarketcap",)
    assert auth.scope == "multi_chain"


# --------------------------------------------------------------------------- #
# TVL + single-source financial concepts
# --------------------------------------------------------------------------- #
def test_tvl_defillama_primary():
    auth = authority_for("tvl")
    assert auth.primary == "defillama"
    assert auth.cross_checks == ()


@pytest.mark.parametrize("concept", ["revenue", "assets"])
def test_sec_financial_concepts_sole_source(concept):
    auth = authority_for(concept)
    assert auth.primary == "sec_edgar"
    assert auth.cross_checks == ()


# --------------------------------------------------------------------------- #
# behaviour: case-insensitive, scope fallback, unknown -> None
# --------------------------------------------------------------------------- #
def test_lookup_is_case_insensitive():
    assert authority_for("PRICE") == authority_for("price")
    assert authority_for("Total_Supply", scope="multi_chain") == authority_for(
        "total_supply", scope="multi_chain"
    )


def test_scope_agnostic_metric_ignores_irrelevant_scope():
    # price has no scope split -> an irrelevant scope falls back to the (None) entry.
    assert authority_for("price", scope="single-chain") == authority_for("price")


def test_unknown_metric_returns_none_no_throw():
    assert authority_for("not_a_metric") is None
    assert authority_for("") is None
    assert authority_for(None) is None  # type: ignore[arg-type]
    # a known metric under an unknown scope (with no scope-agnostic entry) -> None
    assert authority_for("total_supply", scope="layer2") is None


# --------------------------------------------------------------------------- #
# ★ slugs must match the extractors' SOURCE constants exactly (no translation)
# --------------------------------------------------------------------------- #
def test_all_authority_slugs_are_real_extractor_sources():
    for auth in source_authority._AUTHORITY.values():
        assert auth.primary in EXTRACTOR_SOURCES, auth
        for cc in auth.cross_checks:
            assert cc in EXTRACTOR_SOURCES, auth
