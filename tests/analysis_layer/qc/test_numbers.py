"""⑤.1 (TD-048) — the fail-closed numbers-trace gate.

PURE, no network. A faithful report (every machine value intact) traces to [];
an altered or dropped machine value is flagged; null financials cells are
skipped; a SYNTHETIC non-USDC bundle traces ITS own values (proves nothing is
USDC-hardcoded); and the LIVE latest USDC report passes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.qc.numbers import check_numbers_trace

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "meta" / "reports"


# --------------------------------------------------------------------------- #
# fixtures — a small synthetic bundle + a faithful report rendering of it
# --------------------------------------------------------------------------- #
# A NON-USDC subject with made-up windows/values, so a pass proves the gate reads
# field names off `facts` rather than hard-coding any USDC literal.
SYNTH_BUNDLE = {
    "schema": "stack_anamnesis.facts_bundle/v1",
    "subject": "ZYX",
    "subject_type": "stablecoin",
    "issuer": "Acme",
    "metrics": [
        {"metric": "price", "scope": "multi_chain", "value": 1.0023,
         "unit": "USD", "source": "coingecko"},
        {"metric": "market_cap", "scope": "multi_chain", "value": 42123456789.0,
         "unit": "USD", "source": "coingecko"},
        {"metric": "market_cap_rank", "scope": "multi_chain", "value": 11,
         "unit": "count", "source": "coingecko"},
        {"metric": "total_supply", "scope": "single-chain", "value": 12345678901.0,
         "unit": "tokens", "source": "alchemy"},
    ],
    "supply_momentum": [
        {"window": "30d", "window_days": 30, "net_change_pct": -3.1415,
         "net_change_abs": -987654321.0, "abs_unit": "USD", "source": "defillama"},
    ],
    "issuer_financials": {
        "issuer": "Acme",
        "fiscal_year": 2025,
        "revenues": {"value": 5432100000, "unit": "USD", "source": "sec_edgar"},
        "net_income": {"value": -123400000, "unit": "USD", "source": "sec_edgar"},
    },
}


def _faithful_synth_report() -> str:
    """A prose report that renders every SYNTH_BUNDLE value the way the deliverable
    would — filler 4-decimal price, 3-sig-fig magnitudes, the filler-exact percent
    and signed delta."""
    return (
        "# Research — ZYX\n\n"
        "ZYX trades at $1.0023, a market cap of $42.1B (rank #11). "
        "Single-chain supply is 12.3B ZYX. Over 30d supply moved -3.14% "
        "(-$988M). Acme reported FY2025 revenue of $5.43B and a net loss of "
        "-$123M.\n"
    )


# --------------------------------------------------------------------------- #
# 1. a faithful report -> []
# --------------------------------------------------------------------------- #
def test_faithful_synthetic_report_is_clean():
    assert check_numbers_trace(_faithful_synth_report(), SYNTH_BUNDLE) == []


# --------------------------------------------------------------------------- #
# 2. an altered / dropped machine value is flagged
# --------------------------------------------------------------------------- #
def test_altered_percent_is_flagged():
    # -3.14% truncated to -3.1% (the brief's -1.62% -> -1.6% analogue).
    bad = _faithful_synth_report().replace("-3.14%", "-3.1%")
    violations = check_numbers_trace(bad, SYNTH_BUNDLE)
    assert any("supply 30d" in v for v in violations)


def test_altered_magnitude_value_is_flagged():
    # market cap mangled to a different number -> present in NO canonical form.
    bad = _faithful_synth_report().replace("$42.1B", "$24.1B")
    violations = check_numbers_trace(bad, SYNTH_BUNDLE)
    assert any("market_cap" in v for v in violations)


def test_dropped_value_is_flagged():
    # drop the price entirely.
    bad = _faithful_synth_report().replace("$1.0023", "around a dollar")
    violations = check_numbers_trace(bad, SYNTH_BUNDLE)
    assert any("price" in v for v in violations)


def test_dropped_financial_is_flagged():
    bad = _faithful_synth_report().replace("$5.43B", "strong revenue")
    violations = check_numbers_trace(bad, SYNTH_BUNDLE)
    assert any("revenues" in v for v in violations)


# --------------------------------------------------------------------------- #
# 3. null financials cells are skipped (non-issuer subject) — no false flag
# --------------------------------------------------------------------------- #
def test_null_issuer_financials_skipped():
    bundle = dict(SYNTH_BUNDLE)
    bundle["issuer_financials"] = None
    # a report that mentions none of the financials still passes (they're null).
    report = (
        "# Research — ZYX\n\n"
        "ZYX trades at $1.0023, a market cap of $42.1B (rank #11). "
        "Single-chain supply is 12.3B ZYX. Over 30d supply moved -3.14% "
        "(-$988M).\n"
    )
    assert check_numbers_trace(report, bundle) == []


def test_partially_null_financial_cell_skipped():
    bundle = json.loads(json.dumps(SYNTH_BUNDLE))
    bundle["issuer_financials"]["net_income"] = {
        "value": None, "unit": "USD", "source": "sec_edgar"
    }
    # net_income is null -> skipped; the report need not mention it.
    report = (
        "# Research — ZYX\n\n$1.0023, $42.1B, #11, 12.3B ZYX, -3.14%, -$988M, "
        "revenue $5.43B.\n"
    )
    assert check_numbers_trace(report, bundle) == []


# --------------------------------------------------------------------------- #
# 4. ★ GENERIC — nothing USDC-hardcoded: the synthetic non-USDC bundle traces its
#    OWN subject symbol (ZYX) and values.
# --------------------------------------------------------------------------- #
def test_generic_subject_symbol_is_used():
    # The same supply number rendered with the WRONG symbol must NOT satisfy the
    # token trace — proving the subject is read off `facts`, not assumed.
    report = _faithful_synth_report().replace("12.3B ZYX", "12.3B USDC")
    violations = check_numbers_trace(report, SYNTH_BUNDLE)
    assert any("total_supply" in v for v in violations)


# --------------------------------------------------------------------------- #
# 5. the LIVE latest USDC report passes (writer did not override) -> []
# --------------------------------------------------------------------------- #
def _latest_pair():
    bundles = sorted(REPORTS.glob("usdc_*.facts.json"))
    for bundle_path in reversed(bundles):
        report_path = bundle_path.with_name(
            bundle_path.name.replace(".facts.json", ".report.md")
        )
        if report_path.exists():
            return report_path, bundle_path
    return None, None


def test_live_usdc_report_is_clean():
    report_path, bundle_path = _latest_pair()
    if report_path is None:
        pytest.skip("no live <slug>.report.md + .facts.json pair on disk")
    report_md = report_path.read_text(encoding="utf-8")
    facts = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert check_numbers_trace(report_md, facts) == []
