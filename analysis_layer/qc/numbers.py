"""analysis_layer/qc/numbers.py — the NUMBERS-TRACE gate (⑤.1, TD-048).

The first concrete piece of ⑤ (the content-honesty layer) and DISTINCT from ④.3
(``render/validate.py``, HTML integrity): this gate never looks at the document's
structure — it checks that every MACHINE-PRODUCED number (the deterministic facts
bundle, TD-041 ①) survives UNCHANGED into the FINAL, agent-written report. The
writer is an LLM given freedom to write prose; this is the fail-closed backstop
that the prose did not silently alter or drop a number the data layer produced.

PURE, stdlib-only, no-network, deterministic: same ``(report_md, facts)`` in ->
same violations out. ``[]`` == clean.

WHAT IT GUARANTEES (a FLOOR, not a ceiling)
------------------------------------------------------------------------------
For each non-null, machine-authoritative bundle value, at least one of its
canonical renderings is PRESENT in the report. A value that was dropped, or
altered beyond a legitimate rounding (e.g. a writer turning -1.62% into -1.6%, or
$76.5B into $7.65B), appears in NONE of its canonical forms -> flagged.

WHAT IT DOES NOT DO (deferred to TD-049, the red-team / third-source half)
------------------------------------------------------------------------------
It does not catch a *contradicting* number the writer invents elsewhere in prose,
and it does not police MANUAL / narrative numbers (there is no machine value to
trace). It is a presence floor, not a full numeric audit.

SUBJECT-AGNOSTIC (like ④.2): the gate is driven entirely off the bundle's FIELD
NAMES and unit tags — never a USDC literal or a hard-coded subject. A non-USDC
bundle traces ITS own values.

★ FORMATTING PARITY / DEVIATION (TD-023 — verify reality before coding)
------------------------------------------------------------------------------
The brief said to "reuse the filler's formatting (-1.62%, $2.75B, $76.5B)" so the
expected string matches the report. Inspecting reality, TWO conventions actually
coexist in the deliverable, and NEITHER alone makes the real report pass:

  * the FILLER (``fill.render_value`` / the momentum sub-bullets) emits a value
    with 2 decimals after the point — ``$0.9997``, ``52.57B USDC``, ``-1.62%``,
    ``+$180.93M`` — but ONLY for the metrics it renders into a scaffold sub-bullet
    (total_supply, price, supply-momentum). Spot metrics with no [AUTO] slot
    (circulating_supply USD, market_cap, volume) and the SEC financials live ONLY
    as RAW numbers in the Evidence Table;
  * the WRITER, taking those raw numbers into prose, renders them at 3
    SIGNIFICANT FIGURES — ``$76.5B``, ``$78.7B``, ``$2.75B``, ``-$69.5M`` — which
    is what the brief's own ``$76.5B`` example actually is (NOT what
    ``render_value`` produces for that value, which is ``$76.48B``).

So a single "canonical" string can't pass a faithful report. The gate therefore
treats a value as traced when ANY of its canonical renderings is present: the
filler's exact ``render_value`` form AND the 3-significant-figure magnitude form
(both sharing the filler's own T/B/M/K magnitude system, reused from ``fill``),
with sign-placement variants for negatives and Unicode-minus normalised. This
keeps the real report passing with ZERO false positives while staying a strict
floor — an actually-altered number lands on none of the accepted forms. The
precise, discriminating supply-momentum percent stays pinned to the filler's
exact ``{:+.2f}%`` form, so the brief's required ``-1.62% -> -1.6%`` alteration is
still caught.
"""
from __future__ import annotations

import argparse
import json
import sys
from types import SimpleNamespace
from typing import Any, List, Mapping, Optional, Set

from analysis_layer.fillers.fill import _magnitude, _signed_usd, render_value

# Bundle keys under ``issuer_financials`` that are provenance, not a traced value.
_FINANCIAL_META_KEYS = frozenset({"issuer", "fiscal_year"})

# Characters the writer's prose uses that the filler's ASCII rendering does not:
# the Unicode MINUS SIGN (U+2212) and NON-BREAKING SPACE. Normalised in the report
# before matching so an expected ``-$69.5M`` matches a prose ``−$69.5M``.
_NORMALISE = {"−": "-", " ": " "}


def _normalise(text: str) -> str:
    for src, dst in _NORMALISE.items():
        text = text.replace(src, dst)
    return text


# --------------------------------------------------------------------------- #
# canonical renderings — reuse the filler's magnitude system for parity
# --------------------------------------------------------------------------- #
def _three_sig(value: float) -> "tuple[str, str]":
    """A value rendered to 3 significant figures within the filler's magnitude
    band — ``(body, suffix)``, e.g. ``("76.5", "B")`` / ``("181", "M")``. Reuses
    ``fill._magnitude`` so the T/B/M/K suffix matches the filler exactly; this is
    the convention the WRITER uses for numbers that have no filler-rendered slot.
    """
    scaled, suffix = _magnitude(value)
    a = abs(scaled)
    if a >= 100:
        body = f"{scaled:.0f}"
    elif a >= 10:
        body = f"{scaled:.1f}"
    else:
        body = f"{scaled:.2f}"
    return body, suffix


def _render_value_form(value: float, unit: str, metric: str, subject: str) -> str:
    """The filler's EXACT rendering of a value (reused, not re-implemented)."""
    rv = SimpleNamespace(value=value, unit=unit, metric=metric)
    return _normalise(render_value(rv, SimpleNamespace(subject=subject)))


def _usd_forms(value: float) -> Set[str]:
    """Canonical USD renderings of a spot value / financial cell.

    Sub-$1000 (price-like) values render at the filler's 4 decimals only. Larger
    values accept BOTH the filler's 2-decimal magnitude form and the writer's
    3-significant-figure form, in both sign placements for negatives.
    """
    forms = {_render_value_form(value, "USD", "", "")}
    if abs(value) < 1000:
        return forms
    body, suffix = _three_sig(value)
    mag = body.lstrip("-")
    if value < 0:
        forms.add(f"-${mag}{suffix}")
        forms.add(f"$-{mag}{suffix}")
    else:
        forms.add(f"${mag}{suffix}")
    return forms


def _token_forms(value: float, subject: str) -> Set[str]:
    """Canonical token-count renderings — the filler's exact form plus the 3-sig
    form, each tagged with the subject symbol (subject-agnostic)."""
    forms = {_render_value_form(value, "tokens", "", subject)}
    if abs(value) < 1000:
        return forms
    body, suffix = _three_sig(value)
    forms.add(f"{body.lstrip('-')}{suffix} {subject}".rstrip())
    return forms


def _signed_usd_forms(value: float) -> Set[str]:
    """Canonical renderings of a SIGNED USD delta (the supply-momentum abs change).

    The filler renders these with the sign BEFORE the ``$`` (``+$180.93M`` /
    ``-$1.26B``) via ``fill._signed_usd`` — reused here — plus the 3-sig form.
    """
    forms = {_normalise(_signed_usd(value))}
    body, suffix = _three_sig(value)
    sign = "+" if value >= 0 else "-"
    forms.add(f"{sign}${body.lstrip('-')}{suffix}")
    return forms


def _metric_forms(value: Any, unit: str, metric: str, subject: str) -> Set[str]:
    """Canonical renderings for one spot metric, dispatched on its unit."""
    if unit == "count" or metric == "market_cap_rank":
        return {f"#{int(value)}"}
    if unit == "USD":
        return _usd_forms(float(value))
    if unit == "tokens":
        return _token_forms(float(value), subject)
    # Unknown unit -> trust the filler's faithful "value unit" rendering.
    return {_render_value_form(value, unit, metric, subject)}


def _present(forms: Set[str], report: str) -> bool:
    return any(f and f in report for f in forms)


def _show(forms: Set[str]) -> str:
    return " / ".join(sorted(forms))


# --------------------------------------------------------------------------- #
# the check
# --------------------------------------------------------------------------- #
def check_numbers_trace(report_md: str, facts: Mapping[str, Any]) -> List[str]:
    """Trace every machine-produced bundle number into ``report_md``. PURE.

    Returns a list of human-readable violations (one per value that survived in
    NONE of its canonical forms); ``[]`` means every machine value is present.
    Null bundle cells are skipped (no machine value to trace); MANUAL / narrative
    numbers are out of scope (deferred to TD-049). Subject-agnostic: driven off
    the bundle's field names + unit tags, never a hard-coded subject or literal.
    """
    report = _normalise(report_md)
    subject = str(facts.get("subject") or "")
    violations: List[str] = []

    # 1. spot metrics (price, supply, market cap, volume, rank, ...).
    for m in facts.get("metrics", []) or ():
        value = m.get("value")
        if value is None:
            continue
        metric = m.get("metric", "?")
        forms = _metric_forms(value, m.get("unit", ""), metric, subject)
        if not _present(forms, report):
            violations.append(
                f"{metric} ({m.get('scope')}): bundle value {value} "
                f"[{_show(forms)}] not found in report (altered or dropped?)"
            )

    # 2. supply-momentum windows — percent (filler-exact, the precise anchor) and
    #    the signed absolute change.
    for sm in facts.get("supply_momentum", []) or ():
        window = sm.get("window", "?")
        pct = sm.get("net_change_pct")
        if pct is not None:
            form = f"{float(pct):+.2f}%"
            if form not in report:
                violations.append(
                    f"supply {window}: bundle {form} not found in report "
                    f"(altered or dropped?)"
                )
        abs_change = sm.get("net_change_abs")
        if abs_change is not None:
            forms = _signed_usd_forms(float(abs_change))
            if not _present(forms, report):
                violations.append(
                    f"supply {window} abs: bundle {abs_change} [{_show(forms)}] "
                    f"not found in report (altered or dropped?)"
                )

    # 3. issuer SEC financials — each non-null cell carries its own value/unit.
    financials = facts.get("issuer_financials")
    if isinstance(financials, Mapping):
        for key, cell in financials.items():
            if key in _FINANCIAL_META_KEYS or not isinstance(cell, Mapping):
                continue
            value = cell.get("value")
            if value is None:
                continue
            forms = _metric_forms(value, cell.get("unit", "USD"), key, subject)
            if not _present(forms, report):
                violations.append(
                    f"financials {key}: bundle value {value} [{_show(forms)}] "
                    f"not found in report (altered or dropped?)"
                )

    return violations


# --------------------------------------------------------------------------- #
# thin CLI — lets the /research command run the gate FAIL-CLOSED before render
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    """Run the gate over a report .md + a .facts.json. Exit 1 (fail-closed) if any
    machine value is missing, printing each violation; exit 0 when clean."""
    parser = argparse.ArgumentParser(
        prog="python -m analysis_layer.qc.numbers",
        description="Numbers-trace gate (⑤.1): assert every machine-produced "
                    "bundle value survives into the final report.",
    )
    parser.add_argument("report", help="path to the final report markdown")
    parser.add_argument("facts", help="path to the .facts.json bundle")
    args = parser.parse_args(argv)

    with open(args.report, encoding="utf-8") as fh:
        report_md = fh.read()
    with open(args.facts, encoding="utf-8") as fh:
        facts = json.load(fh)

    violations = check_numbers_trace(report_md, facts)
    if violations:
        print(
            "numbers-trace gate FAILED (fail-closed) — machine value(s) missing "
            "from the report:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("numbers-trace gate passed: all machine values present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
