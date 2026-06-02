"""Unit + real-data tests for analysis_layer/aggregators/reconcile.py (B.2.7).

The aggregator is the reconciliation / credibility layer. Its cardinal rule: the
reported value is ALWAYS a real source's actual number (the authority's), never
an average; cross-source agreement is a confidence SIGNAL only.

Two layers:
1. Unit tests on inline ExtractedValues — grouping by (metric, scope) without
   crossing scopes, value == primary's number (NOT averaged), fallback, agree /
   divergence / single_source, and the ★ as_of-gap drift widening.
2. ★ Real-data test — run the pure extractors over whatever USDC envelopes are on
   disk, feed real ExtractedValues to reconcile(), assert STRUCTURE, and REPORT
   the actual numbers (freshness varies, so no hardcoded figures/agreement).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue, ReconciledValue
from analysis_layer.aggregators import reconcile as agg
from analysis_layer.aggregators.reconcile import reconcile

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "meta" / "raw"
RAW_NESTED = ROOT / "meta" / "raw" / "raw"


# --------------------------------------------------------------------------- #
# inline ExtractedValue builders
# --------------------------------------------------------------------------- #
def _ev(metric, value, source, *, unit="USD", scope=None, as_of=None):
    prov = {} if scope is None else {"scope": scope}
    return ExtractedValue(metric=metric, value=value, unit=unit, source=source,
                          subject="USDC", as_of=as_of, provenance=prov)


def _by_key(rvs):
    return {(r.metric, r.scope): r for r in rvs}


# --------------------------------------------------------------------------- #
# grouping + scope rule
# --------------------------------------------------------------------------- #
def test_groups_by_metric_and_scope_never_crossing():
    # same metric, two scopes -> two distinct ReconciledValues, never merged.
    vals = [
        _ev("total_supply", 52.6e9, "alchemy", unit="tokens"),           # scope inferred -> single-chain
        _ev("total_supply", 52.7e9, "etherscan", unit="tokens", scope="single-chain"),
        _ev("total_supply", 76.4e9, "coingecko", unit="tokens", scope="multi_chain"),
        _ev("total_supply", 76.39e9, "coinmarketcap", unit="tokens", scope="multi_chain"),
    ]
    out = _by_key(reconcile(vals))
    assert ("total_supply", "single-chain") in out
    assert ("total_supply", "multi_chain") in out
    # the two groups are independent facts
    sc = out[("total_supply", "single-chain")]
    mc = out[("total_supply", "multi_chain")]
    assert sc.value != mc.value
    assert sc.source_used == "alchemy"        # single-chain primary
    assert mc.source_used == "coingecko"      # multi-chain primary
    # inputs never leak across scopes
    assert all(_scope_in(i) in (None, "single-chain") for i in sc.inputs)
    assert all(i.provenance.get("scope") == "multi_chain" for i in mc.inputs)


def _scope_in(ev):
    return ev.provenance.get("scope")


def test_alchemy_total_supply_scope_inferred_groups_with_etherscan():
    # Alchemy emits no scope tag; it must still land in the single-chain group.
    vals = [
        _ev("total_supply", 52.6e9, "alchemy", unit="tokens"),  # no scope in provenance
        _ev("total_supply", 52.7e9, "etherscan", unit="tokens", scope="single-chain"),
    ]
    out = reconcile(vals)
    assert len(out) == 1
    assert out[0].scope == "single-chain"
    assert {i.source for i in out[0].inputs} == {"alchemy", "etherscan"}


# --------------------------------------------------------------------------- #
# value = primary's actual number, NOT an average
# --------------------------------------------------------------------------- #
def test_value_is_primary_number_not_average():
    vals = [
        _ev("price", 1.0000, "coingecko"),
        _ev("price", 0.9900, "coinmarketcap"),
    ]
    out = reconcile(vals)[0]
    assert out.source_used == "coingecko"
    assert out.value == 1.0000              # the primary's number
    assert out.value != pytest.approx(0.995)  # NOT the average of the two
    # the cross-check's number is recorded, not blended in
    assert out.audit["median"] == pytest.approx(0.995)  # median RECORDED only


def test_fallback_when_primary_absent():
    # CoinGecko (primary for price) absent -> fall back to CMC cross-check.
    vals = [_ev("price", 0.9993, "coinmarketcap")]
    out = reconcile(vals)[0]
    assert out.source_used == "coinmarketcap"
    assert out.value == 0.9993
    assert out.audit["fallback"] is True
    assert out.agreement == "single_source"  # nothing left to cross-check


# --------------------------------------------------------------------------- #
# agreement labels
# --------------------------------------------------------------------------- #
def test_agree_within_band():
    # delta 0.2% < general currency band 0.5% -> agree.
    vals = [_ev("price", 1.000, "coingecko"), _ev("price", 1.002, "coinmarketcap")]
    out = reconcile(vals)[0]
    assert out.agreement == "agree"
    assert out.audit["cross_checks"][0]["within_band"] is True


def test_divergence_flagged_but_value_unchanged():
    # delta 10% > 0.5% -> divergence, but value still the authority's number.
    vals = [_ev("price", 1.00, "coingecko"), _ev("price", 1.10, "coinmarketcap")]
    out = reconcile(vals)[0]
    assert out.agreement == "divergence"
    assert out.value == 1.00                       # NOT dropped, NOT blended
    assert out.source_used == "coingecko"
    assert out.audit["cross_checks"][0]["within_band"] is False


def test_single_source_when_no_crosscheck():
    out = reconcile([_ev("market_cap", 76.4e9, "coingecko")])[0]
    assert out.agreement == "single_source"
    assert out.audit["cross_checks"] == []


# --------------------------------------------------------------------------- #
# ★ as_of-gap drift widening (single-chain)
# --------------------------------------------------------------------------- #
def test_contemporaneous_single_chain_uses_tight_band():
    # ~0.26% delta with near-zero gap -> tight 0.05% band -> divergence.
    vals = [
        _ev("total_supply", 52.571e9, "alchemy", unit="tokens",
            as_of="2026-05-27T15:23:26+00:00"),
        _ev("total_supply", 52.708e9, "etherscan", unit="tokens", scope="single-chain",
            as_of="2026-05-27T15:40:00+00:00"),  # ~17 min apart
    ]
    out = reconcile(vals)[0]
    cc = out.audit["cross_checks"][0]
    assert cc["contemporaneous"] is True
    assert out.agreement == "divergence"           # 0.26% > tight 0.05%


def test_as_of_gap_widening_turns_divergence_into_agree():
    # SAME ~0.26% delta but reads ~1.86 days apart -> band widened by drift ->
    # agree (normal mint/burn, not a real divergence).
    vals = [
        _ev("total_supply", 52.571e9, "alchemy", unit="tokens",
            as_of="2026-05-27T15:23:26+00:00"),
        _ev("total_supply", 52.708e9, "etherscan", unit="tokens", scope="single-chain",
            as_of="2026-05-25T18:49:22+00:00"),
    ]
    out = reconcile(vals)[0]
    cc = out.audit["cross_checks"][0]
    assert cc["contemporaneous"] is False
    assert cc["gap_days"] == pytest.approx(1.86, abs=0.1)
    assert cc["band"] > agg.BAND_SINGLE_CHAIN_SUPPLY     # widened
    assert cc["within_band"] is True
    assert out.agreement == "agree"
    # value still the authority's actual number
    assert out.source_used == "alchemy"
    assert out.value == 52.571e9


def test_multi_chain_supply_uses_point_two_percent_band():
    # 0.1% delta -> within multi-chain 0.2% band -> agree; 0.3% -> divergence.
    near = reconcile([
        _ev("total_supply", 76.40e9, "coingecko", unit="tokens", scope="multi_chain"),
        _ev("total_supply", 76.40e9 * 1.001, "coinmarketcap", unit="tokens", scope="multi_chain"),
    ])[0]
    assert near.agreement == "agree"
    far = reconcile([
        _ev("total_supply", 76.40e9, "coingecko", unit="tokens", scope="multi_chain"),
        _ev("total_supply", 76.40e9 * 1.003, "coinmarketcap", unit="tokens", scope="multi_chain"),
    ])[0]
    assert far.agreement == "divergence"


# --------------------------------------------------------------------------- #
# ★ real-data test
# --------------------------------------------------------------------------- #
def _newest(source: str, pattern: str):
    for base in (RAW / source, RAW_NESTED / source):
        if not base.exists():
            continue
        cands = sorted(base.glob(pattern), reverse=True)
        for c in cands:
            yield json.loads(c.read_text())


def _first_extracted(source, pattern, fn):
    """Run extractor ``fn`` over newest->older envelopes; first non-empty result."""
    for env in _newest(source, pattern):
        res = fn(env)
        if res:
            return res
    return None


def test_real_usdc_reconciliation_structure_and_report(capsys):
    # import the pure extractors HERE (the test produces the inputs; the
    # aggregator never imports extractors).
    from analysis_layer.extractors import alchemy, etherscan, coingecko, coinmarketcap, defillama
    from analysis_layer.resolvers.subject_ref import resolve_subject

    decimals = resolve_subject("USDC").decimals  # 6, via the trunk's resolver

    inputs = []
    a = _first_extracted("alchemy", "*.json", lambda e: alchemy.decode_total_supply(e, decimals))
    if a:
        inputs.append(a)
    es = _first_extracted("etherscan", "*.json", lambda e: etherscan.extract_supply(e, decimals))
    if es:
        inputs.append(es)
    cg = _first_extracted("coingecko", "usdc_*.json", coingecko.extract_spot_metrics)
    if cg:
        inputs.extend(cg)
    cmc = _first_extracted("coinmarketcap", "usdc_*.json", coinmarketcap.extract_latest_quote)
    if cmc:
        inputs.extend(cmc)
    dl = _first_extracted("defillama", "usdc_*.json", lambda e: defillama.latest(e))
    if dl:
        inputs.append(dl)

    if not inputs:
        pytest.skip("no real USDC envelopes on disk")

    rvs = reconcile(inputs)
    by = _by_key(rvs)

    # ---- REPORT (shown with -s) ------------------------------------------- #
    lines = ["", "=== REAL USDC reconciliation ==="]
    for r in rvs:
        lines.append(
            f"{r.metric:<20} scope={str(r.scope):<13} value={r.value:<22} "
            f"src={r.source_used:<14} agree={r.agreement:<13} "
            f"spread={r.audit['spread']*100:.4f}%")
        for cc in r.audit["cross_checks"]:
            extra = ""
            if cc["gap_days"] is not None:
                extra = (f" gap={cc['gap_days']:.2f}d contemporaneous={cc['contemporaneous']}"
                         f" base_band={cc['base_band']*100:.4f}%")
            lines.append(
                f"    vs {cc['source']:<14} delta={cc['delta']*100:.4f}% "
                f"band={cc['band']*100:.4f}% within={cc['within_band']}{extra}")
    report = "\n".join(lines)
    print(report)

    # ---- STRUCTURE assertions (no hardcoded figures) ---------------------- #
    sc = by.get(("total_supply", "single-chain"))
    mc = by.get(("total_supply", "multi_chain"))

    if sc is not None:
        # single-chain Ethereum-only supply: tens of billions, value from the
        # authority's ACTUAL number (Alchemy primary when present).
        assert 40e9 < sc.value < 65e9
        expected_primary = "alchemy" if any(i.source == "alchemy" for i in sc.inputs) else "etherscan"
        assert sc.source_used == expected_primary
        primary_ev = next(i for i in sc.inputs if i.source == sc.source_used)
        assert sc.value == primary_ev.value          # not averaged
        # if both on-chain sources present, the as_of gap must be detected/widened
        if {"alchemy", "etherscan"} <= {i.source for i in sc.inputs}:
            cc = sc.audit["cross_checks"][0]
            assert cc["contemporaneous"] is False     # ~2 days apart
            assert cc["gap_days"] is not None and cc["gap_days"] > 0.04
            assert cc["band"] > agg.BAND_SINGLE_CHAIN_SUPPLY  # widened by drift

    if mc is not None:
        assert 65e9 < mc.value < 90e9
        assert mc.source_used == "coingecko"
        primary_ev = next(i for i in mc.inputs if i.source == "coingecko")
        assert mc.value == primary_ev.value

    # the two supply scopes must never have been merged
    if sc is not None and mc is not None:
        assert sc.value != mc.value
        assert sc.value < mc.value                    # Ethereum-only < cross-chain

    # circulating_supply: DefiLlama (primary) vs CMC within 0.2%? — report it.
    circ = by.get(("circulating_supply", "multi_chain"))
    if circ is not None:
        assert circ.source_used == "defillama"
        cmc_cc = [c for c in circ.audit["cross_checks"] if c["source"] == "coinmarketcap"]
        if cmc_cc:
            print(f"\ncirculating_supply DefiLlama-vs-CMC: delta={cmc_cc[0]['delta']*100:.4f}% "
                  f"band={cmc_cc[0]['band']*100:.4f}% agree={circ.agreement}")

    # make the report visible even on pass
    with capsys.disabled():
        print(report)
