"""analysis_layer/fetch_front.py — the IMPURE FETCH FRONT (B.2.11, TD-038).

Half 2 of 2 of the pipeline front door. ``orchestrate.research()`` is the PURE
analysis half — it reads whatever envelopes already sit under ``meta/raw/`` and
produces the report. This module is the half that REFRESHES those envelopes
first: subject → run the right B.1 fetchers → fresh envelopes on disk → (then)
``research()``. It is the only IMPURE piece (network + API keys), so it is kept
OUT of the pure analysis path and is opt-in (``research(..., fetch=True)`` /
``--fetch``); the default analysis-only path stays offline and unchanged.

★ BEST-EFFORT (the DefiLlama-failed-that-run lesson). Every fetcher runs in its
own isolated subprocess with a timeout; a fetcher that fails — missing key,
network error, rate-limit, subject-not-found, timeout — is RECORDED as a note
and SKIPPED. It must NEVER crash the run; ``research()`` then analyses whatever
envelopes did land (a missing source just leaves its section flagged, exactly as
the filler already handles).

★ SECRETS (invariant I-003). This module never reads, logs, or persists any API
key — each fetcher reads its OWN key from ``~/.config/anamnesis/<source>.key``.
The single secret this module handles is the SEC contact email: it is read from
an env var and passed to the SEC fetcher's ``--sec-email`` (process-memory only),
and is SCRUBBED from every returned note so it can never reach a log or report.

How each source is addressed (from ``subject_ref.identifiers`` — TD-023, the
single source of per-fetcher args):
  * on-chain (etherscan / alchemy)  → the ``eth_contract`` address + ``eth_chain``
  * SEC EDGAR                       → the ``issuer`` name (the fetcher resolves the CIK)
  * coingecko / coinmarketcap / defillama → the CANONICAL SUBJECT NAME, NOT the
    per-source slug/id. ⚠ DEVIATION FROM THE B.2.11 MANDATE, ON PURPOSE (flagged
    in TD-038): these fetchers (a) resolve the subject by name internally
    (CoinGecko /search, CMC /map by slug-then-symbol, DefiLlama by stablecoins
    list name) — CMC literally cannot resolve the numeric id ``3408`` — and (b)
    NAME THEIR OUTPUT FILE after ``--subject``. ``orchestrate`` globs these
    sources as ``<subject.lower()>_*.json``, so the fetch MUST pass the canonical
    name (``USDC``) for the freshly-written envelope to be found by the analysis
    half. Passing the slug ``usd-coin`` would write ``usd-coin_*.json`` and the
    two halves would not compose.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from analysis_layer.contract import SubjectRef
from analysis_layer.resolvers.subject_ref import resolve_subject

ROOT = Path(__file__).resolve().parents[1]
FETCHERS_DIR = ROOT / "tools" / "fetchers"

# Env var the operator sets so the SEC fetcher receives its mandated contact
# email. No pre-existing repo convention was found (see TD-038); this name is the
# chosen contract. NEVER logged/persisted — read here, passed to --sec-email,
# scrubbed from all notes.
SEC_EMAIL_ENV = "ANAMNESIS_SEC_EMAIL"

DEFAULT_TIMEOUT = 120  # seconds, per fetcher subprocess
DEFAULT_FRESHNESS_WINDOW = "30d"


# --------------------------------------------------------------------------- #
# per-source invocation specs
# --------------------------------------------------------------------------- #
def _eth_contract(sref: SubjectRef) -> Optional[str]:
    return (sref.identifiers or {}).get("eth_contract")


_CHAIN_IDS = {"ethereum": 1}


def _chain_id(sref: SubjectRef) -> int:
    return _CHAIN_IDS.get((sref.identifiers or {}).get("eth_chain", "ethereum"), 1)


def _chain_arg(sref: SubjectRef) -> List[str]:
    return ["--chain-id", str(_chain_id(sref))]


def _sec_subject(sref: SubjectRef) -> Optional[str]:
    """The SEC fetch's ``--subject`` (the issuer name) — but ONLY when the subject
    is SEC-registered, i.e. the registry bound a ``sec_cik``. A stablecoin whose
    issuer is not SEC-registered (e.g. Tether) has no CIK, so SEC is skipped with a
    note rather than fetched against an issuer EDGAR cannot resolve."""
    if not (sref.identifiers or {}).get("sec_cik"):
        return None
    return sref.issuer


@dataclass(frozen=True)
class SourceSpec:
    """How to invoke one B.1 fetcher for a subject.

    ``subject_value`` pulls the ``--subject`` arg from the subject_ref (the right
    identifier for THIS source); returning None means the binding is absent and
    the source is skipped with a note. ``fetch_subject_type`` is the type THIS
    fetcher's CLI expects (NOT always the orchestrator's — the on-chain token read
    + SEC both want ``stablecoin_issuer`` while the market sources want
    ``stablecoin``). ``needs_email`` flags the SEC fetcher's ``--sec-email``.
    """

    name: str
    fetcher: str
    fetch_subject_type: str
    subject_value: Callable[[SubjectRef], Optional[str]]
    extra_args: Callable[[SubjectRef], List[str]] = lambda sref: []
    needs_email: bool = False


# Stablecoin set — Part 11.5 Step 1: DefiLlama, CoinGecko, CoinMarketCap,
# Etherscan, Alchemy, SEC EDGAR. Order mirrors that table.
_STABLECOIN_SOURCES: Tuple[SourceSpec, ...] = (
    SourceSpec("defillama", "defillama_fetch.py", "stablecoin",
               lambda s: s.subject),
    SourceSpec("coingecko", "coingecko_fetch.py", "stablecoin",
               lambda s: s.subject),
    SourceSpec("coinmarketcap", "coinmarketcap_fetch.py", "stablecoin",
               lambda s: s.subject),
    SourceSpec("etherscan", "etherscan_fetch.py", "stablecoin",
               _eth_contract, _chain_arg),
    # the token-contract read (eth_call totalSupply) lives under stablecoin_issuer
    SourceSpec("alchemy", "alchemy_fetch.py", "stablecoin_issuer",
               _eth_contract, _chain_arg),
    SourceSpec("sec_edgar", "sec_edgar_fetch.py", "stablecoin_issuer",
               _sec_subject, needs_email=True),
)

# subject_type (the orchestrator's) -> the ordered fetcher set. Extensible: add a
# row to cover chain / protocol subjects.
SOURCES_BY_TYPE: Dict[str, Tuple[SourceSpec, ...]] = {
    "stablecoin": _STABLECOIN_SOURCES,
}


# --------------------------------------------------------------------------- #
# argv construction
# --------------------------------------------------------------------------- #
def build_argv(
    spec: SourceSpec, sref: SubjectRef, freshness_window: str,
    sec_email: Optional[str],
) -> "Tuple[Optional[List[str]], Optional[str]]":
    """Build the full subprocess argv for one fetcher, or ``(None, reason)``.

    Returns ``(argv, None)`` on success or ``(None, skip_reason)`` when a required
    binding (subject identifier / SEC email) is missing — the caller turns the
    reason into a skip note. The argv legitimately carries the SEC email (the
    fetcher needs it); callers must never put argv into a note (see scrubbing).
    """
    subject = spec.subject_value(sref)
    if not subject:
        return None, f"missing subject binding for {spec.name} in subject_ref"

    argv = [
        sys.executable, str(FETCHERS_DIR / spec.fetcher),
        "--subject", subject,
        "--subject-type", spec.fetch_subject_type,
        "--freshness-window", freshness_window,
        *spec.extra_args(sref),
    ]
    if spec.needs_email:
        if not sec_email:
            return None, (
                f"{spec.name} needs a contact email — set ${SEC_EMAIL_ENV} "
                f"(process-memory only; never persisted)"
            )
        argv += ["--sec-email", sec_email]
    return argv, None


# --------------------------------------------------------------------------- #
# subprocess runner (isolated + timed) — the only network-touching code
# --------------------------------------------------------------------------- #
def _run_fetcher(name: str, argv: List[str], timeout: int) -> "Tuple[bool, str]":
    """Invoke one fetcher subprocess; return ``(ok, reason)``. Never raises.

    A non-zero exit / network error is captured from the fetcher's OWN output
    (the fetchers are designed never to echo a key or the email, I-003). A
    timeout is reported WITHOUT the command (``TimeoutExpired`` carries the argv,
    which would leak the email) — only the duration.
    """
    try:
        proc = subprocess.run(
            argv, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"           # NB: no argv echo
    except OSError as exc:                                   # e.g. python missing
        return False, f"could not launch fetcher ({exc.__class__.__name__})"

    if proc.returncode == 0:
        out = (proc.stdout or "").strip().splitlines()
        return True, (out[-1] if out else "ok")
    err = ((proc.stderr or "").strip() or (proc.stdout or "").strip()
           or f"exit {proc.returncode}")
    return False, err.splitlines()[-1][:200]


# --------------------------------------------------------------------------- #
# the front
# --------------------------------------------------------------------------- #
def fetch_subject(
    subject: str,
    *,
    subject_type: Optional[str] = None,
    freshness_window: str = DEFAULT_FRESHNESS_WINDOW,
    timeout: int = DEFAULT_TIMEOUT,
    runner: "Optional[Callable[[str, List[str], int], Tuple[bool, str]]]" = None,
) -> List[str]:
    """Refresh ``subject``'s envelopes by running its B.1 fetcher set. BEST-EFFORT.

    Resolves the subject (clear ``ValueError`` if unresolvable; subject_type
    defaults to the registry's), then for each source in the subject_type's set
    builds the right invocation and runs it in isolation. Returns a list of
    per-source notes (``"<source>: ok — …"`` / ``"<source>: FAILED — …"`` /
    ``"<source>: SKIPPED — …"``); a failing fetcher never stops the others and
    never raises. The fetchers write their own envelopes to ``meta/raw/``; this
    function does not parse their output — it triggers and tolerates.

    ``runner`` is injectable for tests (default: the real subprocess runner).
    The SEC contact email is read from ``$ANAMNESIS_SEC_EMAIL`` and SCRUBBED from
    every returned note (I-003).
    """
    sref = resolve_subject(subject)
    if sref is None:
        raise ValueError(
            f"subject {subject!r} not in subject_ref registry — add bindings "
            f"first (analysis_layer/resolvers/subject_ref.py)"
        )
    if subject_type is None:
        subject_type = sref.subject_type

    specs = SOURCES_BY_TYPE.get(subject_type)
    if not specs:
        return [
            f"no fetcher set defined for subject_type {subject_type!r} — fetch "
            f"skipped; analysis will use existing envelopes"
        ]

    run = runner or _run_fetcher
    sec_email = os.environ.get(SEC_EMAIL_ENV)

    notes: List[str] = []
    for spec in specs:
        argv, skip_reason = build_argv(spec, sref, freshness_window, sec_email)
        if argv is None:
            notes.append(f"{spec.name}: SKIPPED — {skip_reason}")
            continue
        try:
            ok, reason = run(spec.name, argv, timeout)
        except Exception as exc:  # a stub/runner that raises must not crash us
            ok, reason = False, f"runner error ({exc.__class__.__name__})"
        notes.append(f"{spec.name}: {'ok' if ok else 'FAILED'} — {reason}")

    # I-003 defense in depth: the email must never survive into a note/log/report.
    if sec_email:
        notes = [n.replace(sec_email, "<sec-email redacted>") for n in notes]
    return notes
