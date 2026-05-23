"""DefiLlama fetcher — B.1.1.

Fetches protocol / stablecoin / chain TVL from the DefiLlama public API
(no auth). This is the reference fetcher the remaining B.1 fetchers copy.

Source contract: references/data_source_registry.md §1.
  - Auth: none. User-Agent: public_user_agent (PII-free) — NEVER the SEC
    email-bearing UA (this host is not *.sec.gov).
  - Rate limit: undocumented upstream; harness hard rule is 1 req/sec with
    100ms jitter, single concurrent request.
  - Errors: 404 -> subject_not_found_on_defillama; 429 -> wait 60s + retry
    once; 5xx -> upstream_5xx_defillama.

Output: meta/raw/defillama/<subject_slug>_<utc_iso>.json containing
  {subject, subject_type, freshness_window, endpoint, fetched_at, raw_response}.

Usage:
    python tools/fetchers/defillama_fetch.py \
        --subject Aave --subject-type protocol --freshness-window 30d
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

# PII-free public User-Agent (references/data_source_registry.md §6 Cross-cutting
# rules). DefiLlama is NOT a *.sec.gov host, so the SEC email UA must never reach
# it; matches tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"
BASE = "https://api.llama.fi"
RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "defillama"

# Harness pacing contract (registry §1): 1 req/sec ceiling + 100ms jitter,
# single concurrent request. Pace BEFORE every outbound call.
RATE_LIMIT_SECONDS = 1.0
JITTER_SECONDS = 0.1
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

SUBJECT_TYPES = ("stablecoin", "protocol", "chain")
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")

_last_request_at = 0.0


class DefiLlamaFetchError(RuntimeError):
    """Raised on a halting upstream condition (404 / 5xx / unresolved subject)."""


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


def _endpoint(subject: str, subject_type: str) -> str:
    """Primary data endpoint for protocol/chain; stablecoin list for the lookup step."""
    if subject_type == "protocol":
        return f"{BASE}/protocol/{_slugify(subject)}"
    if subject_type == "chain":
        return f"{BASE}/v2/historicalChainTvl/{_slugify(subject)}"
    if subject_type == "stablecoin":
        # Step 1 of the two-step stablecoin path: resolve peggedAssetId by name.
        return f"{BASE}/stablecoins?includePrices=true"
    raise DefiLlamaFetchError(f"unknown subject_type: {subject_type!r}")


def _get_json(url: str, headers: dict[str, str]) -> Any:
    """GET with the registry §1 error contract. 404/5xx halt; 429 retries once."""
    _throttle()
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 404:
        raise DefiLlamaFetchError(
            f"subject_not_found_on_defillama: url={url}"
        )
    if resp.status_code >= 500:
        raise DefiLlamaFetchError(
            f"upstream_5xx_defillama: status={resp.status_code} url={url}"
        )
    resp.raise_for_status()
    return resp.json()


def _fetch_stablecoin(subject: str, headers: dict[str, str]) -> tuple[str, Any]:
    """Two-step: resolve peggedAssetId from the list, then fetch the supply chart."""
    listing = _get_json(_endpoint(subject, "stablecoin"), headers)
    wanted = subject.strip().lower()
    pegged_id = None
    for entry in listing.get("peggedAssets", []):
        if wanted in {
            str(entry.get("name", "")).lower(),
            str(entry.get("symbol", "")).lower(),
        }:
            pegged_id = entry.get("id")
            break
    if pegged_id is None:
        raise DefiLlamaFetchError(
            f"subject_not_found_on_defillama: stablecoin={subject!r} not in /stablecoins list"
        )
    chart_url = f"{BASE}/stablecoincharts/all?stablecoin={pegged_id}"
    return chart_url, _get_json(chart_url, headers)


def fetch(subject: str, subject_type: str, freshness_window: str) -> dict[str, Any]:
    """Fetch raw DefiLlama data for one subject. freshness_window is recorded for the
    downstream parser to window; DefiLlama returns full history here."""
    headers = {"User-Agent": PUBLIC_USER_AGENT}

    if subject_type == "stablecoin":
        url, raw = _fetch_stablecoin(subject, headers)
    else:
        url = _endpoint(subject, subject_type)
        raw = _get_json(url, headers)

    return {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        "endpoint": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": raw,
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
    p.add_argument("--subject-type", required=True, choices=list(SUBJECT_TYPES))
    p.add_argument("--freshness-window", required=True, choices=list(FRESHNESS_WINDOWS))
    args = p.parse_args(argv)

    payload = fetch(args.subject, args.subject_type, args.freshness_window)
    path = write_output(payload)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
