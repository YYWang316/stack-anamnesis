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

from dataclasses import dataclass
from datetime import date
from typing import Any, List, Mapping, Optional, Sequence, Tuple, Union

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


# --------------------------------------------------------------------------- #
# DATA-DRIVEN latest-annual selection (TD-037)
# --------------------------------------------------------------------------- #
# ``get_xbrl_value`` above answers "give me concept C at the period I name". The
# orchestrator instead needs "give me the LATEST full fiscal year present" so all
# issuer financials come from ONE consistent year — naming a fixed (fy, fp) per
# concept silently mixed years and surfaced a stale FY (masking Circle's
# swing-to-loss). ``latest_annual`` is that data-driven selector: no hardcoded
# frame / fy — it reads the concept's annual rows and picks the most recent one.
#
# "Annual" is identified by the SEC ``fp == "FY"`` tag (the annual-period marker
# the 10-K carries) — NOT by ``frame``, so it never depends on a pre-known frame
# string. A flow concept (Revenues, NetIncomeLoss) is a ~1-year DURATION
# (start→end); a stock concept (Assets, Liabilities, StockholdersEquity) is an
# INSTANT at fiscal-year-end (no ``start``). The 10-K restates prior years as
# comparatives (same period END, different ``filed``) — we pick the most recent
# period end, breaking ties on latest ``filed`` then ``accn`` (the same
# authority rule as ``get_xbrl_value``). A concept-ALIAS priority list covers
# issuers that move a metric between us-gaap concepts across years (the
# revenue-concept-switch case): the first alias that has annual data wins.
@dataclass(frozen=True)
class AnnualFact:
    """One concept's value for the latest full fiscal year present in an envelope."""

    concept: str       # the alias that actually carried the data
    taxonomy: str      # "us-gaap" / "dei"
    value: float
    unit: str          # "USD" / "shares" / …
    period_end: str    # ISO date, e.g. "2025-12-31"
    fy: str            # human label derived from period_end, e.g. "FY2025"
    form: Optional[str]
    filed: Optional[str]
    accn: Optional[str]


def _is_annual_row(row: Mapping[str, Any], kind: str) -> bool:
    """True if ``row`` is a full-fiscal-year row of the requested ``kind``.

    Annual is marked by ``fp == "FY"`` (the 10-K's annual-period tag — robust to
    absent ``frame``). ``kind="duration"`` wants a ~1-year flow span (``start`` →
    ``end``); ``kind="instant"`` wants a balance-sheet point (no ``start``).
    """
    if str(row.get("fp") or "").upper() != "FY":
        return False
    end = _parse_date(row.get("end"))
    if end is None:
        return False
    start = _parse_date(row.get("start"))
    if kind == "instant":
        return start is None
    if start is None:                       # duration needs a real span
        return False
    return (end - start).days > 300         # ~1-year, not a stub/partial


def _annual_sort_key(item: Tuple[Mapping[str, Any], str]):
    """Order annual rows: most recent period END, then latest ``filed``, ``accn``."""
    row, _unit = item
    end = _parse_date(row.get("end")) or date.min
    return (end, str(row.get("filed") or ""), str(row.get("accn") or ""))


def latest_annual(
    envelope: Mapping[str, Any],
    concept_or_aliases: Union[str, Sequence[str]],
    kind: str = "duration",
) -> Optional[AnnualFact]:
    """The latest full-fiscal-year value for a concept (or its alias priority).

    Parameters
    ----------
    concept_or_aliases : a concept name, or an ordered priority list — the first
        alias that has any annual data wins (the revenue-concept-switch case).
    kind : ``"duration"`` (flow: annual span) or ``"instant"`` (stock: year-end).

    Returns an ``AnnualFact`` for the most recent annual period present, or None
    if no alias has a usable annual row (rule 1: never throws). NB: NO hardcoded
    frame/fy — the period is whatever the data's latest annual row carries.
    """
    aliases: Tuple[str, ...] = (
        (concept_or_aliases,) if isinstance(concept_or_aliases, str)
        else tuple(concept_or_aliases)
    )
    if kind not in ("duration", "instant"):
        return None

    for concept in aliases:
        found = _concept_units(envelope, concept)
        if found is None:
            continue
        taxonomy, units = found
        rows: List[Tuple[Mapping[str, Any], str]] = []
        for unit, urows in units.items():
            if not isinstance(urows, list):
                continue
            for r in urows:
                if isinstance(r, Mapping) and _is_annual_row(r, kind):
                    rows.append((r, unit))
        if not rows:
            continue

        row, unit = max(rows, key=_annual_sort_key)
        value = row.get("val")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        end = str(row.get("end"))
        return AnnualFact(
            concept=concept, taxonomy=taxonomy, value=value, unit=unit,
            period_end=end, fy=f"FY{end[:4]}", form=row.get("form"),
            filed=row.get("filed"), accn=row.get("accn"),
        )
    return None


def extract_annual_fact(
    envelope: Mapping[str, Any],
    metric: str,
    concept_or_aliases: Union[str, Sequence[str]],
    kind: str = "duration",
) -> Optional[ExtractedValue]:
    """``latest_annual`` wrapped as an ``ExtractedValue`` for the analysis trunk.

    ``metric`` is the stable label used downstream (kept constant regardless of
    which alias matched, so the Evidence Table reads consistently). ``as_of`` is
    the fiscal PERIOD END (the period the number describes — same contract as
    ``get_xbrl_value``); the human fiscal-period label (e.g. ``"FY2025"``) is
    carried in ``provenance`` so the report reads clearly. None if no annual data.
    """
    fact = latest_annual(envelope, concept_or_aliases, kind)
    if fact is None:
        return None
    return ExtractedValue(
        metric=metric,
        value=fact.value,
        unit=fact.unit,
        source=SOURCE,
        subject=envelope.get("subject"),
        as_of=fact.period_end,          # fiscal period END, not fetched_at
        provenance={
            "taxonomy": fact.taxonomy,
            "concept": fact.concept,    # the alias that actually carried the data
            "fiscal_period": fact.fy,   # human label, e.g. "FY2025"
            "period_end": fact.period_end,
            "kind": kind,
            "form": fact.form,
            "filed": fact.filed,
            "accn": fact.accn,
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
