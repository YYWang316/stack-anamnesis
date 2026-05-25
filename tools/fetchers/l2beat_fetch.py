"""L2Beat fetcher — B.1.7 (final B.1 fetcher).

Fetches Layer-2 ecosystem data (Total Value Secured, stage / risk
classification) for a single L2 chain from the L2Beat public API (no auth).
The L2-specific complement to DefiLlama (§1, DeFi-aggregator-focused) and
Etherscan (§3, L1-Ethereum-focused).

Source contract: references/data_source_registry.md §12.
  - Auth: none. User-Agent: public_user_agent (PII-free) — NEVER the SEC
    email-bearing UA (this host is not *.sec.gov).
  - Rate limit: undocumented upstream; the host is fronted by Cloudflare and
    throttles aggressively. Harness hard rule: 1 req/3s with 100ms jitter,
    single concurrent request.
  - Errors: 404 / unresolved chain -> l2beat_chain_not_found; 429 -> wait 60s
    + retry once; 5xx -> upstream_5xx_l2beat.

LIVE-VERIFIED DIVERGENCE FROM REGISTRY §12 (prefer-intent-over-literal):
  Registry §12 documents `l2beat.com/api/tvl.json` (aggregate) and
  `l2beat.com/api/[project].json` (per-project). Both return 404 as of
  2026-05 — the API moved (§12 itself warns the endpoints change and are
  unsupported). The current public surface is:
    - /api/scaling/summary  -> {chart, projects}, projects keyed by slug,
                               each with tvs.breakdown.total, stage, risks.
    - /api/scaling/activity -> aggregate tx chart across ALL L2s (not
                               per-chain), so out of B.1.7 per-subject scope.
  The faithful per-chain equivalent of the defunct per-project endpoint is
  slicing the matched project out of /api/scaling/summary. That is what this
  fetcher does.

Output: meta/raw/l2beat/<subject_slug>_<utc_iso>.json containing
  {subject, subject_type, freshness_window, endpoint, fetched_at, raw_response}.
  raw_response is keyed by sub-call name ({"summary": <matched project>}).

Usage:
    python tools/fetchers/l2beat_fetch.py \
        --subject Arbitrum --subject-type chain --freshness-window 30d
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# PII-free public User-Agent (references/data_source_registry.md §12 + §6).
# L2Beat is NOT a *.sec.gov host, so the SEC email UA must never reach it;
# matches tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"
BASE = "https://l2beat.com/api"
RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "l2beat"

# Harness pacing contract (registry §12): 1 req/3s ceiling + 100ms jitter,
# single concurrent request. L2Beat is fronted by Cloudflare and throttles
# unadvertised endpoints hard, so pace conservatively BEFORE every call.
RATE_LIMIT_SECONDS = 3.0
JITTER_SECONDS = 0.1
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

# L2Beat is L2-only: only subject_type == "chain" is in scope.
SUPPORTED_SUBJECT_TYPE = "chain"
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")

_last_request_at = 0.0


class L2BeatFetchError(RuntimeError):
    """Raised on a halting condition (unsupported subject_type / 404 / 5xx)."""


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "-").replace("/", "_")


def _throttle() -> None:
    """Block until at least RATE_LIMIT_SECONDS (+jitter) since the last call."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = RATE_LIMIT_SECONDS + random.uniform(0, JITTER_SECONDS) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _summary_endpoint() -> str:
    """The single canonical endpoint — per-project data keyed by slug."""
    return f"{BASE}/scaling/summary"


def _get_json(url: str, headers: dict[str, str]) -> Any:
    """GET with the registry §12 error contract. 404/5xx halt; 429 retries once."""
    _throttle()
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 404:
        raise L2BeatFetchError(f"l2beat_chain_not_found: url={url}")
    if resp.status_code >= 500:
        raise L2BeatFetchError(
            f"upstream_5xx_l2beat: status={resp.status_code} url={url}"
        )
    resp.raise_for_status()
    return resp.json()


def _resolve_project(projects: dict[str, Any], subject: str) -> tuple[str, Any]:
    """Match `subject` to an L2Beat project. Returns (slug, project_dict).

    L2Beat keys projects by its own slug, which is usually `_slugify(subject)`
    (arbitrum, base, optimism, starknet, scroll). Some diverge from the common
    name (e.g. "zkSync" -> "zksync-era", "OP Mainnet" lives under "optimism"),
    so fall back to matching the project's own `slug`/`name`, then a prefix
    match before giving up.
    """
    slug = _slugify(subject)

    # 1. Direct slug-key hit (the common case).
    if slug in projects:
        return slug, projects[slug]

    # 2. Match the project's own slug or display name (case-insensitive).
    want_name = subject.strip().lower()
    for key, proj in projects.items():
        if not isinstance(proj, dict):
            continue
        proj_slug = str(proj.get("slug", "")).lower()
        proj_name = str(proj.get("name", "")).lower()
        if slug in {proj_slug, key.lower()} or want_name in {proj_name, proj_slug}:
            return key, proj
        if _slugify(str(proj.get("name", ""))) == slug:
            return key, proj

    # 3. Prefix match (e.g. "zksync" -> "zksync-era").
    for key, proj in projects.items():
        if key.lower().startswith(slug) or slug.startswith(key.lower()):
            return key, proj

    raise L2BeatFetchError(
        f"l2beat_chain_not_found: subject={subject!r} not tracked by L2Beat"
    )


def fetch(subject: str, subject_type: str, freshness_window: str) -> dict[str, Any]:
    """Fetch raw L2Beat data for one L2 chain. freshness_window is recorded for
    the downstream parser; L2Beat returns a current snapshot here.

    subject_type MUST be "chain" — L2Beat is L2-only. This is validated BEFORE
    any network call so unsupported subjects halt without touching the API.
    """
    if subject_type != SUPPORTED_SUBJECT_TYPE:
        raise L2BeatFetchError(
            f"subject_type_not_supported_by_l2beat: {subject_type!r} "
            "(L2Beat tracks L2 chains only; subject_type must be 'chain')"
        )

    headers = {"User-Agent": PUBLIC_USER_AGENT}
    url = _summary_endpoint()
    summary = _get_json(url, headers)
    projects = summary.get("projects", {})
    if not isinstance(projects, dict):
        raise L2BeatFetchError(f"l2beat_chain_not_found: malformed summary at {url}")

    resolved_slug, project = _resolve_project(projects, subject)

    return {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        "endpoint": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": {"summary": project, "resolved_slug": resolved_slug},
    }


def write_output(payload: dict[str, Any]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(payload["subject"])
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RAW_DIR / f"{slug}_{ts}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--subject", required=True)
    p.add_argument("--subject-type", required=True)
    p.add_argument("--freshness-window", required=True, choices=list(FRESHNESS_WINDOWS))
    args = p.parse_args(argv)

    payload = fetch(args.subject, args.subject_type, args.freshness_window)
    path = write_output(payload)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
