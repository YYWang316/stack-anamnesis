"""④.2 (TD-047) — the subject-agnostic inline-SVG chart builders.

PURE, no network. The builders read ONLY the facts-bundle field names, so a
made-up NON-USDC bundle must produce charts from ITS numbers — proving nothing is
hardcoded to USDC. Missing fields → None (the renderer turns that into an honest
placeholder). Same facts → byte-identical SVG (determinism).
"""
from __future__ import annotations

from analysis_layer.render.charts import (
    issuer_financials_svg, supply_momentum_svg,
)

# A synthetic NON-USDC bundle: a made-up "TESTCOIN" with different windows and
# values than the real USDC report — if a chart renders THESE, nothing is
# USDC-hardcoded.
TESTCOIN_MOMENTUM = [
    {"window": "14d", "window_days": 14, "net_change_pct": 3.50, "source": "fakesource"},
    {"window": "60d", "window_days": 60, "net_change_pct": -7.25, "source": "fakesource"},
]
TESTCOIN_FINANCIALS = {
    "issuer": "TestCorp",
    "fiscal_year": 2099,
    "revenues": {"value": 1234000000.0, "unit": "EUR", "source": "fake_edgar"},
    "net_income": {"value": -42000000.0, "unit": "EUR", "source": "fake_edgar"},
    "assets": {"value": 9000000000.0, "unit": "EUR", "source": "fake_edgar"},
    "liabilities": {"value": 8000000000.0, "unit": "EUR", "source": "fake_edgar"},
    "equity": {"value": 1000000000.0, "unit": "EUR", "source": "fake_edgar"},
}


def test_supply_momentum_basic_bars_and_colours():
    svg = supply_momentum_svg(TESTCOIN_MOMENTUM)
    assert svg is not None and svg.startswith("<svg")
    assert svg.count("<rect") == 2                 # one bar per window
    assert "14d" in svg and "60d" in svg           # window labels from THE DATA
    assert "+3.50%" in svg and "−7.25%" in svg     # signed value labels
    assert "var(--ok-ink)" in svg                  # positive bar → green
    assert "var(--bad-ink)" in svg                 # negative bar → red


def test_supply_momentum_subject_agnostic():
    """GENERIC: a totally different (window, value) set drives the chart — proves
    nothing is keyed to USDC's 7d/30d/90d or its numbers."""
    svg = supply_momentum_svg(TESTCOIN_MOMENTUM)
    # USDC's real values / windows must NOT appear for TESTCOIN's input
    assert "7d" not in svg and "90d" not in svg
    assert "−1.62%" not in svg and "+0.24%" not in svg


def test_supply_momentum_empty_returns_none():
    assert supply_momentum_svg([]) is None
    assert supply_momentum_svg(None) is None
    # entries with no usable net_change_pct → None, not a fabricated bar
    assert supply_momentum_svg([{"window": "7d", "net_change_pct": None}]) is None


def test_issuer_financials_flow_and_stock():
    svg = issuer_financials_svg(TESTCOIN_FINANCIALS)
    assert svg is not None and svg.startswith("<svg")
    # five fields → five bars
    assert svg.count("<rect") == 5
    assert "Revenue" in svg and "Net income" in svg          # flow group
    assert "Assets" in svg and "Liabilities" in svg and "Equity" in svg  # stock
    assert "FY2099" in svg                                    # fiscal year from data
    assert "EUR" in svg                                       # unit from data
    # the negative net income is red and signed
    assert "var(--bad-ink)" in svg
    assert "−$42.0M" in svg
    # positive magnitudes use the navy accent, NOT the green ok-ink
    assert "var(--color-accent)" in svg


def test_issuer_financials_subject_agnostic():
    svg = issuer_financials_svg(TESTCOIN_FINANCIALS)
    # USDC/Circle's real FY/values must NOT leak in — TESTCOIN's drive it
    assert "Circle" not in svg and "FY2025" not in svg
    assert "FY2099" in svg
    assert "$1.23B" in svg  # TESTCOIN revenue, not any USDC number


def test_issuer_financials_none_and_empty():
    assert issuer_financials_svg(None) is None
    assert issuer_financials_svg({}) is None
    # present dict but no numeric concept fields → None (no fabricated chart)
    assert issuer_financials_svg({"issuer": "X", "fiscal_year": 2030}) is None


def test_issuer_financials_partial_group():
    """Only flow present (no stock fields) still renders — just the flow group."""
    svg = issuer_financials_svg({
        "fiscal_year": 2040,
        "revenues": {"value": 500.0, "unit": "USD", "source": "s"},
    })
    assert svg is not None
    assert svg.count("<rect") == 1
    assert "Revenue" in svg
    assert "Assets" not in svg


def test_charts_self_contained():
    for svg in (supply_momentum_svg(TESTCOIN_MOMENTUM),
                issuer_financials_svg(TESTCOIN_FINANCIALS)):
        assert "<script" not in svg
        assert "http://" not in svg and "https://" not in svg
        assert "cdn" not in svg.lower()
        assert "<image" not in svg and "xlink" not in svg


def test_charts_deterministic():
    assert supply_momentum_svg(TESTCOIN_MOMENTUM) == supply_momentum_svg(TESTCOIN_MOMENTUM)
    assert issuer_financials_svg(TESTCOIN_FINANCIALS) == issuer_financials_svg(TESTCOIN_FINANCIALS)
