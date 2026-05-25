"""SEC EDGAR fetcher — B.1.4 (first two-UA enforcer, first email-PII handler).

Fetches filings index + financial-data XBRL for any subject whose
parent_or_issuer_entity is a SEC-registered listed company (per P0_subject_confirm):
the submissions list (recent 10-K/10-Q/8-K + metadata) and the companyfacts XBRL
JSON (machine-readable financial line items). Extends the etherscan_fetch reference
pattern (B.1.3), generalising its runtime-secret handling from an API key to a
PII-bearing contact email.

Source contract: references/data_source_registry.md §6.
  - Auth: NO API key. SEC mandates a User-Agent header carrying a contact email.
  - Two-UA invariant (THE I-003 DEFENSE): every HTTP call selects its User-Agent
    BY HOST through `_select_user_agent`. `*.sec.gov` (or exact `sec.gov`) gets the
    email-bearing sec_user_agent; every other host gets the PII-free public UA. The
    I-003 leak (Phase A) happened because a single email-bearing UA was reused on a
    non-SEC host (investors.intuit.com). This fetcher makes that impossible at the
    implementation layer. See references/equity_incidents_archive.md I-003.
  - Email handling: sec_email is PROCESS-MEMORY ONLY. It is never written to disk,
    never placed in the envelope (the SEC URLs carry no email — it lives only in the
    request header), and never echoed in an error message (even on malformed input).
  - Dual-mode input (方案 C): EITHER --sec-email (direct) OR --run-dir
    (orchestrator-coupled, reads <run_dir>/meta/gates.json), never both, never neither.
  - Rate limit: SEC documents 10 req/sec; this harness uses a conservative 0.5 req/sec
    (2s between calls + 100ms jitter), single concurrent request — polite to a shared
    public resource.
  - Errors: submissions 404 -> subject_not_found_on_sec_edgar; 403 -> rate_limited_by_sec
    (NO auto-retry — SEC takes rate limits seriously); 429 -> wait 60s + retry once;
    5xx -> upstream_5xx_sec; companyfacts 404 -> soft skip (null).

Output: meta/raw/sec_edgar/<subject_slug>_cik<CIK>_<utc_iso>.json with the standard
  6-key envelope. raw_response is {submissions, companyfacts} keyed by call. The
  'endpoint' field is the base https://data.sec.gov pattern; the email is NEVER in it
  (SEC puts the email in the header, not the URL — so this is automatic, and a test
  asserts the email string appears nowhere in the serialized envelope).

Usage:
    # Direct mode
    python tools/fetchers/sec_edgar_fetch.py \
        --subject Circle --subject-type stablecoin_issuer \
        --freshness-window 30d --sec-email operator@example.com

    # Orchestrator-coupled mode (reads <run_dir>/meta/gates.json)
    python tools/fetchers/sec_edgar_fetch.py \
        --subject Circle --subject-type stablecoin_issuer \
        --freshness-window 30d --run-dir /path/to/run
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# All SEC structured endpoints live under this host.
SEC_BASE = "https://data.sec.gov"

# PII-free public User-Agent — identical to the sibling fetchers and to
# tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT. Used for any NON-sec.gov host.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"

# Email-bearing UA template. The email is substituted at runtime by — and ONLY by —
# `_select_user_agent`, and only for *.sec.gov hosts. This is the I-003 chokepoint.
SEC_UA_TEMPLATE = "StackAnamnesis/1.0 ({email})"

RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "sec_edgar"

# Harness pacing contract (registry §6): SEC documents 10 req/sec; we cap far under at
# 0.5 req/sec (2s) + 100ms jitter, single concurrent request. Pace BEFORE every call.
RATE_LIMIT_SECONDS = 2.0
JITTER_SECONDS = 0.1
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

# Canonical 5-class enum (references/subject_taxonomy.md). The registry's SEC gate is
# conditional on a listed parent, not on the class; the class is recorded, not routed.
SUBJECT_TYPES = (
    "stablecoin_issuer",
    "orchestrator",
    "wallet",
    "chain",
    "agentic_payment_layer",
)
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")

# Mini CIK registry — 10 entries for B.1.4. Broader subject->CIK resolution (the SEC
# full-text company search) is a future TD; for now a token like "USDC" must be
# resolved to its parent name ("Circle") by the caller before dispatch.
CIK_REGISTRY: dict[str, str] = {
    "circle": "0001876042",          # Circle Internet Group (CRCL); per registry §6
    "coinbase": "0001679788",        # Coinbase Global
    "coinbase global": "0001679788",
    "microstrategy": "0001050446",   # MicroStrategy
    "marathon digital": "0001507605",
    "riot platforms": "0001167419",
    "block": "0001512673",           # Block Inc. (formerly Square)
    "robinhood": "0001783879",
    "galaxy digital": "0001750155",
    "intuit": "0000896878",          # Phase A test subject; kept for I-003 regression
}

_last_request_at = 0.0


class EdgarFetchError(RuntimeError):
    """Raised on a halting condition (bad email, unresolved CIK, gate-coupling failure,
    rate limit, 5xx). Error messages NEVER carry the sec_email value."""


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "-").replace("/", "_")


def _resolve_cik(subject: str) -> str:
    """Resolve a subject to a zero-padded 10-digit CIK string.

    A purely-numeric subject is taken as a CIK and zero-padded to 10 digits. Otherwise
    the lowercased subject is looked up in CIK_REGISTRY. Raises cik_resolution_failed
    when neither path resolves.
    """
    s = subject.strip()
    if s.isdigit():
        return s.zfill(10)
    cik = CIK_REGISTRY.get(s.lower())
    if cik is not None:
        return cik
    raise EdgarFetchError(f"cik_resolution_failed: subject={subject!r}")


def _validate_email(email: str) -> None:
    """Minimum-sanity check on the contact email.

    Must contain '@' and at least one '.' after the '@', and must not be the canonical
    Gate-2 decline token "declined" (the caller should have caught that; defense in
    depth). On failure raises EdgarFetchError("sec_email_invalid") WITHOUT echoing the
    rejected value — the email must never reach a log or error string.
    """
    if email == "declined":
        raise EdgarFetchError("sec_email_invalid")
    at = email.find("@")
    if at == -1 or "." not in email[at + 1 :]:
        raise EdgarFetchError("sec_email_invalid")


def _select_user_agent(url: str, sec_email: str) -> str:
    """THE I-003 DEFENSE — single source of truth for User-Agent selection.

    Selects BY HOST, never by "whichever UA is set". A host of exactly `sec.gov` or any
    `*.sec.gov` subdomain gets the email-bearing SEC UA; every other host (including
    `sec.gov.evil.com`, which only *looks* like SEC) gets the PII-free public UA. This
    is the ONLY place SEC_UA_TEMPLATE is ever formatted with the email.
    """
    host = (urlparse(url).hostname or "").lower()
    if host == "sec.gov" or host.endswith(".sec.gov"):
        return SEC_UA_TEMPLATE.format(email=sec_email)
    return PUBLIC_USER_AGENT


def _load_email_from_run_dir(run_dir: Path) -> str:
    """Read the contact email from <run_dir>/meta/gates.json (orchestrator-coupled mode).

    Per agents/sec_email_gate.md's output schema, the email lives at
    gates.sec_email.value. Errors map to the dual-mode contract:
      - missing / unparseable / malformed gates.json -> gates_file_unreadable
      - sec_email.applies == False -> sec_email_gate_skipped (this subject doesn't
        trigger SEC; the fetcher should not have been dispatched)
      - sec_email.value == "declined" -> sec_email_declined_by_user

    NOTE (interim deviation, see registry §6 / TD): the canonical gate writes only the
    sentinel "email_provided" to disk and keeps the real email in process memory. Until
    the B.2 orchestrator exists, this run-dir mode reads the email straight from
    gates.json, which means the email is on disk for the run's duration. The direct
    --sec-email mode keeps the email process-memory-only and is preferred for now.
    """
    gates_path = run_dir / "meta" / "gates.json"
    try:
        data = json.loads(gates_path.read_text(encoding="utf-8"))
        entry = data["gates"]["sec_email"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        raise EdgarFetchError("gates_file_unreadable")
    if entry.get("applies") is False:
        raise EdgarFetchError("sec_email_gate_skipped")
    value = entry.get("value")
    if value == "declined":
        raise EdgarFetchError("sec_email_declined_by_user")
    if not isinstance(value, str):
        raise EdgarFetchError("gates_file_unreadable")
    return value


def _throttle() -> None:
    """Block until at least RATE_LIMIT_SECONDS (+jitter) since the last call."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = RATE_LIMIT_SECONDS + random.uniform(0, JITTER_SECONDS) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _get_json(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    """GET with the registry §6 error contract. Returns (status_code, parsed_json).

    403 -> rate_limited_by_sec, NO auto-retry (SEC treats rate limits seriously).
    429 -> wait 60s and retry once. 5xx -> upstream_5xx_sec. 404 is returned to the
    caller (submissions treats it as not-found; companyfacts as a soft skip). Error
    messages include the SEC URL, which is safe — the email is in the header, not the URL.
    """
    _throttle()
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 403:
        raise EdgarFetchError(f"rate_limited_by_sec: status=403 url={url}")
    if resp.status_code >= 500:
        raise EdgarFetchError(f"upstream_5xx_sec: status={resp.status_code} url={url}")
    data = resp.json() if resp.status_code != 404 else None
    return resp.status_code, data


def fetch(
    subject: str,
    subject_type: str,
    freshness_window: str,
    sec_email: str,
) -> dict[str, Any]:
    """Fetch raw SEC EDGAR data for one subject: submissions -> companyfacts.

    Validates the email, resolves the CIK, then makes the two calls sequentially through
    the throttle. Both URLs are *.sec.gov, so both route through `_select_user_agent` and
    receive the SEC UA — but the helper is still the gate, so a future non-SEC URL would
    automatically get the public UA. companyfacts 404 is a soft skip (null). Returns the
    6-key envelope; sec_email appears nowhere in it.
    """
    _validate_email(sec_email)
    cik = _resolve_cik(subject)

    submissions_url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    companyfacts_url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"

    sub_status, submissions = _get_json(
        submissions_url, {"User-Agent": _select_user_agent(submissions_url, sec_email)}
    )
    if sub_status == 404:
        raise EdgarFetchError(f"subject_not_found_on_sec_edgar: cik={cik}")

    cf_status, companyfacts = _get_json(
        companyfacts_url, {"User-Agent": _select_user_agent(companyfacts_url, sec_email)}
    )
    # Not every CIK has companyfacts (delayed XBRL pipeline, registry §6) — soft skip.
    if cf_status == 404:
        companyfacts = None

    return {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        # Base host pattern only — the email is in the request header, never the URL.
        "endpoint": SEC_BASE,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": {
            "submissions": submissions,
            "companyfacts": companyfacts,
        },
    }


def write_output(payload: dict[str, Any]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(payload["subject"])
    cik = _resolve_cik(payload["subject"])
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RAW_DIR / f"{slug}_cik{cik}_{ts}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--subject", required=True)
    p.add_argument("--subject-type", required=True, choices=list(SUBJECT_TYPES))
    p.add_argument("--freshness-window", required=True, choices=list(FRESHNESS_WINDOWS))
    # 方案 C: exactly one of the two input modes — argparse itself enforces this.
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sec-email", help="contact email (direct mode; process-memory only)")
    mode.add_argument("--run-dir", help="run dir whose meta/gates.json carries the email")
    args = p.parse_args(argv)

    if args.sec_email is not None:
        sec_email = args.sec_email
    else:
        sec_email = _load_email_from_run_dir(Path(args.run_dir))

    payload = fetch(args.subject, args.subject_type, args.freshness_window, sec_email)
    path = write_output(payload)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
