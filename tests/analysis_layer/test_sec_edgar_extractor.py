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
