"""analysis_layer/bundle.py — the FACTS BUNDLE (B.2.12, TD-041).

Step ① of the LLM report-writer chain. The orchestrator already turns a fetched
subject into reconciled, provenance-carrying facts; this module packs those
DETERMINISTIC facts into one clean, self-contained "facts folder" (a JSON-
serialisable dict) for a downstream report-writer to read — FACTS ONLY, no
analysis and no prose.

WHY a separate artifact from the .md
------------------------------------------------------------------------------
The markdown report is the canonical human deliverable; it interleaves the
filled numbers with the template's narrative scaffolding and its honest
``[MANUAL]`` / ``UNFILLED`` flags. A report-writer LLM should NOT have to scrape
numbers back out of that prose — it should be handed the numbers directly, each
with its provenance (source + as_of + agreement), and nothing else. So the
bundle is:

  * FACTS ONLY — every entry is a reconciled number or an identifier, each with
    its source and timestamp. No sentences, no template scaffolding, no
    ``[MANUAL]`` placeholder text, no derived verdicts (CONFIRMATION/DIVERGENCE
    is the writer's call, not a fact).
  * STABLE snake_case field names + deterministic ordering (lists pre-sorted,
    dict keys serialised sorted) — same input -> byte-identical JSON.
  * PURE — typed objects in, dict out; no I/O, no network, no wall-clock. The
    bundle content carries NO generation timestamp (only the on-disk filename
    does, mirroring the .md), so determinism holds.

The orchestrator wires this behind ``research(..., bundle=True)`` / ``--bundle``,
writing ``<slug>_<utc>.facts.json`` NEXT TO the ``.md``; the ``.md`` stays the
canonical artifact and the bundle defaults OFF.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence

from analysis_layer.contract import ReconciledValue, SubjectRef

SCHEMA = "stack_anamnesis.facts_bundle/v1"

# agreement -> confidence label. Mirrors the filler's H/M/L scale
# (analysis_layer/fillers/fill.py ``_CONFIDENCE``) so the bundle's confidence
# matches the report's Evidence Table exactly — kept local to keep this module
# free of the prose-building filler's notes.
_CONFIDENCE: Dict[str, str] = {
    "agree": "High",
    "single_source": "Medium",
    "divergence": "Low",
}

# SEC us-gaap concept -> the bundle's stable snake_case key for issuer financials.
# Names match the orchestrator's ``_SEC_FACTS`` concepts (the only ones extracted).
_FINANCIAL_KEYS: Dict[str, str] = {
    "Revenues": "revenues",
    "NetIncomeLoss": "net_income",
    "Assets": "assets",
    "Liabilities": "liabilities",
    "StockholdersEquity": "equity",
}

_SUPPLY_CHANGE_PREFIX = "net_supply_change_"
_SEC_SOURCE = "sec_edgar"


def _confidence(agreement: str) -> str:
    return _CONFIDENCE.get(agreement, "Unknown")


def _scope_key(rv: ReconciledValue) -> str:
    """A sort key for scope that puts ``None`` first deterministically."""
    return rv.scope or ""


def _dedup(reconciled, supply_change) -> List[ReconciledValue]:
    """One pooled, de-duplicated list of the caller's reconciled + supply_change.

    The orchestrator passes the base reconciled facts and the supply-change
    derivations as two lists. We pool them and drop duplicates (keyed by
    metric/scope/source) so that even if a caller hands the already-merged list
    in BOTH slots no fact is double-counted — the classification below then
    routes each to its section.
    """
    seen = set()
    pool: List[ReconciledValue] = []
    for rv in list(reconciled or ()) + list(supply_change or ()):
        key = (rv.metric, rv.scope, rv.source_used)
        if key in seen:
            continue
        seen.add(key)
        pool.append(rv)
    return pool


def _metric_entry(rv: ReconciledValue) -> Dict[str, Any]:
    """One reconciled spot metric, with provenance — no prose."""
    return {
        "metric": rv.metric,
        "scope": rv.scope,
        "value": rv.value,
        "unit": rv.unit,
        "source": rv.source_used,
        "as_of": rv.as_of,
        "agreement": rv.agreement,
        "confidence": _confidence(rv.agreement),
    }


def _momentum_entry(rv: ReconciledValue) -> Dict[str, Any]:
    """One supply-momentum window, flattened from the derivation's audit trail."""
    audit = rv.audit if isinstance(rv.audit, Mapping) else {}
    window = rv.metric[len(_SUPPLY_CHANGE_PREFIX):]  # "7d" / "30d" / "90d"
    return {
        "window": window,
        "window_days": audit.get("window_days"),
        "actual_days": audit.get("actual_days"),
        "net_change_pct": rv.value,            # signed percent POINTS (e.g. +0.24)
        "net_change_abs": audit.get("abs_change"),  # signed, series unit (USD-peg)
        "abs_unit": "USD",
        "direction": audit.get("direction"),
        "then_date": audit.get("then_date"),
        "now_date": audit.get("now_date"),
        "source": rv.source_used,
        "as_of": rv.as_of,
        "agreement": rv.agreement,
        "confidence": _confidence(rv.agreement),
    }


def _issuer_financials(rows: Sequence[ReconciledValue]) -> Optional[Dict[str, Any]]:
    """The issuer's regulated SEC financials, or ``None`` when none were extracted.

    Each mapped fact carries its own value/unit/source/as_of (provenance). The
    ``fiscal_year`` is the latest year present across the facts — by TD-037 the
    orchestrator already selects ONE consistent fiscal year, so they agree; we
    take ``max`` defensively rather than assume.
    """
    if not rows:
        return None
    facts: Dict[str, Any] = {}
    years: List[int] = []
    for rv in rows:
        key = _FINANCIAL_KEYS.get(rv.metric)
        if key is None:
            continue
        facts[key] = {
            "value": rv.value,
            "unit": rv.unit,
            "source": rv.source_used,
            "as_of": rv.as_of,
        }
        if isinstance(rv.as_of, str) and len(rv.as_of) >= 4 and rv.as_of[:4].isdigit():
            years.append(int(rv.as_of[:4]))
    if not facts:
        return None
    out: Dict[str, Any] = {"issuer": None, "fiscal_year": max(years) if years else None}
    out.update(facts)
    return out


def build_facts_bundle(
    subject_ref: SubjectRef,
    reconciled: Sequence[ReconciledValue],
    supply_change: Sequence[ReconciledValue] = (),
    *,
    sources_loaded: Sequence[str] = (),
) -> Dict[str, Any]:
    """Pack reconciled facts into a JSON-serialisable, prose-free facts bundle.

    PURE + deterministic — same inputs produce a byte-identical bundle (see
    :func:`serialize_bundle`). Carries ONLY facts: the subject + its identifiers,
    every reconciled spot metric with provenance, the supply-momentum windows,
    the issuer's SEC financials (when present), and the list of contributing
    sources. NEVER any analysis, prose, derived verdict, or ``[MANUAL]`` text.

    Parameters
    ----------
    subject_ref:
        The resolved subject bindings (subject, type, issuer, decimals, ids).
    reconciled:
        The aggregator's reconciled spot facts (price, supply, market cap, plus
        the issuer's SEC financials).
    supply_change:
        The supply-momentum derivations (``net_supply_change_{7,30,90}d``). May
        be empty (a subject with no historical series).
    sources_loaded:
        Source slugs that contributed envelopes this run.
    """
    pool = _dedup(reconciled, supply_change)

    momentum_rows: List[ReconciledValue] = []
    financial_rows: List[ReconciledValue] = []
    metric_rows: List[ReconciledValue] = []
    for rv in pool:
        if rv.metric.startswith(_SUPPLY_CHANGE_PREFIX):
            momentum_rows.append(rv)
        elif rv.source_used == _SEC_SOURCE and rv.metric in _FINANCIAL_KEYS:
            financial_rows.append(rv)
        else:
            metric_rows.append(rv)

    metrics = sorted(
        (_metric_entry(rv) for rv in metric_rows),
        key=lambda e: (e["metric"], e["scope"] or ""),
    )
    supply_momentum = sorted(
        (_momentum_entry(rv) for rv in momentum_rows),
        key=lambda e: (e["window_days"] if e["window_days"] is not None else 0, e["window"]),
    )
    financials = _issuer_financials(financial_rows)
    if financials is not None:
        financials["issuer"] = subject_ref.issuer

    identifiers = {
        str(k): v for k, v in (subject_ref.identifiers or {}).items()
    }

    return {
        "schema": SCHEMA,
        "subject": subject_ref.subject,
        "subject_type": subject_ref.subject_type,
        "issuer": subject_ref.issuer,
        "decimals": subject_ref.decimals,
        "contract": identifiers.get("eth_contract"),
        "chain": identifiers.get("eth_chain"),
        "identifiers": identifiers,
        "sources": sorted(set(sources_loaded)),
        "metrics": metrics,
        "supply_momentum": supply_momentum,
        "issuer_financials": financials,
    }


def serialize_bundle(bundle: Mapping[str, Any]) -> str:
    """The canonical byte form of a bundle: sorted keys, 2-space indent, UTF-8.

    ``sort_keys`` makes the object key order deterministic regardless of the
    build's insertion order; the lists are already pre-sorted in
    :func:`build_facts_bundle`. A trailing newline keeps it a tidy text file.
    """
    return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
