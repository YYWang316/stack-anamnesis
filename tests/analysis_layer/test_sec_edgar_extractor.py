"""Unit + real-envelope tests for analysis_layer/extractors/sec_edgar.py (B.2.1).

Covers the XBRL company-facts extractor contract: typed value on success,
None on missing concept/units/period (null-guard, rule 1), period resolution
via SEC ``frame`` (the fy/fp filing-tag is NOT a period — TD-023), dedup of a
period reported across multiple filings, and a real Circle envelope decode.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer.contract import ExtractedValue
from analysis_layer.extractors import sec_edgar

ROOT = Path(__file__).resolve().parents[2]
SEC_RAW = ROOT / "meta" / "raw" / "sec_edgar"


# --------------------------------------------------------------------------- #
# inline-mock envelope builders
# --------------------------------------------------------------------------- #
def _envelope(facts: dict, submissions: dict | None = None) -> dict:
    raw = {"companyfacts": {"cik": 1, "entityName": "Mock", "facts": facts}}
    if submissions is not None:
        raw["submissions"] = submissions
    return {
        "subject": "MockCo",
        "subject_type": "stablecoin_issuer",
        "fetched_at": "2026-05-27T15:23:18.369072+00:00",
        "raw_response": raw,
    }


def _row(start, end, val, fy, fp, form, frame, accn, filed):
    return {
        "start": start, "end": end, "val": val, "fy": fy, "fp": fp,
        "form": form, "frame": frame, "accn": accn, "filed": filed,
    }


# A concept whose USD array spans fy/fp/form, with a DUPLICATE period
# (CY2024 annual) reported in two filings: the original FY2024 10-K and a
# later restatement (10-K/A). This exercises dedup-by-period.
MOCK_FACTS = {
    "us-gaap": {
        "Revenues": {
            "label": "Revenues",
            "units": {
                "USD": [
                    # discrete Q3 2025 (what a Q3 caller means)
                    _row("2025-07-01", "2025-09-30", 739_759_000, 2025, "Q3",
                         "10-Q", "CY2025Q3", "acc-q3", "2025-11-12"),
                    # YTD 9-month 2025 — same fp="Q3" but NOT the discrete
                    # quarter; frame=None so it must NOT be picked for "Q3".
                    _row("2025-01-01", "2025-09-30", 1_976_410_000, 2025, "Q3",
                         "10-Q", None, "acc-q3", "2025-11-12"),
                    # CY2024 annual — ORIGINAL FY2024 10-K
                    _row("2024-01-01", "2024-12-31", 1_676_000_000, 2024, "FY",
                         "10-K", "CY2024", "acc-orig", "2025-03-01"),
                    # CY2024 annual — RESTATED later in a 10-K/A (same period,
                    # different filing, slightly different value + later filed)
                    _row("2024-01-01", "2024-12-31", 1_676_253_000, 2024, "FY",
                         "10-K/A", "CY2024", "acc-amend", "2026-03-09"),
                ]
            },
        }
    }
}


# --------------------------------------------------------------------------- #
# get_xbrl_value — happy path + frame/period semantics
# --------------------------------------------------------------------------- #
def test_discrete_quarter_resolved_via_frame():
    env = _envelope(MOCK_FACTS)
    ev = sec_edgar.get_xbrl_value(env, "Revenues", fy=2025, fp="Q3", form="10-Q")

    assert isinstance(ev, ExtractedValue)
    assert ev.metric == "Revenues"
    assert ev.value == 739_759_000          # discrete quarter, NOT the YTD 1.976B
    assert ev.unit == "USD"
    assert ev.source == "sec_edgar"
    assert ev.subject == "MockCo"
    # as_of is the fiscal PERIOD END, not the envelope fetched_at (TD-023 design)
    assert ev.as_of == "2025-09-30"
    assert ev.provenance["frame"] == "CY2025Q3"
    assert ev.provenance["concept"] == "Revenues"
    assert ev.provenance["fp"] == "Q3"


def test_ytd_row_not_returned_for_quarter():
    # The 9-month YTD row shares fp="Q3" but is frame=None; a "Q3" request
    # must never collapse to it.
    env = _envelope(MOCK_FACTS)
    ev = sec_edgar.get_xbrl_value(env, "Revenues", fy=2025, fp="Q3", form="10-Q")
    assert ev.value != 1_976_410_000


def test_dedup_picks_latest_filed_restatement():
    # CY2024 annual appears in two filings; authoritative = latest filed.
    env = _envelope(MOCK_FACTS)
    ev = sec_edgar.get_xbrl_value(env, "Revenues", fy=2024, fp="FY")

    assert ev.value == 1_676_253_000             # restated value
    assert ev.provenance["accn"] == "acc-amend"  # latest filed (2026-03-09)
    assert ev.provenance["filed"] == "2026-03-09"
    assert ev.provenance["dedup_candidates"] == 2


def test_form_filter_selects_original_over_restatement():
    # form is a hard filter: ask for the original 10-K, not the 10-K/A.
    env = _envelope(MOCK_FACTS)
    ev = sec_edgar.get_xbrl_value(env, "Revenues", fy=2024, fp="FY", form="10-K")
    assert ev.value == 1_676_000_000
    assert ev.provenance["accn"] == "acc-orig"


def test_instant_concept_resolved_via_q4i_frame():
    # Balance-sheet (instant) concept: FY request resolves to the CY{fy}Q4I
    # frame; start is None.
    facts = {"us-gaap": {"Assets": {"units": {"USD": [
        _row(None, "2024-12-31", 45_834_409_000, 2025, "FY", "10-K",
             "CY2024Q4I", "acc-10k", "2026-03-09"),
    ]}}}}
    ev = sec_edgar.get_xbrl_value(_envelope(facts), "Assets", fy=2024, fp="FY")
    assert ev.value == 45_834_409_000
    assert ev.as_of == "2024-12-31"
    assert ev.unit == "USD"


def test_non_usd_unit_is_surfaced():
    facts = {"us-gaap": {"EntityCommonStockSharesOutstanding": {"units": {
        "shares": [_row(None, "2025-12-31", 220_000_000, 2025, "FY", "10-K",
                        "CY2025Q4I", "acc", "2026-03-09")]
    }}}}
    ev = sec_edgar.get_xbrl_value(
        _envelope(facts), "EntityCommonStockSharesOutstanding", fy=2025, fp="FY"
    )
    assert ev.unit == "shares"          # not assumed to be USD
    assert ev.value == 220_000_000


def test_frame_none_falls_back_to_period_geometry():
    # No frame anywhere for the period -> geometry fallback finds the annual row.
    facts = {"us-gaap": {"Revenues": {"units": {"USD": [
        _row("2023-01-01", "2023-12-31", 1_450_466_000, 2025, "FY", "10-K",
             None, "acc", "2026-03-09"),
    ]}}}}
    ev = sec_edgar.get_xbrl_value(_envelope(facts), "Revenues", fy=2023, fp="FY")
    assert ev.value == 1_450_466_000


# --------------------------------------------------------------------------- #
# get_xbrl_value — null-guards (rule 1: None, never throw)
# --------------------------------------------------------------------------- #
def test_missing_concept_returns_none():
    assert sec_edgar.get_xbrl_value(
        _envelope(MOCK_FACTS), "NotAConcept", fy=2025, fp="FY"
    ) is None


def test_missing_units_returns_none():
    facts = {"us-gaap": {"Revenues": {"label": "Revenues"}}}  # no 'units'
    assert sec_edgar.get_xbrl_value(
        _envelope(facts), "Revenues", fy=2025, fp="FY"
    ) is None


def test_no_matching_period_returns_none():
    # Concept + units exist, but no row matches fy=1999.
    assert sec_edgar.get_xbrl_value(
        _envelope(MOCK_FACTS), "Revenues", fy=1999, fp="FY"
    ) is None


def test_form_filter_with_no_match_returns_none():
    assert sec_edgar.get_xbrl_value(
        _envelope(MOCK_FACTS), "Revenues", fy=2024, fp="FY", form="10-K405"
    ) is None


def test_missing_raw_response_returns_none():
    assert sec_edgar.get_xbrl_value({"subject": "x"}, "Revenues", fy=2025,
                                    fp="FY") is None


# --------------------------------------------------------------------------- #
# latest_annual — DATA-DRIVEN latest-consistent-FY selection (TD-037)
# --------------------------------------------------------------------------- #
def _annual_flow(concept, rows):
    """A facts dict for one duration concept; rows = list of (start,end,val,fp,filed,accn)."""
    return {"us-gaap": {concept: {"units": {"USD": [
        _row(s, e, v, int(e[:4]), fp, "10-K", None, a, f) for (s, e, v, fp, f, a) in rows
    ]}}}}


def _annual_instant(concept, rows):
    """A facts dict for one instant concept; rows = list of (end,val,fp,filed,accn)."""
    return {"us-gaap": {concept: {"units": {"USD": [
        _row(None, e, v, int(e[:4]), fp, "10-K", None, a, f) for (e, v, fp, f, a) in rows
    ]}}}}


def test_latest_annual_picks_most_recent_year_not_an_older_one():
    # Two annual FY rows + a quarterly row; the FY selector must return the
    # NEWEST full year (2025), never the older comparative (2024) or the quarter.
    facts = _annual_flow("Revenues", [
        ("2024-01-01", "2024-12-31", 1_676_253_000, "FY", "2026-03-09", "a24"),
        ("2025-01-01", "2025-12-31", 2_746_642_000, "FY", "2026-03-09", "a25"),
        ("2025-07-01", "2025-09-30",   739_759_000, "Q3", "2025-11-12", "aq3"),
    ])
    fact = sec_edgar.latest_annual(_envelope(facts), "Revenues", kind="duration")
    assert fact is not None
    assert fact.value == 2_746_642_000        # FY2025, not FY2024's 1.676B
    assert fact.period_end == "2025-12-31"
    assert fact.fy == "FY2025"


def test_latest_annual_flow_vs_instant():
    # A flow concept resolves as a ~1-year DURATION; an instant concept resolves
    # at the fiscal-year-end POINT (start=None). Each kind ignores the other's row.
    flow = sec_edgar.latest_annual(
        _envelope(_annual_flow("NetIncomeLoss", [
            ("2025-01-01", "2025-12-31", -69_508_000, "FY", "2026-03-09", "a25"),
        ])), "NetIncomeLoss", kind="duration")
    assert flow is not None and flow.value == -69_508_000   # the LOSS

    inst = sec_edgar.latest_annual(
        _envelope(_annual_instant("Assets", [
            ("2024-12-31", 45_834_409_000, "FY", "2026-03-09", "a24"),
            ("2025-12-31", 78_713_207_000, "FY", "2026-03-09", "a25"),
        ])), "Assets", kind="instant")
    assert inst is not None and inst.value == 78_713_207_000 and inst.period_end == "2025-12-31"

    # asking for the WRONG kind finds no matching row -> None (rule 1)
    assert sec_edgar.latest_annual(
        _envelope(_annual_instant("Assets", [
            ("2025-12-31", 78_713_207_000, "FY", "2026-03-09", "a25")])),
        "Assets", kind="duration") is None


def test_latest_annual_restatement_tie_broken_by_latest_filed():
    # Same period END (2025-12-31) reported twice; pick the latest-filed restatement.
    facts = _annual_flow("Revenues", [
        ("2025-01-01", "2025-12-31", 2_700_000_000, "FY", "2026-02-01", "orig"),
        ("2025-01-01", "2025-12-31", 2_746_642_000, "FY", "2026-03-09", "amend"),
    ])
    fact = sec_edgar.latest_annual(_envelope(facts), "Revenues", kind="duration")
    assert fact.value == 2_746_642_000        # restated
    assert fact.filed == "2026-03-09" and fact.accn == "amend"


def test_latest_annual_concept_alias_priority():
    # Revenue under alias A (FY2025) and alias B (FY2024). First alias WITH data
    # wins -> A's FY2025, even though B exists.
    facts = {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _row("2025-01-01", "2025-12-31", 2_746_642_000, 2025, "FY", "10-K",
                 None, "aA", "2026-03-09")]}},
        "Revenues": {"units": {"USD": [
            _row("2024-01-01", "2024-12-31", 1_676_253_000, 2024, "FY", "10-K",
                 None, "aB", "2025-03-01")]}},
    }}
    fact = sec_edgar.latest_annual(
        _envelope(facts),
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
        kind="duration")
    assert fact.value == 2_746_642_000
    assert fact.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert fact.fy == "FY2025"

    # first alias absent -> falls through to the next alias that HAS data
    fact2 = sec_edgar.latest_annual(
        _envelope(facts), ("NotAConcept", "Revenues"), kind="duration")
    assert fact2 is not None and fact2.concept == "Revenues"


def test_latest_annual_missing_concept_returns_none():
    assert sec_edgar.latest_annual(_envelope(MOCK_FACTS), "NotAConcept") is None
    assert sec_edgar.latest_annual({"subject": "x"}, "Revenues") is None
    # bad kind -> None, never throws
    assert sec_edgar.latest_annual(_envelope(MOCK_FACTS), "Revenues", kind="bogus") is None


def test_extract_annual_fact_wraps_as_extracted_value():
    facts = _annual_instant("StockholdersEquity", [
        ("2024-12-31",   570_529_000, "FY", "2026-03-09", "a24"),
        ("2025-12-31", 3_329_327_000, "FY", "2026-03-09", "a25"),
    ])
    ev = sec_edgar.extract_annual_fact(
        _envelope(facts), "StockholdersEquity", "StockholdersEquity", kind="instant")
    assert isinstance(ev, ExtractedValue)
    assert ev.metric == "StockholdersEquity"          # stable label
    assert ev.value == 3_329_327_000                  # FY2025, not FY2024's 570.5M
    assert ev.as_of == "2025-12-31"                   # period END
    assert ev.provenance["fiscal_period"] == "FY2025"
    assert ev.provenance["kind"] == "instant"
    # no annual data -> None
    assert sec_edgar.extract_annual_fact(
        _envelope(facts), "X", "NotAConcept", kind="instant") is None


# --------------------------------------------------------------------------- #
# latest_annual — real Circle envelope (the GROUND-TRUTH FY2025 anchor, TD-037)
# --------------------------------------------------------------------------- #
def test_real_envelope_latest_annual_is_fy2025_consistent():
    env = _latest_circle_envelope()
    specs = [
        ("Revenues", ("Revenues",), "duration", 2_746_642_000),
        ("NetIncomeLoss", ("NetIncomeLoss",), "duration", -69_508_000),
        ("Assets", ("Assets",), "instant", 78_713_207_000),
        ("Liabilities", ("Liabilities",), "instant", 75_382_434_000),
        ("StockholdersEquity", ("StockholdersEquity",), "instant", 3_329_327_000),
    ]
    for metric, aliases, kind, expected in specs:
        fact = sec_edgar.latest_annual(env, aliases, kind=kind)
        assert fact is not None, metric
        assert fact.value == expected, f"{metric}: {fact.value} != {expected}"
        assert fact.period_end == "2025-12-31", metric   # all the SAME latest year
        assert fact.fy == "FY2025", metric


# --------------------------------------------------------------------------- #
# list_filings
# --------------------------------------------------------------------------- #
def test_list_filings_filters_by_form():
    submissions = {"filings": {"recent": {
        "form": ["10-K", "10-Q", "8-K", "10-Q"],
        "accessionNumber": ["a1", "a2", "a3", "a4"],
        "filingDate": ["2026-03-09", "2026-05-11", "2026-05-18", "2025-11-12"],
        "reportDate": ["2025-12-31", "2026-03-31", "", "2025-09-30"],
    }, "files": []}}
    env = _envelope({}, submissions=submissions)

    tenq = sec_edgar.list_filings(env, form="10-Q")
    assert [f["accn"] for f in tenq] == ["a2", "a4"]
    assert tenq[0] == {"accn": "a2", "form": "10-Q",
                       "filed": "2026-05-11", "report": "2026-03-31"}
    # no filter -> all
    assert len(sec_edgar.list_filings(env)) == 4


def test_list_filings_missing_submissions_returns_empty():
    # Degrades to [] (a list), not None — rule 1 for a collection result.
    assert sec_edgar.list_filings(_envelope({})) == []
    assert sec_edgar.list_filings({"subject": "x"}) == []


# --------------------------------------------------------------------------- #
# real Circle envelope
# --------------------------------------------------------------------------- #
def _latest_circle_envelope() -> dict:
    candidates = sorted(SEC_RAW.glob("*.json"), reverse=True)
    for path in candidates:
        env = json.loads(path.read_text())
        facts = (
            env.get("raw_response", {})
            .get("companyfacts", {})
            .get("facts", {})
        )
        if "us-gaap" in facts:
            return env
    pytest.skip("no SEC EDGAR company-facts envelope found on disk")


def test_real_envelope_fy2025_revenue():
    # Verified against the on-disk envelope: Circle FY2025 (CY2025) revenue
    # from the 10-K (accn 0001876042-26-000062, filed 2026-03-09).
    env = _latest_circle_envelope()
    ev = sec_edgar.get_xbrl_value(env, "Revenues", fy=2025, fp="FY", form="10-K")

    assert ev is not None
    assert ev.value == 2_746_642_000
    assert ev.unit == "USD"
    assert ev.source == "sec_edgar"
    assert ev.as_of == "2025-12-31"          # period end, not fetched_at
    assert ev.provenance["frame"] == "CY2025"
    assert ev.provenance["accn"] == "0001876042-26-000062"


def test_real_envelope_assets_dedup_across_filings():
    # Assets at 2024-12-31 (instant) is reported in three filings (Q2/Q3 10-Q
    # comparatives + the FY 10-K). With no form filter, dedup must pick the
    # authoritative (latest-filed) row, and all carry the same value.
    env = _latest_circle_envelope()
    ev = sec_edgar.get_xbrl_value(env, "Assets", fy=2024, fp="FY")

    assert ev is not None
    assert ev.value == 45_834_409_000
    assert ev.as_of == "2024-12-31"


def test_real_envelope_list_filings_has_periodic_reports():
    env = _latest_circle_envelope()
    tenk = sec_edgar.list_filings(env, form="10-K")
    assert any(f["accn"] == "0001876042-26-000062" for f in tenk)
    assert all(f["form"] == "10-K" for f in tenk)
