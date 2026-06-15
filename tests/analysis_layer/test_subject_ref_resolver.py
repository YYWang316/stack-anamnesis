"""Unit + real-envelope cross-check tests for
analysis_layer/resolvers/subject_ref.py (B.2.6a, TD-030).

subject_ref is the first resolver in the analysis-layer trunk (extractor ->
resolver -> aggregator -> filler). It maps a canonical subject to the
out-of-envelope bindings the extractors take as manual args — decimals,
per-source ids, on-chain contract, issuer CIK.

Two layers of test:

1. Contract behaviour — case-insensitive lookup, unknown -> None (no throw),
   the resolved USDC bindings are the expected values.
2. ★ Grounding cross-check (TD-023) — each binding is asserted to MATCH what
   the corresponding REAL envelope on disk actually used (its ``endpoint`` /
   ``subject`` / ``companyfacts.cik``). This is what keeps the in-module
   registry honest: it cannot drift from the ids the fetchers really called.
   Each cross-check globs the newest envelope and SKIPS (not fails) if none is
   on disk, mirroring the extractor real-tests.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from analysis_layer.contract import SubjectRef
from analysis_layer.resolvers import subject_ref

ROOT = Path(__file__).resolve().parents[2]
# Canonical sibling convention (cf. the extractor real-tests). In some worktrees
# the shared raw store is reached through a nested ``raw`` symlink
# (meta/raw/raw/<source>/), so each lookup probes both bases.
RAW = ROOT / "meta" / "raw"
RAW_NESTED = ROOT / "meta" / "raw" / "raw"


def _newest_envelope(source: str, pattern: str) -> dict:
    """Newest ``<pattern>`` envelope for ``source`` on disk, or skip if none."""
    for base in (RAW / source, RAW_NESTED / source):
        if not base.exists():
            continue
        candidates = sorted(base.glob(pattern), reverse=True)
        if candidates:
            return json.loads(candidates[0].read_text())
    pytest.skip(f"no real {source} envelope ({pattern}) found on disk")


# --------------------------------------------------------------------------- #
# contract behaviour
# --------------------------------------------------------------------------- #
def test_resolve_usdc_returns_subject_ref_with_expected_bindings():
    ref = subject_ref.resolve_subject("USDC")
    assert isinstance(ref, SubjectRef)
    assert ref.subject == "USDC"
    assert ref.subject_type == "stablecoin"
    assert ref.decimals == 6
    assert ref.issuer == "Circle"
    ids = ref.identifiers
    assert ids["coingecko"] == "usd-coin"
    assert ids["coinmarketcap"] == "3408"
    assert ids["defillama"] == "2"
    assert ids["eth_contract"] == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    assert ids["eth_chain"] == "ethereum"
    assert ids["sec_cik"] == "0001876042"


def test_resolve_usdt_second_binding_no_sec_cik():
    """USDT is bound DATA-ONLY (TD-046) — same stablecoin path as USDC, but with NO
    sec_cik (Tether is not SEC-registered), so the issuer-financials source is
    optional, not assumed."""
    ref = subject_ref.resolve_subject("USDT")
    assert isinstance(ref, SubjectRef)
    assert ref.subject == "USDT"
    assert ref.subject_type == "stablecoin"
    assert ref.decimals == 6
    assert ref.issuer == "Tether"
    ids = ref.identifiers
    assert ids["coingecko"] == "tether"
    assert ids["eth_contract"] == "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    assert ids["eth_chain"] == "ethereum"
    assert "sec_cik" not in ids   # deliberately absent → SEC skipped end-to-end


def test_resolve_eth_first_cross_type_l1_no_contract_no_issuer():
    """ETH is the FIRST non-stablecoin binding (TD-046) — subject_type ``l1`` (→
    playbook class B), a NATIVE coin so NO eth_contract (on-chain sources skip), NO
    issuer / sec_cik (SEC skips). Proves the registry holds a cross-type subject."""
    ref = subject_ref.resolve_subject("ETH")
    assert isinstance(ref, SubjectRef)
    assert ref.subject == "ETH"
    assert ref.subject_type == "l1"        # NOT stablecoin → class B, not A
    assert ref.decimals == 18
    assert ref.issuer is None
    ids = ref.identifiers
    assert ids["coingecko"] == "ethereum"
    assert ids["coinmarketcap"] == "1027"
    assert "eth_contract" not in ids       # native → contract-keyed sources skip
    assert "sec_cik" not in ids            # no issuer → SEC skips


def test_lookup_is_case_insensitive():
    ref = subject_ref.resolve_subject("USDC")
    assert subject_ref.resolve_subject("usdc") == ref
    assert subject_ref.resolve_subject("Usdc") == ref
    assert subject_ref.resolve_subject("  usdc  ") == ref


def test_unknown_subject_returns_none_no_throw():
    assert subject_ref.resolve_subject("NOPECOIN") is None
    assert subject_ref.resolve_subject("") is None
    # non-str must not throw either (rule 1).
    assert subject_ref.resolve_subject(None) is None  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# ★ grounding cross-checks — each binding vs the real envelope that used it
# --------------------------------------------------------------------------- #
def test_coingecko_slug_matches_real_envelope():
    env = _newest_envelope("coingecko", "usdc_*.json")
    # endpoint: .../coins/usd-coin -> the slug is the last path segment.
    slug = env["endpoint"].rstrip("/").rsplit("/", 1)[-1]
    assert slug == subject_ref.resolve_subject("USDC").identifiers["coingecko"]


def test_coinmarketcap_id_matches_real_envelope():
    env = _newest_envelope("coinmarketcap", "usdc_*.json")
    m = re.search(r"[?&]id=(\d+)", env["endpoint"])
    assert m is not None, "CMC envelope endpoint should carry ?id="
    assert m.group(1) == subject_ref.resolve_subject("USDC").identifiers["coinmarketcap"]


def test_defillama_id_matches_real_envelope():
    env = _newest_envelope("defillama", "usdc_*.json")
    m = re.search(r"[?&]stablecoin=(\d+)", env["endpoint"])
    assert m is not None, "DefiLlama envelope endpoint should carry ?stablecoin="
    assert m.group(1) == subject_ref.resolve_subject("USDC").identifiers["defillama"]


def test_eth_contract_and_chain_match_real_envelopes():
    ids = subject_ref.resolve_subject("USDC").identifiers
    # On-chain contract: the Alchemy / Etherscan 0x-form envelope ``subject`` is
    # the contract address. Glob USDC's OWN contract (a shared raw dir may hold a
    # second subject's 0x… envelopes, e.g. USDT). Compare case-insensitively.
    c = ids["eth_contract"].lower()
    onchain = _newest_envelope("alchemy", f"*{c}*.json")
    assert onchain["subject"].lower() == ids["eth_contract"].lower()
    # Chain: the Etherscan endpoint carries ?chainid=1 == Ethereum mainnet.
    es = _newest_envelope("etherscan", f"*{c}*.json")
    m = re.search(r"[?&]chainid=(\d+)", es["endpoint"])
    assert m is not None and m.group(1) == "1"  # chainid 1 == ids["eth_chain"]
    assert ids["eth_chain"] == "ethereum"


def test_decimals_consistent_with_real_onchain_supply():
    """decimals=6 must decode the real Etherscan tokensupply to a sane USDC
    Ethereum-only magnitude — the cross-check that grounds the decimals binding
    against an actual on-chain read rather than a guess."""
    decimals = subject_ref.resolve_subject("USDC").decimals
    env = _newest_envelope("etherscan", "usdc_*.json")
    raw = env["raw_response"]["tokensupply"]["result"]
    supply = int(raw) / 10 ** decimals
    # Ethereum-only USDC supply is tens of billions (~$52B at envelope time);
    # any wrong ``decimals`` (e.g. 18) would land orders of magnitude off-band.
    assert 1e10 < supply < 1e11


def test_sec_cik_matches_real_envelope():
    env = _newest_envelope("sec_edgar", "circle_*.json")
    cik = env["raw_response"]["companyfacts"]["cik"]
    assert cik == subject_ref.resolve_subject("USDC").identifiers["sec_cik"]
