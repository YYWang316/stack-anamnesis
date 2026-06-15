"""Provenance v1 (TD-051) — "where each number came from".

Two facts-driven pieces of the renderer, both PURE / self-contained / no-network:
  1. a "Data Sources" footer listing the distinct human-readable sources + as-of;
  2. a native ``title`` tooltip (source company + as-of) on each UNAMBIGUOUS
     machine-traceable number in the body.

No URLs, no JS — so ④.3 ``validate_report_html`` must still pass. Subject-agnostic:
the synthetic bundle below is a made-up NON-USDC subject, so nothing is hardcoded.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from analysis_layer.render.html import render_html
from analysis_layer.render.validate import validate_report_html
from analysis_layer.render.provenance import (
    build_prov_index, data_sources_section, wrap_body_numbers,
)

ROOT = Path(__file__).resolve().parents[2]

# A synthetic NON-USDC bundle with full provenance fields (source + as_of on every
# value). Distinct sources: defillama (2026-03-10), coingecko (2026-03-09),
# sec_edgar (2025-12-31). Each value below maps to exactly ONE source → unambiguous.
PROV_FACTS = {
    "subject": "ZYX",
    "subject_type": "stablecoin",
    "metrics": [
        {"metric": "circulating_supply", "scope": "multi_chain",
         "value": 50_000_000_000.0, "unit": "USD", "source": "defillama",
         "as_of": "2026-03-10T00:00:00+00:00", "agreement": "agree",
         "confidence": "High"},
        {"metric": "price", "scope": "multi_chain", "value": 0.9988,
         "unit": "USD", "source": "coingecko", "as_of": "2026-03-09T12:00:00Z",
         "agreement": "agree", "confidence": "High"},
        {"metric": "market_cap_rank", "scope": "multi_chain", "value": 11,
         "unit": "count", "source": "coingecko", "as_of": "2026-03-09T12:00:00Z",
         "agreement": "single_source", "confidence": "Medium"},
    ],
    "supply_momentum": [
        {"window": "30d", "window_days": 30, "net_change_pct": -3.40,
         "net_change_abs": -1_750_000_000.0, "source": "defillama",
         "as_of": "2026-03-10T00:00:00+00:00", "agreement": "single_source",
         "confidence": "Medium"},
    ],
    "issuer_financials": {
        "issuer": "ZYX Corp", "fiscal_year": 2025,
        "revenues": {"value": 4_200_000_000.0, "unit": "USD",
                     "source": "sec_edgar", "as_of": "2025-12-31"},
        "net_income": {"value": -88_000_000.0, "unit": "USD",
                       "source": "sec_edgar", "as_of": "2025-12-31"},
        "assets": None, "liabilities": None, "equity": None,
    },
}

# A body that mentions the traceable numbers in PROSE + a table (table.memo, needed
# for the ④.3 design-structure check) + one untraceable figure that must stay bare.
PROV_MD = """# ZYX — provenance sample

## Part 5 — Metrics

| Metric | Value | Source |
|--------|-------|--------|
| circulating supply | $50.0B | defillama |

The float is $50.0B and the 30d slope is −3.40%; FY2025 revenue was $4.20B against
a net loss of −$88.0M. Rank is #11. An untraceable figure $777.7B should stay bare.
"""


def _spans(html: str):
    """All provenance spans → list of (title, inner_text)."""
    return re.findall(r'<span class="src" title="([^"]*)">([^<]*)</span>', html)


# --------------------------------------------------------------------------- #
# Piece 1 — Data Sources section
# --------------------------------------------------------------------------- #
def test_data_sources_section_lists_distinct_human_sources():
    section = data_sources_section(PROV_FACTS)
    assert 'class="data-sources"' in section
    assert "Data Sources" in section
    # human-readable company names (not raw slugs), distinct, with as-of dates
    assert "CoinGecko" in section and "DefiLlama" in section and "SEC EDGAR" in section
    assert "coingecko" not in section and "sec_edgar" not in section
    assert "as of 2026-03-10" in section   # defillama
    assert "as of 2026-03-09" in section   # coingecko
    assert "as of 2025-12-31" in section   # sec_edgar
    # deterministic ordering: alphabetical by display name
    assert section.index("CoinGecko") < section.index("DefiLlama") < section.index("SEC EDGAR")


def test_data_sources_date_range_when_multiple_dates():
    facts = {"metrics": [
        {"metric": "a", "value": 1.0, "unit": "USD", "source": "defillama",
         "as_of": "2026-01-01T00:00:00Z"},
        {"metric": "b", "value": 2.0, "unit": "USD", "source": "defillama",
         "as_of": "2026-02-15T00:00:00Z"},
    ]}
    section = data_sources_section(facts)
    assert "2026-01-01 – 2026-02-15" in section   # min – max range


def test_unknown_source_slug_title_cased():
    facts = {"metrics": [
        {"metric": "x", "value": 1.0, "unit": "USD", "source": "weird_source",
         "as_of": "2026-03-01T00:00:00Z"},
    ]}
    section = data_sources_section(facts)
    assert "Weird Source" in section   # title-cased fallback


def test_no_data_sources_section_when_facts_none():
    assert data_sources_section(None) == ""
    assert data_sources_section({}) == ""


# --------------------------------------------------------------------------- #
# Piece 2 — traceable-number tooltips
# --------------------------------------------------------------------------- #
def test_traceable_prose_number_wrapped_with_source_and_asof():
    html = render_html(PROV_MD, facts=PROV_FACTS)
    spans = dict((txt, title) for title, txt in _spans(html))
    # the unique circulating-supply figure → DefiLlama (+ its as-of)
    assert spans.get("$50.0B") == "DefiLlama · as of 2026-03-10"
    # SEC financials → SEC EDGAR
    assert spans.get("$4.20B") == "SEC EDGAR · as of 2025-12-31"
    assert spans.get("−$88.0M") == "SEC EDGAR · as of 2025-12-31"
    # rank → CoinGecko
    assert spans.get("#11") == "CoinGecko · as of 2026-03-09"


def test_unicode_minus_momentum_wrapped():
    """A supply-momentum percent written with the Unicode minus (−3.40%) in prose
    is matched (the index carries both ASCII and Unicode-minus variants)."""
    html = render_html(PROV_MD, facts=PROV_FACTS)
    spans = dict((txt, title) for title, txt in _spans(html))
    assert spans.get("−3.40%") == "DefiLlama · as of 2026-03-10"


def test_untraceable_number_not_wrapped():
    html = render_html(PROV_MD, facts=PROV_FACTS)
    wrapped = {txt for _, txt in _spans(html)}
    assert "$777.7B" not in wrapped         # not in the bundle → never wrapped
    assert "$777.7B" in html                # …but still present, just bare


def test_ambiguous_number_skipped_no_false_source():
    """The SAME canonical string from TWO different sources must NOT be wrapped —
    honesty over coverage (never attach a possibly-wrong source)."""
    ambig = {"subject": "ZYX", "metrics": [
        {"metric": "circulating_supply", "scope": "multi_chain",
         "value": 50_000_000_000.0, "unit": "USD", "source": "defillama",
         "as_of": "2026-03-10T00:00:00Z"},
        {"metric": "market_cap", "scope": "multi_chain",
         "value": 50_000_000_000.0, "unit": "USD", "source": "coingecko",
         "as_of": "2026-03-09T00:00:00Z"},
    ]}
    index = build_prov_index(ambig)
    # "$50.0B" maps to two distinct sources → dropped from the index entirely
    assert index is None or "$50.0B" not in index
    body = "<p>the supply is $50.0B today</p>"
    assert wrap_body_numbers(body, index) == body   # unchanged, no false source


def test_wrap_is_tag_safe_no_attribute_corruption():
    """The wrap only touches text content — never a tag/attribute. A value that
    appears in an attribute (here a contrived title) is left intact."""
    index = {"$50.0B": "DefiLlama · as of 2026-03-10"}
    body = '<span title="cost $50.0B">the float is $50.0B</span>'
    out = wrap_body_numbers(body, index)
    # the attribute value is untouched; only the text node gets a span
    assert 'title="cost $50.0B"' in out
    assert '<span class="src" title="DefiLlama · as of 2026-03-10">$50.0B</span>' in out
    assert out.count('class="src"') == 1   # the attribute occurrence was NOT wrapped


# --------------------------------------------------------------------------- #
# integration — self-containment / ④.3 / determinism / facts=None
# --------------------------------------------------------------------------- #
def test_self_contained_and_validate_passes():
    html = render_html(PROV_MD, facts=PROV_FACTS)
    # no external resource / JS — titles carry only "Company · as of DATE"
    assert "<script" not in html
    assert "http://" not in html and "https://" not in html
    assert "<link" not in html and "src=" not in html
    assert "@import" not in html and "cdn" not in html.lower()
    # ④.3 fail-closed gate still passes unchanged
    assert validate_report_html(html, facts_present=True) == []


def test_determinism():
    assert render_html(PROV_MD, facts=PROV_FACTS) == render_html(PROV_MD, facts=PROV_FACTS)
    assert build_prov_index(PROV_FACTS) == build_prov_index(PROV_FACTS)


def test_facts_none_no_provenance():
    html = render_html(PROV_MD)   # no facts
    assert 'class="data-sources"' not in html
    assert '<span class="src"' not in html
    assert build_prov_index(None) is None
    assert wrap_body_numbers("the float is $50.0B", None) == "the float is $50.0B"
    assert validate_report_html(html, facts_present=False) == []


def test_subject_agnostic_no_usdc_leak():
    """ZYX's values drive the provenance; no USDC literal appears."""
    html = render_html(PROV_MD, facts=PROV_FACTS)
    assert "Circle" not in html and "USDC" not in html
    assert "$50.0B" in html   # ZYX's own number is the one traced


# --------------------------------------------------------------------------- #
# e2e on the real LLM sample (skips when the gitignored artifacts are absent)
# --------------------------------------------------------------------------- #
def test_real_sample_provenance_and_validate():
    md_path = ROOT / "meta/reports/usdc_v3_llm_20260612T192215Z.report.md"
    facts_path = ROOT / "meta/reports/usdc_20260605T211153Z.facts.json"
    if not md_path.exists() or not facts_path.exists():
        pytest.skip("real USDC sample / bundle not on disk (gitignored)")
    md = md_path.read_text(encoding="utf-8")
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    html = render_html(md, facts=facts)
    # Data Sources footer + at least one wrapped number, and ④.3 still clean
    assert 'class="data-sources"' in html
    assert html.count('<span class="src" ') > 0
    assert validate_report_html(html, facts_present=True) == []
