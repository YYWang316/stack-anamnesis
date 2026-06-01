"""Extractor for SEC EDGAR XBRL company-facts envelopes
(tools/fetchers/sec_edgar_fetch.py).

Envelope shape (verified against meta/raw/sec_edgar/*.json, TD-023):

    {
      "subject": "Circle",
      "subject_type": "stablecoin_issuer",
      "fetched_at": "2026-05-27T15:23:18.369072+00:00",
      "raw_response": {
        "submissions":  {... filings.recent columnar arrays ...},
        "companyfacts": {
          "cik": ..., "entityName": ...,
          "facts": {
            "us-gaap": {"<Concept>": {"label": ..., "units": {
                "USD": [ {start,end,val,fy,fp,form,frame,accn,filed}, ... ]
            }}},
            "dei": {...}
          }
        }
      }
    }

All functions here are pure (rule 3): envelope in, typed value out, no I/O.
Every hop is null-guarded (rule 1): a missing concept / units / matching row
returns None, never throws.

----------------------------------------------------------------------------
TD-023 divergence — why we DON'T filter on the literal ``fy``/``fp`` fields
----------------------------------------------------------------------------
In SEC company-facts each data point's ``fy``/``fp`` is the fiscal year/period
of the *filing that reported it*, NOT the period the number describes. A FY2025
10-K restates CY2023 and CY2024 as comparatives, so all three annual-revenue
rows in that filing carry ``fy=2025, fp="FY", form="10-K"``. Naive
``row["fy"] == fy`` filtering would therefore return three different periods for
one (fy, fp) request and break the "one reconcilable value out" contract.

SEC's canonical period key is the ``frame`` field — the same key its /frames
API uses: ``CY2025`` (annual duration), ``CY2025Q3`` (discrete quarter),
``CY2024Q4I`` (instant / balance-sheet at period end). We therefore interpret
the (fy, fp) arguments as *the period the caller wants* and resolve them to a
frame, not to the literal fy/fp tag. ``frame`` also cleanly distinguishes the
discrete quarter a caller means (``CY2025Q3``) from the year-to-date
cumulative row that shares ``fp="Q3"`` but carries ``frame=None``.

A documented geometry fallback (period dates, no frame) covers rows whose
``frame`` is absent; see ``_period_matches``.
"""
from __future__ import annotations

from datetime import date
from typing import Any, List, Mapping, Optional

from analysis_layer.contract import ExtractedValue

SOURCE = "sec_edgar"

# Taxonomies searched, in priority order, when locating a concept.
_TAXONOMIES = ("us-gaap", "dei")


# --------------------------------------------------------------------------- #
# envelope navigation helpers (each hop null-guarded — rule 1)
# --------------------------------------------------------------------------- #
def _facts(envelope: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return ``raw_response.companyfacts.facts`` or None if any hop missing."""
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return None
    cf = raw.get("companyfacts")
    if not isinstance(cf, Mapping):
        return None
    facts = cf.get("facts")
    return facts if isinstance(facts, Mapping) else None


def _concept_units(
    envelope: Mapping[str, Any], concept: str
) -> Optional[tuple]:
    """Find ``concept`` across taxonomies; return ``(taxonomy, units_map)``.

    Returns None if facts, the concept, or its ``units`` map are absent /
    malformed. ``units_map`` is ``{unit_str: [row, ...]}`` (e.g. ``"USD"``,
    ``"shares"``, ``"USD/shares"``).
    """
    facts = _facts(envelope)
    if facts is None:
        return None
    for tax in _TAXONOMIES:
        block = facts.get(tax)
        if not isinstance(block, Mapping):
            continue
        node = block.get(concept)
        if not isinstance(node, Mapping):
            continue
        units = node.get("units")
        if isinstance(units, Mapping) and units:
            return tax, units
    return None


def _parse_date(value: Any) -> Optional[date]:
    """ISO ``YYYY-MM-DD`` -> date, else None. Never throws."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# period matching
# --------------------------------------------------------------------------- #
def _expected_frames(fy: int, fp: str) -> tuple:
    """Frame strings a (fy, fp) request can resolve to.

    ``fp`` is normalised upper-case. Both the duration and the instant
    (balance-sheet) variant are returned because the caller does not know
    whether the concept is a flow (Revenues -> duration) or a stock
    (Assets -> instant); only one will exist for a given concept.

    NB: frames use *calendar* year (``CY``). For a calendar-fiscal-year filer
    (Circle, fiscalYearEnd=1231) ``fy`` == calendar year. A non-calendar filer
    would need fy->calendar mapping; out of scope for the envelopes we hold.
    """
    fp = fp.upper()
    if fp == "FY":
        # annual duration -> CY{fy}; fiscal-year-end instant -> CY{fy}Q4I
        return (f"CY{fy}", f"CY{fy}Q4I")
    # quarterly: discrete-quarter duration + the period-end instant
    return (f"CY{fy}{fp}", f"CY{fy}{fp}I")


def _period_matches(row: Mapping[str, Any], fy: int, fp: str) -> bool:
    """Geometry fallback when ``frame`` is absent.

    Matches on the row's actual ``start``/``end`` dates so a value with no
    frame (older / amended filings) is still findable. Critically, for
    quarters it distinguishes the *discrete* quarter (~3 months) from the
    year-to-date cumulative row (>~4 months) that shares the same ``fp`` —
    otherwise a "Q3" request would wrongly pick up the 9-month YTD figure.
    """
    fp = fp.upper()
    end = _parse_date(row.get("end"))
    if end is None or end.year != fy:
        return False
    start = _parse_date(row.get("start"))
    if start is None:
        # instant (balance-sheet) row: end date in fy is enough.
        return True
    span = (end - start).days
    if fp == "FY":
        return span > 300  # full-year duration
    return 60 <= span <= 100  # discrete quarter (~91d), not YTD cumulative


def _select_period_rows(
    rows: List[Mapping[str, Any]], unit: str, fy: int, fp: str
) -> List[tuple]:
    """Rows (paired with their unit) matching the requested period.

    PRIMARY: SEC ``frame`` match (precise, canonical). FALLBACK (only if no
    frame matched anywhere): period-geometry match. The fallback runs only
    when frames are entirely absent for the period so we never mix a YTD row
    in alongside a clean frame match.
    """
    wanted = _expected_frames(fy, fp)
    framed = [(r, unit) for r in rows if r.get("frame") in wanted]
    if framed:
        return framed
    return [(r, unit) for r in rows if _period_matches(r, fy, fp)]


def _authoritative(matched: List[tuple]) -> Optional[tuple]:
    """Dedup rows sharing a period across filings; return the authoritative one.

    Rule: latest ``filed`` date, then highest ``accn`` as tiebreak. Rationale:
    the same economic period (e.g. CY2024 year-end Assets) is reported in the
    original filing AND restated as a comparative in later filings; the most
    recently filed report carries the most current / audited / restated figure
    and supersedes earlier ones. ISO ``filed`` strings sort correctly
    lexicographically. ``accn`` (e.g. ``0001876042-26-000062``) embeds an
    incrementing sequence, a stable tiebreak when two rows share a filed date.
    """
    if not matched:
        return None

    def _key(item: tuple):
        row = item[0]
        return (str(row.get("filed") or ""), str(row.get("accn") or ""))

    return max(matched, key=_key)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def get_xbrl_value(
    envelope: Mapping[str, Any],
    concept: str,
    fy: int,
    fp: str,
    form: Optional[str] = None,
) -> Optional[ExtractedValue]:
    """Extract one XBRL fact for ``concept`` at fiscal period (``fy``, ``fp``).

    Parameters
    ----------
    concept : us-gaap / dei concept, e.g. ``"Revenues"``, ``"Assets"``.
    fy, fp  : the period the caller wants — ``fp`` is ``"FY"`` (annual) or
              ``"Q1".."Q4"`` (discrete quarter). Resolved to a SEC ``frame``;
              NOT matched against the literal fy/fp filing tags (see module
              docstring, TD-023).
    form    : optional hard filter on the source form (``"10-K"`` / ``"10-Q"``).
              When given and no matching-period row has that form -> None.

    Returns an ``ExtractedValue`` on success, or None if the concept / units
    are absent or no row matches the period (+ form). Never throws (rule 1).

    as_of design (adaptation of the live-snapshot Alchemy contract): for a
    financial fact the timestamp the value *reflects* is the fiscal PERIOD END
    (the ``end`` field), NOT the envelope fetch time. Reconciling "FY2025
    revenue" across sources must align on the period the number describes, so
    ``as_of`` carries the period end. The filing date and the envelope's
    ``fetched_at`` are preserved in ``provenance`` for the audit trail.
    """
    found = _concept_units(envelope, concept)
    if found is None:
        return None
    taxonomy, units = found

    matched: List[tuple] = []
    for unit, rows in units.items():
        if not isinstance(rows, list):
            continue
        period_rows = _select_period_rows(rows, unit, fy, fp)
        if form is not None:
            period_rows = [pr for pr in period_rows if pr[0].get("form") == form]
        matched.extend(period_rows)

    chosen = _authoritative(matched)
    if chosen is None:
        return None
    row, unit = chosen

    value = row.get("val")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    return ExtractedValue(
        metric=concept,
        value=value,
        unit=unit,  # actual unit key: "USD" / "shares" / "USD/shares"
        source=SOURCE,
        subject=envelope.get("subject"),
        as_of=row.get("end"),  # fiscal period END, not fetched_at — see above
        provenance={
            "taxonomy": taxonomy,
            "concept": concept,
            "fy": fy,
            "fp": fp.upper(),
            "form": row.get("form"),
            "start": row.get("start"),
            "end": row.get("end"),
            "accn": row.get("accn"),
            "frame": row.get("frame"),
            "filed": row.get("filed"),
            "unit": unit,
            "dedup_candidates": len(matched),
            "fetched_at": envelope.get("fetched_at"),
        },
    )


def list_filings(
    envelope: Mapping[str, Any], form: Optional[str] = None
) -> List[Mapping[str, Any]]:
    """Filing descriptors from ``raw_response.submissions.filings.recent``.

    Returns a list of ``{accn, form, filed, report}`` dicts, optionally
    filtered to ``form``. Returns ``[]`` (not None) if submissions / the
    columnar arrays are absent or malformed — a filing *list* naturally
    degrades to empty, unlike a scalar value which degrades to None (rule 1).

    ``filings.recent`` is columnar (parallel arrays keyed by field); a
    ``filings.files`` overflow page can exist for very prolific filers and is
    NOT walked here (it points at separate JSON not embedded in the envelope).
    """
    raw = envelope.get("raw_response")
    if not isinstance(raw, Mapping):
        return []
    sub = raw.get("submissions")
    if not isinstance(sub, Mapping):
        return []
    filings = sub.get("filings")
    if not isinstance(filings, Mapping):
        return []
    recent = filings.get("recent")
    if not isinstance(recent, Mapping):
        return []

    forms = recent.get("form")
    accns = recent.get("accessionNumber")
    filed = recent.get("filingDate")
    report = recent.get("reportDate")
    if not isinstance(forms, list):
        return []
    accns = accns if isinstance(accns, list) else []
    filed = filed if isinstance(filed, list) else []
    report = report if isinstance(report, list) else []

    out: List[Mapping[str, Any]] = []
    for i, f in enumerate(forms):
        if form is not None and f != form:
            continue
        out.append(
            {
                "accn": accns[i] if i < len(accns) else None,
                "form": f,
                "filed": filed[i] if i < len(filed) else None,
                "report": report[i] if i < len(report) else None,
            }
        )
    return out
