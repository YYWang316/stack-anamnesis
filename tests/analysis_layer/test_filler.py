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
from analysis_layer.fillers.fill import (
    build_evidence_table, fill, render_value, select_sections,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "meta" / "raw"
TEMPLATE = ROOT / "references" / "templates" / "crypto_research_v1.2.md"
# The on-disk file is named v1.3 but its content header is "Research SOP v1.4" —
# the unified master template with the Part 5.1–5.5 subject-type modules and the
# Part 8 valuation Paths A/B/C the module-aware pass selects against.
TEMPLATE_V14 = ROOT / "references" / "templates" / "crypto_research_v1.3.md"
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
# module-aware section selection (B.2.8b)
# --------------------------------------------------------------------------- #
# An inline unified template: a [Both] section (subject-agnostic), a [Mode B
# only] section (dropped in Mode A), a [Chain] module and a [Stablecoin] module
# (subject-type-exclusive, exactly one survives per subject).
MODULE_TEMPLATE = """## Part 0 — Meta `[Both]`
- **Title**:

## Part 2 — News Hook `[Mode B only — comes BEFORE Part 1]`
### 2.1 What happened
news body that must vanish in Mode A.

## Part 5.X Chain metrics `[Chain / L2]`
- chain-only metric `[AUTO: DefiLlama TVL]`

## Part 5.Y Stablecoin metrics `[Stablecoin]`
- Stablecoin supply `[AUTO: DefiLlama stablecoins]`

## Part 6 — Competitive `[Both, essential]`
shared competitive body kept for every subject.
"""

SREF_CHAIN = SubjectRef(subject="Ethereum", subject_type="chain", decimals=None)
SREF_UNKNOWN = SubjectRef(subject="MysteryDAO", subject_type="wallet", decimals=None)


def test_select_keeps_stablecoin_module_drops_chain_and_modeB():
    kept, info = select_sections(MODULE_TEMPLATE, "stablecoin", mode="subject_driven")
    # subject-type-agnostic [Both] + the matching [Stablecoin] module survive
    assert "Stablecoin metrics" in kept
    assert "Part 0 — Meta" in kept and "Competitive" in kept
    # the [Chain] module and the [Mode B only] section are GONE (not flagged)
    assert "Chain metrics" not in kept
    assert "chain-only metric" not in kept
    assert "News Hook" not in kept and "news body" not in kept
    assert "Part 2 — News Hook" in info["omitted"][0] or any(
        "News Hook" in h for h in info["omitted"])
    assert info["failsafe"] is None


def test_select_keeps_chain_module_drops_stablecoin():
    kept, info = select_sections(MODULE_TEMPLATE, "chain", mode="subject_driven")
    assert "Chain metrics" in kept
    assert "Part 0 — Meta" in kept and "Competitive" in kept
    assert "Stablecoin metrics" not in kept
    assert "Stablecoin supply" not in kept
    # Mode B section still dropped (we are in Mode A regardless of subject)
    assert "News Hook" not in kept


def test_select_failsafe_keeps_everything_for_unknown_subject_type():
    kept, info = select_sections(MODULE_TEMPLATE, "wallet", mode="subject_driven")
    # unmapped type -> nothing dropped, both modules + Mode B section survive
    assert "Chain metrics" in kept and "Stablecoin metrics" in kept
    assert "News Hook" in kept
    assert kept == MODULE_TEMPLATE
    assert info["failsafe"] and "wallet" in info["failsafe"]
    assert info["omitted"] == []


def test_select_payment_chain_keeps_payment_not_generic_chain_token():
    # "payment chain" is consumed before the generic "chain" token, so a
    # [Payment chain] section is NOT kept for a plain chain subject.
    tmpl = "## Part 5.3 Payment chain–specific `[Payment chain]`\n- m `[AUTO: x]`\n"
    kept_pay, _ = select_sections(tmpl, "payment_chain")
    kept_chain, _ = select_sections(tmpl, "chain")
    assert "Payment chain–specific" in kept_pay
    assert "Payment chain–specific" not in kept_chain


def test_fill_runs_module_selection_when_subject_ref_present():
    # fill() drops the [Mode B only] News Hook for a Mode-A stablecoin run.
    out = fill(MODULE_TEMPLATE, [], SREF)
    assert "Stablecoin metrics" in out
    assert "Chain metrics" not in out
    assert "News Hook" not in out
    assert "[AUTO module-aware]" in out and "stablecoin" in out


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
    a = _first("alchemy", "*0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48*.json", lambda e: alchemy.decode_total_supply(e, decimals))
    if a:
        inputs.append(a)
    es = _first("etherscan", "*0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48*.json", lambda e: etherscan.extract_supply(e, decimals))
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


def _build_usdc_reconciled():
    """Run the real USDC chain: on-disk envelopes -> pure extractors -> reconcile().
    Returns ``(sref, reconciled)`` or ``None`` if no envelopes are present."""
    from analysis_layer.extractors import (
        alchemy, etherscan, coingecko, coinmarketcap, defillama,
    )
    from analysis_layer.resolvers.subject_ref import resolve_subject
    from analysis_layer.aggregators.reconcile import reconcile

    sref = resolve_subject("USDC")
    decimals = sref.decimals

    inputs = []
    a = _first("alchemy", "*0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48*.json", lambda e: alchemy.decode_total_supply(e, decimals))
    if a:
        inputs.append(a)
    es = _first("etherscan", "*0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48*.json", lambda e: etherscan.extract_supply(e, decimals))
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
        return None
    return sref, reconcile(inputs)


def test_real_usdc_module_aware_fill(capsys):
    """★ THE PAYOFF — re-run the USDC chain and fill() the REAL v1.4 master
    template with subject_type='stablecoin', mode A. The output must be a CLEAN
    stablecoin report: the chain/payment/DeFi modules and the Mode-B News Hook are
    GONE entirely, the Stablecoin module + the subject-agnostic [Both] sections
    stay, and the stablecoin [AUTO] supply slots are still filled."""
    if not TEMPLATE_V14.exists():
        pytest.skip("v1.4 template absent")
    built = _build_usdc_reconciled()
    if built is None:
        pytest.skip("no real USDC envelopes on disk")
    sref, reconciled = built

    markdown = fill(TEMPLATE_V14.read_text(encoding="utf-8"), reconciled, sref,
                    mode="subject_driven")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "usdc_b28b_module_aware.md"
    out_path.write_text(markdown, encoding="utf-8")

    # ---- OMITTED: chain / payment / DeFi modules + the Mode-B News Hook ---- #
    # (anchored on header strings unique to each omitted section)
    assert "通用指标" not in markdown               # 5.1 generic chain metrics
    assert "Chain-specific" not in markdown          # 5.2
    assert "TVL 不是核心" not in markdown            # 5.3 payment-chain header
    assert "Utilization rate" not in markdown        # 5.4 DeFi-protocol metric
    assert "News Hook" not in markdown               # Part 2 (Mode B only)
    assert "4.3 Tokenomics" not in markdown          # crypto-native-asset only
    assert "If no token exists" not in markdown      # Part 8 Path B (infra)

    # ---- KEPT: the Stablecoin module + the [Both] sections ---------------- #
    assert "Stablecoin module" in markdown           # 5.5
    assert "Reserve & Backing" in markdown           # 5.5 D
    assert "Issuer Economics" in markdown            # 5.5 E
    assert "Thesis & Framing" in markdown            # Part 1 [Both]
    assert "Competitive Landscape" in markdown       # Part 6 [Both]
    assert "Part 11 — Conclusion" in markdown        # Part 11 [Both]
    assert "Path C" in markdown                      # stablecoin valuation path

    # ---- stablecoin [AUTO] supply slot still filled, rest flagged --------- #
    assert "[AUTO ✓ FILLED" in markdown
    by = {(r.metric, r.scope): r for r in reconciled}
    if by.get(("total_supply", "single-chain")) is not None:
        assert ("52.5" in markdown or "52.6" in markdown) and "single-chain" in markdown
    if by.get(("total_supply", "multi_chain")) is not None:
        assert ("76.3" in markdown or "76.4" in markdown) and "cross-chain" in markdown
    assert "UNFILLED [AUTO]" in markdown
    assert "no matching [AUTO] template slot" in markdown   # mcap/rank/volume etc.

    # ---- evidence table, faithfulness flags, module-aware note ------------ #
    assert "Auto Evidence Table" in markdown
    assert "NEEDS HUMAN REVIEW [SEMI-AUTO]" in markdown
    assert "**MANUAL** — researcher must fill" in markdown
    assert "[AUTO subject_ref]" in markdown and "Circle" in markdown
    assert "[AUTO module-aware]" in markdown and "stablecoin" in markdown

    summary = [
        "", "=== REAL USDC module-aware (v1.4) filled markdown ===",
        f"written to: {out_path.relative_to(ROOT)}",
        f"reconciled facts: {len(reconciled)}",
        f"FILLED markers: {markdown.count('[AUTO ✓ FILLED')}",
        f"UNFILLED (flagged): {markdown.count('UNFILLED [AUTO]')}",
        "OMITTED modules: Part 2 (News Hook), 5.1 通用指标, 5.2 Chain-specific, "
        "5.3 Payment chain, 5.4 DeFi, 4.3 Tokenomics, Path A, Path B",
        "KEPT: Part 5.5 Stablecoin module + [Both] sections + Path C",
    ]
    with capsys.disabled():
        print("\n".join(summary))


# --------------------------------------------------------------------------- #
# ★ real end-to-end — B.2.9 change layer (supply momentum) fills the 5.5 A
#   "Net … supply change" [SEMI-AUTO] slot
# --------------------------------------------------------------------------- #
def _section_5_5_a(markdown: str) -> str:
    """Extract the Part 5.5 'A. Supply & Distribution Dynamics' sub-section for the
    before/after paste (header down to the next '####' sub-header)."""
    lines = markdown.splitlines()
    start = next((i for i, l in enumerate(lines)
                  if l.startswith("####") and "Supply & Distribution" in l), None)
    if start is None:
        return "(5.5 A section not found)"
    end = next((j for j in range(start + 1, len(lines))
                if lines[j].startswith("####")), len(lines))
    return "\n".join(lines[start:end])


def test_real_usdc_supply_change_fills_5_5_a(capsys):
    """★ THE B.2.9 PAYOFF — load the real DefiLlama envelope, compute_supply_change()
    leg 1/3 of the KEY SIGNAL, CONCATENATE with reconcile(inputs), and fill() the real
    v1.4 template (stablecoin, Mode A). The 5.5 A "Net … supply change" line must flip
    from flagged-for-human to "[SEMI-AUTO ✓ COMPUTED]" carrying the computable windows
    (abs + pct + actual-days) at Medium confidence — while the rest of the report is
    unchanged (still clean, chain modules still omitted, the KEY SIGNAL verdict NOT
    auto-decided)."""
    if not TEMPLATE_V14.exists():
        pytest.skip("v1.4 template absent")
    built = _build_usdc_reconciled()
    if built is None:
        pytest.skip("no real USDC envelopes on disk")
    sref, reconciled = built

    from analysis_layer.derivations.supply_change import compute_supply_change

    # the same envelope the filler's other supply slots read
    env = next(_newest("defillama", "usdc_*.json"), None)
    if env is None:
        pytest.skip("no real DefiLlama envelope on disk")

    template = TEMPLATE_V14.read_text(encoding="utf-8")

    # ---- BEFORE: fill WITHOUT the change layer -> the slot is flagged ----- #
    before = fill(template, reconciled, sref, mode="subject_driven")
    before_5_5_a = _section_5_5_a(before)
    assert "NEEDS HUMAN REVIEW [SEMI-AUTO]" in before_5_5_a   # flagged for a human
    assert "[SEMI-AUTO ✓ COMPUTED" not in before_5_5_a

    # ---- compute leg 1/3 + CONCATENATE with the reconciled values --------- #
    changes, notes = compute_supply_change(env, sref)
    assert changes, "real envelope should cover at least one window"
    after = fill(template, list(reconciled) + changes, sref, mode="subject_driven")
    after_5_5_a = _section_5_5_a(after)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "usdc_b29_supply_change.md").write_text(after, encoding="utf-8")

    # ---- AFTER: the 5.5 A net-change slot is now FILLED ------------------- #
    assert "[SEMI-AUTO ✓ COMPUTED" in after_5_5_a
    assert "NEEDS HUMAN REVIEW [SEMI-AUTO]" not in after_5_5_a or \
        "[SEMI-AUTO ✓ COMPUTED" in after_5_5_a   # the net-change line specifically flipped
    # the computed windows render as sub-bullets with abs + pct + actual-days
    by = {rv.metric: rv for rv in changes}
    for metric, rv in by.items():
        days = rv.audit["window_days"]
        assert f"over {days}d" in after_5_5_a
        # right sign: a rising window shows '+', a falling one '-'
        sign = "+" if rv.value > 0 else "-"
        assert f"({sign}" in after_5_5_a
    assert "actual" in after_5_5_a
    # single-source-by-nature -> Medium confidence
    assert "**Medium** (single_source)" in after_5_5_a

    # ---- the KEY SIGNAL verdict is NOT auto-decided (left as template) ---- #
    assert "☐ CONFIRMATION" in after and "☐ DIVERGENCE" in after

    # ---- the rest of the report is UNCHANGED outside 5.5 A ---------------- #
    # chain modules still omitted, evidence table + faithfulness flags intact
    assert "通用指标" not in after and "Utilization rate" not in after
    assert "News Hook" not in after
    assert "Stablecoin module" in after and "Path C" in after
    assert "Auto Evidence Table" in after
    assert "[AUTO subject_ref]" in after and "Circle" in after
    # the report BODY (everything before the Evidence Table) is byte-identical
    # outside the 5.5 A block; the Evidence Table itself legitimately gains the 3
    # new net-change rows (they are reconciled facts, recorded — not dropped).
    before_body = before.split("## Auto Evidence Table")[0].replace(before_5_5_a, "")
    after_body = after.split("## Auto Evidence Table")[0].replace(after_5_5_a, "")
    assert before_body == after_body
    # and the new facts DO surface in the Evidence Table at Medium confidence
    assert "net_supply_change_7d" in after and "Medium (single_source)" in after

    with capsys.disabled():
        print("\n=== B.2.9 — Part 5.5 A  (BEFORE: flagged) ===")
        print(before_5_5_a)
        print("\n=== B.2.9 — Part 5.5 A  (AFTER: computed) ===")
        print(after_5_5_a)
        computed = ", ".join(sorted(m.replace("net_supply_change_", "") for m in by))
        skipped = "; ".join(notes) if notes else "(none)"
        print(f"\ncomputable windows from real envelope: {computed}")
        print(f"skipped windows: {skipped}")
