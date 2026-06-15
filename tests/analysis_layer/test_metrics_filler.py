"""2a filler (TD-050 go-live chunk 1) — machine facts table at <!-- MODULE: metrics -->.

The deterministic step that renders the facts bundle into the v3 skeleton's metrics
table. PURE, field-driven, subject-agnostic. Verifies: ONLY the metrics anchor is
consumed (metrics-analysis + others left for the writer/renderer), graceful-missing
sub-tables, numbers match fill.py's formatters / the ⑤.1 gate, and determinism.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.fillers.fill import (
    build_metrics_table, fill_metrics_module, render_value,
)
from analysis_layer.qc.numbers import _metric_forms

ROOT = Path(__file__).resolve().parents[2]

# A minimal skeleton fragment carrying the metrics anchor, the metrics-analysis
# anchor (the substring trap), and one other anchor that must be left intact.
SKEL = """## Part 5 — Metrics

<!-- MODULE: metrics -->

<!-- MODULE: metrics-analysis -->

## Part 8 — Valuation

<!-- MODULE: valuation -->
"""

# A synthetic NON-USDC bundle (subject-agnostic): if the table renders from THESE
# fields, nothing is hardcoded to USDC.
FACTS = {
    "subject": "ZYX",
    "metrics": [
        {"metric": "price", "scope": "multi_chain", "value": 1.0023, "unit": "USD",
         "source": "coingecko", "as_of": "2026-03-09T12:00:00Z", "confidence": "High"},
        {"metric": "circulating_supply", "scope": "multi_chain",
         "value": 12_300_000_000.0, "unit": "USD", "source": "defillama",
         "as_of": "2026-03-10T00:00:00+00:00", "confidence": "High"},
        {"metric": "total_supply", "scope": "single-chain", "value": 8_000_000_000.0,
         "unit": "tokens", "source": "alchemy", "as_of": "2026-03-10T00:00:00Z",
         "confidence": "High"},
        {"metric": "market_cap_rank", "scope": "multi_chain", "value": 17,
         "unit": "count", "source": "coingecko", "as_of": "2026-03-09T12:00:00Z",
         "confidence": "Medium"},
    ],
    "supply_momentum": [
        {"window": "30d", "window_days": 30, "net_change_pct": 2.50,
         "net_change_abs": 300_000_000.0, "direction": "up", "source": "defillama",
         "as_of": "2026-03-10T00:00:00Z", "confidence": "Medium"},
    ],
    "issuer_financials": {
        "issuer": "ZYX Corp", "fiscal_year": 2024,
        "revenues": {"value": 1_000_000_000.0, "unit": "USD", "source": "sec_edgar",
                     "as_of": "2024-12-31"},
        "net_income": {"value": 50_000_000.0, "unit": "USD", "source": "sec_edgar",
                       "as_of": "2024-12-31"},
    },
}


# --------------------------------------------------------------------------- #
# anchor handling — fill ONLY metrics; never touch metrics-analysis / others
# --------------------------------------------------------------------------- #
def test_metrics_anchor_replaced_others_intact():
    out = fill_metrics_module(SKEL, FACTS)
    assert "<!-- MODULE: metrics -->" not in out            # consumed
    assert "<!-- MODULE: metrics-analysis -->" in out       # NOT touched
    assert "<!-- MODULE: valuation -->" in out              # left for the writer
    # the table landed where the metrics anchor was
    assert "**Spot metrics**" in out
    assert "**Supply momentum**" in out
    assert "**Issuer financials** (ZYX Corp · FY2024)" in out


def test_substring_trap_metrics_analysis_not_caught():
    """A skeleton with ONLY the metrics-analysis anchor (no bare metrics anchor)
    is returned UNCHANGED — the full-anchor match never catches the longer one."""
    skel = "intro\n\n<!-- MODULE: metrics-analysis -->\n\noutro\n"
    assert fill_metrics_module(skel, FACTS) == skel


def test_prose_anchor_mention_not_replaced():
    """An anchor mentioned INLINE in prose (the skeleton's own ANCHOR CONVENTION
    describes `<!-- MODULE: metrics -->`) is left intact — only the STANDALONE
    anchor line is the injection point, so the table is inserted exactly once."""
    skel = (
        "> ANCHOR CONVENTION — the filler MUST replace `<!-- MODULE: metrics -->`.\n\n"
        "<!-- MODULE: metrics -->\n\n"
        "<!-- MODULE: metrics-analysis -->\n"
    )
    out = fill_metrics_module(skel, FACTS)
    assert out.count("**Spot metrics**") == 1                       # filled once
    assert "the filler MUST replace `<!-- MODULE: metrics -->`" in out  # prose intact
    assert "<!-- MODULE: metrics-analysis -->" in out


# --------------------------------------------------------------------------- #
# field-driven + graceful-missing (like charts.py)
# --------------------------------------------------------------------------- #
def test_missing_issuer_financials_no_table_no_error():
    facts = dict(FACTS, issuer_financials=None)
    table = build_metrics_table(facts)
    assert "**Spot metrics**" in table and "**Supply momentum**" in table
    assert "**Issuer financials**" not in table          # omitted, not an error


def test_spot_only_bundle():
    facts = {"subject": "ZYX", "metrics": FACTS["metrics"]}
    table = build_metrics_table(facts)
    assert "**Spot metrics**" in table
    assert "**Supply momentum**" not in table
    assert "**Issuer financials**" not in table


def test_all_empty_bundle_honest_note():
    table = build_metrics_table({"subject": "ZYX"})
    assert table == "_No machine-readable metrics in this bundle._"
    # and it still consumes the anchor (the filler is the metrics consumer)
    out = fill_metrics_module("<!-- MODULE: metrics -->", {"subject": "ZYX"})
    assert "<!-- MODULE: metrics -->" not in out


def test_subject_agnostic_token_symbol():
    """The token-count value carries the bundle's OWN subject symbol, not USDC."""
    table = build_metrics_table(FACTS)
    assert "8.00B ZYX" in table
    assert "USDC" not in table


# --------------------------------------------------------------------------- #
# numbers match the filler's formatters / the ⑤.1 gate
# --------------------------------------------------------------------------- #
def test_values_match_render_value_and_qc_forms():
    table = build_metrics_table(FACTS)
    # spot-check several values against render_value (the canonical formatter)
    from types import SimpleNamespace

    def rv(value, unit, metric, subject="ZYX"):
        return render_value(SimpleNamespace(value=value, unit=unit, metric=metric),
                            SimpleNamespace(subject=subject))

    assert rv(12_300_000_000.0, "USD", "circulating_supply") == "$12.30B"
    assert "$12.30B" in table
    assert rv(1.0023, "USD", "price") == "$1.0023" and "$1.0023" in table
    assert rv(17, "count", "market_cap_rank") == "#17" and "#17" in table
    # supply momentum: ⑤.1-exact percent + signed-$ absolute
    assert "+2.50%" in table and "+$300.00M" in table
    # the printed value is a form the ⑤.1 numbers-trace gate recognises
    forms = _metric_forms(12_300_000_000.0, "USD", "circulating_supply", "ZYX")
    assert "$12.30B" in forms


def test_deterministic():
    assert build_metrics_table(FACTS) == build_metrics_table(FACTS)
    assert fill_metrics_module(SKEL, FACTS) == fill_metrics_module(SKEL, FACTS)


# --------------------------------------------------------------------------- #
# e2e on the real tracked skeleton (+ the gitignored bundle, skip if absent)
# --------------------------------------------------------------------------- #
def test_real_skeleton_metrics_filled():
    skel_path = ROOT / "references/templates/crypto_research_v3.md"
    bundle_path = ROOT / "meta/reports/usdc_20260605T211153Z.facts.json"
    skel = skel_path.read_text(encoding="utf-8")
    if not bundle_path.exists():
        pytest.skip("real USDC bundle not on disk (gitignored)")
    facts = json.loads(bundle_path.read_text(encoding="utf-8"))
    out = fill_metrics_module(skel, facts)
    # the STANDALONE injection anchor is consumed → the table is inserted EXACTLY
    # once (the anchor's prose mentions in the ANCHOR CONVENTION blockquote remain,
    # by design — they are documentation the writer drops, not injection points).
    assert out.count("**Spot metrics**") == 1
    import re as _re
    assert not _re.search(r"(?m)^<!-- MODULE: metrics -->[ \t]*$", out)  # line gone
    assert "<!-- MODULE: metrics-analysis -->" in out     # writer's dock, untouched
    for anchor in ("mechanism", "comparison-matrix", "valuation", "risk-rows",
                   "thesis-breakers", "charts"):
        assert f"<!-- MODULE: {anchor} -->" in out
    assert "**Supply momentum**" in out
    assert "**Issuer financials** (Circle · FY2025)" in out
