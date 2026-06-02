"""analysis_layer/orchestrate.py — the analysis ORCHESTRATOR (B.2.10, TD-036).

The pipeline front door, HALF 1 of 2. Until now the full analysis trunk
(resolve → load envelopes → extract → reconcile → derive → fill → write) only
existed hand-wired inside the tests (``tests/analysis_layer/test_filler.py``'s
``_build_usdc_reconciled`` + the e2e tests). This module CENTRALISES exactly
that wiring behind one entry point so any fetched subject's report can be
regenerated with a single call / one CLI command.

This half is PURE (rule 3): it reads the envelopes already on disk under
``meta/raw/<source>/`` and produces the markdown report. It makes NO network
calls and reads NO env keys. The FETCH half — running the B.1 fetchers to
REFRESH those envelopes before analysing — is the NEXT step (B.2.11) and is
deliberately NOT built here.

Two things the hand-wired tests did NOT do, which the orchestrator does:
  * it wires ALL SIX extractors, including ``sec_edgar`` — so Circle's regulated
    SEC financials (revenue / assets / …) flow into the report's Evidence Table,
    a more complete deliverable than the filler e2e makes;
  * it is best-effort about missing sources — a source with no envelope on disk
    (e.g. a DefiLlama fetch that failed that run) is simply SKIPPED; the report
    still builds and that section stays flagged exactly as the filler handles it.

Determinism: given a fixed set of on-disk envelopes the report CONTENT is
byte-identical across runs (only the output filename's UTC stamp differs).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional

from analysis_layer.aggregators.reconcile import reconcile
from analysis_layer.contract import ExtractedValue, ReconciledValue, SubjectRef
from analysis_layer.derivations.supply_change import compute_supply_change
from analysis_layer.extractors import (
    alchemy, coingecko, coinmarketcap, defillama, etherscan, sec_edgar,
)
from analysis_layer.fillers.fill import fill
from analysis_layer.resolvers.subject_ref import resolve_subject

ROOT = Path(__file__).resolve().parents[1]
# The on-disk file is named v1.3 but its content header is "Research SOP v1.4" —
# the unified master template with the Part 5.1–5.5 subject-type modules.
DEFAULT_TEMPLATE = ROOT / "references" / "templates" / "crypto_research_v1.3.md"
DEFAULT_RAW_DIR = "meta/raw"
DEFAULT_OUT_DIR = "meta/reports"


# --------------------------------------------------------------------------- #
# SEC facts pulled for an issuer-backed subject
# --------------------------------------------------------------------------- #
# (concept, fy, fp) XBRL facts read from the issuer's SEC company-facts envelope.
# Each (fy, fp) resolves to a SEC ``frame`` present in Circle's real envelope
# (TD-023: grounded against meta/raw/sec_edgar/*.json — Revenues→CY2024,
# Assets/Liabilities→CY{fy}Q4I instant, NetIncomeLoss→CY2024, StockholdersEquity
# →CY{fy}Q4I). These land in the Evidence Table (no [AUTO] slot maps to them),
# surfacing the issuer's regulated financials alongside the on-chain metrics.
_SEC_FACTS = (
    ("Revenues", 2024, "FY"),
    ("Assets", 2025, "FY"),
    ("Liabilities", 2025, "FY"),
    ("NetIncomeLoss", 2024, "FY"),
    ("StockholdersEquity", 2024, "FY"),
)


# --------------------------------------------------------------------------- #
# source → extractor mapping
# --------------------------------------------------------------------------- #
# Each adapter normalises one source's heterogeneous extractor signature to the
# uniform ``(envelope, subject_ref) -> list[ExtractedValue]`` shape the loader
# iterates over. An adapter returns ``[]`` when its source yields nothing for the
# envelope (rule 1: never throws). The mapping naming ALL SIX sources is the
# single guard against silently dropping one (see test_orchestrate mapping test).
def _alchemy_values(env: Mapping, sref: SubjectRef) -> List[ExtractedValue]:
    ev = alchemy.decode_total_supply(env, sref.decimals)
    return [ev] if ev is not None else []


def _etherscan_values(env: Mapping, sref: SubjectRef) -> List[ExtractedValue]:
    ev = etherscan.extract_supply(env, sref.decimals)
    return [ev] if ev is not None else []


def _coingecko_values(env: Mapping, sref: SubjectRef) -> List[ExtractedValue]:
    return coingecko.extract_spot_metrics(env)


def _coinmarketcap_values(env: Mapping, sref: SubjectRef) -> List[ExtractedValue]:
    return coinmarketcap.extract_latest_quote(env)


def _defillama_values(env: Mapping, sref: SubjectRef) -> List[ExtractedValue]:
    ev = defillama.latest(env)
    return [ev] if ev is not None else []


def _sec_edgar_values(env: Mapping, sref: SubjectRef) -> List[ExtractedValue]:
    out: List[ExtractedValue] = []
    for concept, fy, fp in _SEC_FACTS:
        ev = sec_edgar.get_xbrl_value(env, concept, fy, fp)
        if ev is not None:
            out.append(ev)
    return out


# source slug -> adapter. ORDER fixed for determinism. ALL six wired.
SOURCE_EXTRACTORS: "Dict[str, Callable[[Mapping, SubjectRef], List[ExtractedValue]]]" = {
    "alchemy": _alchemy_values,
    "etherscan": _etherscan_values,
    "coingecko": _coingecko_values,
    "coinmarketcap": _coinmarketcap_values,
    "defillama": _defillama_values,
    "sec_edgar": _sec_edgar_values,
}


def _envelope_pattern(source: str, sref: SubjectRef) -> str:
    """Glob a source's envelope dir uses for THIS subject (mirrors the tests).

    The on-chain sources (Alchemy / Etherscan) key their files by contract
    address / chain, so the test globs ``*.json`` and relies on the extractor to
    skip non-matching envelopes; the aggregator-keyed sources key by the
    subject's own slug (``usdc_*.json``); SEC keys by the issuer's CIK.
    """
    slug = sref.subject.lower()
    if source in ("alchemy", "etherscan"):
        return "*.json"
    if source == "sec_edgar":
        cik = (sref.identifiers or {}).get("sec_cik")
        return f"*cik{cik}*.json" if cik else "*.json"
    return f"{slug}_*.json"


# --------------------------------------------------------------------------- #
# envelope loading (newest-first, best-effort)
# --------------------------------------------------------------------------- #
def _iter_envelopes_newest(raw_dir: Path, source: str, pattern: str):
    """Yield parsed envelopes for ``source``, NEWEST first (filename-sorted).

    A missing source dir yields nothing; an unreadable / malformed file is
    skipped (rule 1) — never crashes the report build.
    """
    base = raw_dir / source
    if not base.exists():
        return
    for path in sorted(base.glob(pattern), reverse=True):
        try:
            yield json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue


def _newest_defillama_envelope(raw_dir: Path, sref: SubjectRef) -> Optional[Mapping]:
    """The newest DefiLlama envelope for the subject, or None (for the change
    derivation, which needs the raw series envelope — not just its latest point)."""
    pattern = _envelope_pattern("defillama", sref)
    return next(_iter_envelopes_newest(raw_dir, "defillama", pattern), None)


def load_and_extract(
    subject: str, raw_dir: "str | Path" = DEFAULT_RAW_DIR
) -> List[ExtractedValue]:
    """Resolve ``subject`` and extract every on-disk fact for it. PURE.

    For each source (in fixed order) loads the NEWEST matching envelope, runs the
    source's extractor, and keeps the first envelope that yields any value —
    mirroring the tests' ``_first`` semantics (an on-chain dir holds both a
    chain-level and a contract envelope; only the latter decodes a supply). A
    source with NO usable envelope is simply skipped. Raises ``ValueError`` if
    the subject is not in the subject_ref registry.

    Reusable building block: the fetch front (B.2.11) and the tests can call this
    directly without going through :func:`research`.
    """
    sref = _resolve_or_raise(subject)
    extracted, _loaded = _extract_for(sref, _as_dir(raw_dir))
    return extracted


def _extract_for(sref: SubjectRef, raw_dir: Path):
    """(extracted values, list of sources that contributed) for ``sref``."""
    extracted: List[ExtractedValue] = []
    loaded: List[str] = []
    for source, adapter in SOURCE_EXTRACTORS.items():
        pattern = _envelope_pattern(source, sref)
        values: List[ExtractedValue] = []
        for env in _iter_envelopes_newest(raw_dir, source, pattern):
            values = adapter(env, sref)
            if values:
                break
        if values:
            extracted.extend(values)
            loaded.append(source)
    return extracted, loaded


# --------------------------------------------------------------------------- #
# the report build
# --------------------------------------------------------------------------- #
@dataclass
class ResearchResult:
    """What one :func:`research` run produced — path + a one-glance summary."""

    path: Path
    markdown: str
    subject: str
    subject_type: str
    sources_loaded: List[str]
    reconciled_count: int
    filled_slots: int
    derivations: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _resolve_or_raise(subject: str) -> SubjectRef:
    sref = resolve_subject(subject)
    if sref is None:
        raise ValueError(
            f"subject {subject!r} not in subject_ref registry — add bindings "
            f"first (analysis_layer/resolvers/subject_ref.py)"
        )
    return sref


def _as_dir(value: "str | Path") -> Path:
    """A directory path, anchored to ROOT when given relative (so the CLI works
    from any cwd while the mandate's ``meta/raw`` default still resolves)."""
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def build_report(
    subject: str,
    *,
    subject_type: Optional[str] = None,
    mode: str = "subject_driven",
    template_path: "str | Path" = DEFAULT_TEMPLATE,
    raw_dir: "str | Path" = DEFAULT_RAW_DIR,
) -> "tuple[str, SubjectRef, List[str], List[ReconciledValue], List[str]]":
    """Run the PURE pipeline and return the report markdown + metadata.

    Does everything :func:`research` does EXCEPT writing the file — so callers
    that want the markdown (or the determinism test) need not touch disk.
    Returns ``(markdown, subject_ref, sources_loaded, reconciled, notes)``.
    """
    sref = _resolve_or_raise(subject)
    # An explicit subject_type arg overrides the registry's (drives module-aware
    # section selection); default to the registry's subject_type.
    if subject_type is not None and subject_type != sref.subject_type:
        sref = _retype(sref, subject_type)
    raw = _as_dir(raw_dir)

    # 1–3. resolve → load newest envelope per source → extract (all 6 sources).
    extracted, sources_loaded = _extract_for(sref, raw)

    # 4. reconcile the extracted facts.
    reconciled: List[ReconciledValue] = list(reconcile(extracted))

    # 5. derivation: supply-momentum change over the DefiLlama series, if present.
    #    CONCATENATE its values; collect skip notes. Best-effort: absent → skip.
    notes: List[str] = []
    dl_env = _newest_defillama_envelope(raw, sref)
    if dl_env is not None:
        changes, change_notes = compute_supply_change(dl_env, sref)
        reconciled = reconciled + list(changes)
        notes.extend(change_notes)

    # 6. fill the template (module-aware, keyed on subject_type + mode).
    markdown = fill(_as_template_text(template_path), reconciled, sref, mode=mode)
    return markdown, sref, sources_loaded, reconciled, notes


def _retype(sref: SubjectRef, subject_type: str) -> SubjectRef:
    """A copy of ``sref`` with an overridden ``subject_type`` (caller override)."""
    return SubjectRef(
        subject=sref.subject, subject_type=subject_type, decimals=sref.decimals,
        issuer=sref.issuer, identifiers=sref.identifiers,
    )


def _as_template_text(template_path: "str | Path") -> str:
    p = Path(template_path)
    if not p.is_absolute():
        p = ROOT / p
    return p.read_text(encoding="utf-8")


def _run(
    subject: str,
    *,
    subject_type: Optional[str] = None,
    mode: str = "subject_driven",
    template_path: "str | Path" = DEFAULT_TEMPLATE,
    raw_dir: "str | Path" = DEFAULT_RAW_DIR,
    out_dir: "str | Path" = DEFAULT_OUT_DIR,
) -> ResearchResult:
    """Build the report, WRITE it, and return the full result (path + summary)."""
    markdown, sref, sources_loaded, reconciled, notes = build_report(
        subject, subject_type=subject_type, mode=mode,
        template_path=template_path, raw_dir=raw_dir,
    )

    out = _as_dir(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"{sref.subject.lower()}_{stamp}.md"
    path.write_text(markdown, encoding="utf-8")

    filled = markdown.count("[AUTO ✓ FILLED") + markdown.count("[SEMI-AUTO ✓ COMPUTED")
    derivations = (
        ["supply_change (net 7d/30d/90d)"]
        if "[SEMI-AUTO ✓ COMPUTED" in markdown else []
    )
    return ResearchResult(
        path=path, markdown=markdown, subject=sref.subject,
        subject_type=sref.subject_type, sources_loaded=sources_loaded,
        reconciled_count=len(reconciled), filled_slots=filled,
        derivations=derivations, notes=notes,
    )


def research(
    subject: str,
    *,
    subject_type: Optional[str] = None,
    mode: str = "subject_driven",
    template_path: "str | Path" = DEFAULT_TEMPLATE,
    raw_dir: "str | Path" = DEFAULT_RAW_DIR,
    out_dir: "str | Path" = DEFAULT_OUT_DIR,
) -> Path:
    """Regenerate ``subject``'s research report from on-disk envelopes. PURE.

    Steps (all pure — no network, no env-key reads): resolve_subject → load the
    newest envelope per source → extract (all 6 sources incl. SEC) → reconcile →
    supply-change derivation → module-aware fill → write. Returns the written
    report's path. Raises ``ValueError`` if the subject is not in the registry.
    """
    return _run(
        subject, subject_type=subject_type, mode=mode,
        template_path=template_path, raw_dir=raw_dir, out_dir=out_dir,
    ).path


# --------------------------------------------------------------------------- #
# thin CLI
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m analysis_layer.orchestrate",
        description="Regenerate a subject's research report from on-disk "
                    "envelopes (PURE — no network).",
    )
    parser.add_argument("subject", help="canonical subject, e.g. USDC")
    parser.add_argument("--subject-type", default=None,
                        help="override subject_type (default: from subject_ref)")
    parser.add_argument("--mode", default="subject_driven",
                        help="subject_driven (Mode A) | news_driven (Mode B)")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                        help="template path (default: v1.4 master SOP)")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    try:
        result = _run(
            args.subject, subject_type=args.subject_type, mode=args.mode,
            template_path=args.template, raw_dir=args.raw_dir, out_dir=args.out_dir,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        printed_path = result.path.relative_to(ROOT)
    except ValueError:
        printed_path = result.path
    print(f"report written to: {printed_path}")
    skipped = [s for s in SOURCE_EXTRACTORS if s not in result.sources_loaded]
    summary = (
        f"subject={result.subject} · subject_type={result.subject_type} · "
        f"sources loaded={len(result.sources_loaded)} "
        f"({', '.join(result.sources_loaded) or 'none'})"
        + (f" · skipped sources: {', '.join(skipped)}" if skipped else "")
        + f" · reconciled facts={result.reconciled_count} · "
        f"filled slots={result.filled_slots} · "
        f"derivations={', '.join(result.derivations) or 'none'}"
    )
    print(summary)
    for note in result.notes:
        print(f"  - skipped window: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
