"""Unit + real-data tests for analysis_layer/fillers/fill.py (B.2.8).

The filler is the FINAL stage of the analysis-layer trunk
(extractor -> resolver -> aggregator -> filler). Its cardinal rule: ONLY ``[AUTO]``
slots get auto-filled (with a real reconciled value); ``[SEMI-AUTO]`` / ``[MANUAL]``
stay flagged for a human; nothing is ever fabricated.

Two layers:
1. Unit tests on an inline template string + inline ReconciledValues — [AUTO]
   fills, the two supply scopes landing in DISTINCT slots (never merged), Evidence
   Table confidence mapping, SEMI/MANUAL staying flagged, an [AUTO] with no value
   staying flagged, and scope omitted on price.
2. ★ Real end-to-end — load the on-disk USDC envelopes, run the PURE extractors ->
   reconcile() -> fill() against the REAL v1.2 template, write the produced
   markdown to a gitignored path, and assert the real numbers land. glob+skip if
   no envelopes are present.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue, ReconciledValue, SubjectRef
from analysis_layer.fillers.fill import build_evidence_table, fill, render_value

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "meta" / "raw"
TEMPLATE = ROOT / "references" / "templates" / "crypto_research_v1.2.md"
OUT_DIR = ROOT / "meta" / "reports"


# --------------------------------------------------------------------------- #
# inline builders
# --------------------------------------------------------------------------- #
def _rv(metric, value, source, *, unit="USD", scope=None, agreement="single_source",
        as_of="2026-05-27T15:00:00+00:00", inputs=(), audit=None):
    return ReconciledValue(
        metric=metric, value=value, unit=unit, source_used=source, scope=scope,
        as_of=as_of, agreement=agreement, inputs=tuple(inputs),
        audit=audit if audit is not None else {"cross_checks": []},
    )


def _ev(metric, value, source, *, unit="USD", scope=None):
    prov = {"scope": scope} if scope else {}
    return ExtractedValue(metric=metric, value=value, unit=unit, source=source,
                          subject="USDC", as_of="2026-05-27T15:00:00+00:00", provenance=prov)


SREF = SubjectRef(
    subject="USDC", subject_type="stablecoin", decimals=6, issuer="Circle",
    identifiers={"coingecko": "usd-coin", "coinmarketcap": "3408",
                 "defillama": "2", "eth_contract": "0xA0b8", "sec_cik": "0001876042"},
)


# An inline template with DISTINCT per-scope supply slots + a price slot + SEMI /
# MANUAL slots + an [AUTO] slot we have no value for, to exercise every branch.
INLINE_TEMPLATE = """## Part 0 — Meta
- **Title**:
- **Subject Type**: ☐ Chain ☐ Asset/Token

## Part 5 — Metrics
- Ethereum-only on-chain supply `[AUTO: Alchemy eth_call totalSupply]`
- Cross-chain aggregate supply `[AUTO: CoinGecko market_data total_supply]`
- Spot price `[AUTO: CoinGecko current_price]`
- TVL over time `[AUTO: DefiLlama historical TVL series]`
- Stablecoin transfer volume `[SEMI-AUTO: Etherscan token transfers; aggregate]`
- Finality time `[MANUAL: chain protocol spec; not in fetchers]`
"""


def _supply_audit(other_source, other_unit, delta, band, within, gap_days=None):
    return {"cross_checks": [{"source": other_source, "value": 0, "as_of": None,
                              "delta": delta, "band": band, "within_band": within,
                              "gap_days": gap_days}]}


# --------------------------------------------------------------------------- #
# unit tests
# --------------------------------------------------------------------------- #
def test_auto_slot_gets_value_and_two_supply_scopes_are_distinct():
    reconciled = [
        _rv("total_supply", 52.571e9, "alchemy", unit="tokens", scope="single-chain",
            agreement="agree",
            inputs=[_ev("total_supply", 52.571e9, "alchemy", unit="tokens", scope="single-chain"),
                    _ev("total_supply", 52.708e9, "etherscan", unit="tokens", scope="single-chain")],
            audit=_supply_audit("etherscan", "tokens", 0.0026, 0.0033, True, gap_days=1.86)),
        _rv("total_supply", 76.378e9, "coingecko", unit="tokens", scope="multi_chain",
            agreement="agree"),
    ]
    out = fill(INLINE_TEMPLATE, reconciled, SREF)

    # both [AUTO] supply slots are filled (marker rewritten) and carry their value
    assert out.count("[AUTO ✓ FILLED") >= 2
    assert "52.57B USDC" in out          # single-chain Ethereum-only
    assert "76.38B USDC" in out          # cross-chain aggregate

    # the two scopes are DISTINCT lines, never merged into one number
    eth_line = next(l for l in out.splitlines() if "52.57B USDC" in l)
    cross_line = next(l for l in out.splitlines() if "76.38B USDC" in l)
    assert eth_line != cross_line
    assert "single-chain" in eth_line
    assert "cross-chain" in cross_line
    # not arithmetically combined (no ~129B total anywhere)
    assert "129" not in out


def test_scope_label_omitted_on_price():
    reconciled = [_rv("price", 0.999729, "coingecko", unit="USD", scope="multi_chain",
                      agreement="agree")]
    out = fill(INLINE_TEMPLATE, reconciled, SREF)
    price_line = next(l for l in out.splitlines() if "$0.9997" in l)
    # price renders, but its multi_chain tag is NOT printed as a scope label
    assert "$0.9997" in price_line
    assert "multi_chain" not in price_line
    assert "cross-chain" not in price_line


def test_semi_and_manual_slots_stay_flagged_not_fabricated():
    out = fill(INLINE_TEMPLATE, [], SREF)
    semi = next(l for l in out.splitlines() if "transfer volume" in l)
    manual = next(l for l in out.splitlines() if "Finality time" in l)
    # markers preserved, visibly flagged, NO fabricated number
    assert "[SEMI-AUTO:" in semi and "NEEDS HUMAN REVIEW" in semi
    assert "[MANUAL:" in manual and "MANUAL" in manual
    assert not re.search(r"\d", manual.split("MANUAL")[-1].replace("B.2", ""))  # no digits invented


def test_auto_slot_with_no_value_stays_flagged():
    # only price supplied -> the TVL [AUTO] slot has no matching value.
    out = fill(INLINE_TEMPLATE, [_rv("price", 1.0, "coingecko")], SREF)
    tvl_line = next(l for l in out.splitlines() if "TVL over time" in l)
    assert "[AUTO:" in tvl_line                # marker NOT consumed
    assert "UNFILLED [AUTO]" in tvl_line
    assert "✓ FILLED" not in tvl_line


def test_evidence_table_maps_confidence_from_agreement():
    reconciled = [
        _rv("price", 1.0, "coingecko", agreement="agree"),
        _rv("market_cap_rank", 6, "coingecko", unit="count", agreement="single_source"),
        _rv("price", 1.1, "coingecko", scope="x", agreement="divergence"),
    ]
    table = build_evidence_table(reconciled, placed=set())
    assert "High (agree)" in table
    assert "Medium (single_source)" in table
    assert "Low (divergence)" in table


def test_evidence_table_notes_value_with_no_slot():
    # a reconciled value placed in NO slot is flagged in the table, not dropped.
    reconciled = [_rv("volume_24h", 18e9, "coingecko", agreement="single_source")]
    out = fill(INLINE_TEMPLATE, reconciled, SREF)
    assert "no matching [AUTO] template slot" in out
    assert "18000000000" in out                 # full precision, recorded in the table


def test_evidence_table_notes_unit_mismatch_in_crosscheck():
    # DefiLlama circulating_supply (USD-peg) cross-checked vs CMC (tokens).
    rv = _rv("circulating_supply", 76.48e9, "defillama", unit="USD", scope="multi_chain",
             agreement="agree",
             inputs=[_ev("circulating_supply", 76.48e9, "defillama", unit="USD", scope="multi_chain"),
                     _ev("circulating_supply", 76.39e9, "coinmarketcap", unit="tokens", scope="multi_chain")],
             audit=_supply_audit("coinmarketcap", "tokens", 0.0012, 0.002, True))
    table = build_evidence_table([rv], placed={("circulating_supply", "multi_chain")})
    assert "[unit: USD vs tokens]" in table


def test_subject_ref_fills_header_context():
    out = fill(INLINE_TEMPLATE, [], SREF)
    assert "[AUTO subject_ref]" in out
    assert "USDC" in out and "Circle" in out
    assert "usd-coin" in out and "3408" in out
    # Title slot filled; Asset/Token box checked
    title = next(l for l in out.splitlines() if l.strip().startswith("- **Title**:"))
    assert "USDC" in title
    assert "☑ Asset/Token" in out


def test_fill_is_pure_does_not_mutate_inputs():
    reconciled = [_rv("price", 1.0, "coingecko")]
    snapshot = (reconciled[0].metric, reconciled[0].value, reconciled[0].audit)
    fill(INLINE_TEMPLATE, reconciled, SREF)
    assert (reconciled[0].metric, reconciled[0].value, reconciled[0].audit) == snapshot


def test_render_value_human_readable():
    assert render_value(_rv("price", 0.999729, "cg", unit="USD"), SREF) == "$0.9997"
    assert render_value(_rv("market_cap", 76.39e9, "cg", unit="USD"), SREF) == "$76.39B"
    assert render_value(_rv("total_supply", 52.571e9, "al", unit="tokens"), SREF) == "52.57B USDC"
    assert render_value(_rv("market_cap_rank", 6, "cg", unit="count"), SREF) == "#6"


# --------------------------------------------------------------------------- #
# ★ real end-to-end test
# --------------------------------------------------------------------------- #
def _newest(source: str, pattern: str):
    base = RAW / source
    if not base.exists():
        return
    for c in sorted(base.glob(pattern), reverse=True):
        yield json.loads(c.read_text())


def _first(source, pattern, fn):
    for env in _newest(source, pattern):
        res = fn(env)
        if res:
            return res
    return None


def test_real_usdc_end_to_end_fill(capsys):
    if not TEMPLATE.exists():
        pytest.skip("template absent")
    # import the PURE extractors HERE — the filler never imports them.
    from analysis_layer.extractors import (
        alchemy, etherscan, coingecko, coinmarketcap, defillama,
    )
    from analysis_layer.resolvers.subject_ref import resolve_subject
    from analysis_layer.aggregators.reconcile import reconcile

    sref = resolve_subject("USDC")
    decimals = sref.decimals

    inputs = []
    a = _first("alchemy", "*.json", lambda e: alchemy.decode_total_supply(e, decimals))
    if a:
        inputs.append(a)
    es = _first("etherscan", "*.json", lambda e: etherscan.extract_supply(e, decimals))
    if es:
        inputs.append(es)
    cg = _first("coingecko", "usdc_*.json", coingecko.extract_spot_metrics)
    if cg:
        inputs.extend(cg)
    cmc = _first("coinmarketcap", "usdc_*.json", coinmarketcap.extract_latest_quote)
    if cmc:
        inputs.extend(cmc)
    dl = _first("defillama", "usdc_*.json", lambda e: defillama.latest(e))
    if dl:
        inputs.append(dl)

    if not inputs:
        pytest.skip("no real USDC envelopes on disk")

    reconciled = reconcile(inputs)
    markdown = fill(TEMPLATE.read_text(encoding="utf-8"), reconciled, sref)

    # write the deliverable to a gitignored path
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "usdc_b28_filled.md"
    out_path.write_text(markdown, encoding="utf-8")

    by = {(r.metric, r.scope): r for r in reconciled}

    # ---- [AUTO] supply slot carries the real numbers --------------------- #
    sc = by.get(("total_supply", "single-chain"))
    mc = by.get(("total_supply", "multi_chain"))
    circ = by.get(("circulating_supply", "multi_chain"))

    # the stablecoin-supply [AUTO] slot must have been FILLED
    assert "[AUTO ✓ FILLED" in markdown
    if sc is not None:
        assert "52.5" in markdown or "52.6" in markdown     # Ethereum-only ~$52.6B
        assert "single-chain" in markdown
    if mc is not None:
        assert "76.3" in markdown or "76.4" in markdown     # cross-chain ~$76.4B
        assert "cross-chain" in markdown
    if circ is not None:
        assert "76.4" in markdown or "76.5" in markdown

    # ---- price reconciled and present (no [AUTO] price slot in v1.2 -> it
    #      lands in the Evidence Table with a "no slot" note) -------------- #
    price = by.get(("price", "multi_chain"))
    if price is not None:
        assert "0.999" in markdown
    assert "no matching [AUTO] template slot" in markdown    # price/mcap/rank etc.

    # ---- Evidence Table present, one row per reconciled fact, confidence -- #
    assert "Auto Evidence Table" in markdown
    assert "Confidence" in markdown
    assert "High (agree)" in markdown or "Medium (single_source)" in markdown

    # ---- SEMI / MANUAL stayed flagged ------------------------------------ #
    assert "NEEDS HUMAN REVIEW [SEMI-AUTO]" in markdown
    assert "**MANUAL** — researcher must fill" in markdown
    # the real template's SEMI/MANUAL markers survive
    assert "[SEMI-AUTO:" in markdown and "[MANUAL:" in markdown

    # ---- some [AUTO] slots have no value -> stay flagged ----------------- #
    assert "UNFILLED [AUTO]" in markdown

    # ---- subject_ref header context -------------------------------------- #
    assert "[AUTO subject_ref]" in markdown and "Circle" in markdown

    # report
    summary = [
        "", "=== REAL USDC filled markdown ===",
        f"written to: {out_path.relative_to(ROOT)}",
        f"reconciled facts: {len(reconciled)}",
        f"slots FILLED markers: {markdown.count('[AUTO ✓ FILLED')}",
        f"slots UNFILLED (flagged): {markdown.count('UNFILLED [AUTO]')}",
        f"SEMI-AUTO flagged: {markdown.count('NEEDS HUMAN REVIEW [SEMI-AUTO]')}",
        f"MANUAL flagged: {markdown.count('**MANUAL** — researcher must fill')}",
    ]
    with capsys.disabled():
        print("\n".join(summary))
