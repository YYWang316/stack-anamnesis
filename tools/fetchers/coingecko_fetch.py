"""CoinGecko fetcher — B.1.2.

Fetches spot price / market cap / 24h volume / historical price for any token
CoinGecko covers, via the Demo (free, no-key) API. Copies the defillama_fetch
reference pattern (B.1.1).

Source contract: references/data_source_registry.md §4.
  - Auth: none on this Demo no-key path. User-Agent: public_user_agent (PII-free)
    — NEVER the SEC email-bearing UA (this host is not *.sec.gov).
  - Coin ids are slug-based, not symbol-based, and symbols collide — resolve the
    subject to a coin id via /search before any data call.
  - Rate limit: free/Demo is 10-30 calls/min, burst-sensitive; harness hard rule
    is 1 req/2.5 sec with 200ms jitter, single concurrent request.
  - Errors: empty /search -> subject_not_found_on_coingecko; 404 on /coins/<id>
    -> coin_id_invalid; 429 -> wait 60s + retry once; 5xx -> upstream_5xx_coingecko.

Output: meta/raw/coingecko/<subject_slug>_<utc_iso>.json containing
  {subject, subject_type, freshness_window, endpoint, fetched_at, raw_response},
  where raw_response is {search, spot, history} keyed by call.

Usage:
    python tools/fetchers/coingecko_fetch.py \
        --subject Bitcoin --subject-type chain --freshness-window 30d
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
# rules). CoinGecko is NOT a *.sec.gov host, so the SEC email UA must never reach
# it; matches tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"
BASE = "https://api.coingecko.com/api/v3"
RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "coingecko"

# Harness pacing contract (registry §4): free/Demo tier is 10-30 calls/min and
# burst-sensitive, so cap at 1 req/2.5 sec + 200ms jitter, single concurrent
# request. Pace BEFORE every outbound call (search, spot, history).
RATE_LIMIT_SECONDS = 2.5
JITTER_SECONDS = 0.2
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

SUBJECT_TYPES = ("stablecoin", "protocol", "chain")
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")

# freshness_window -> /market_chart `days`. since_TGE -> "max" (free tier caps
# lookback at 365 days per registry §4 quirk; max returns what's allowed).
_DAYS_BY_WINDOW: dict[str, int | str] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "quarter": 90,
    "1 year": 365,
    "since_TGE": "max",
}

_last_request_at = 0.0


class CoinGeckoFetchError(RuntimeError):
    """Raised on a halting upstream condition (empty search / 404 / 5xx)."""


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "-").replace("/", "_")


def _days_from_freshness(window: str) -> int | str:
    """Map a freshness_window to the /market_chart `days` parameter."""
    try:
        return _DAYS_BY_WINDOW[window]
    except KeyError:
        raise CoinGeckoFetchError(f"unknown freshness_window: {window!r}")


def _throttle() -> None:
    """Block until at least RATE_LIMIT_SECONDS (+jitter) since the last call."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = RATE_LIMIT_SECONDS + random.uniform(0, JITTER_SECONDS) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _get_json(url: str, headers: dict[str, str]) -> Any:
    """GET with the registry §4 error contract. 404 maps to coin_id_invalid here
    (the resolve step handles empty-search separately); 5xx halts; 429 retries once."""
    _throttle()
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 404:
        raise CoinGeckoFetchError(f"coin_id_invalid: url={url}")
    if resp.status_code >= 500:
        raise CoinGeckoFetchError(
            f"upstream_5xx_coingecko: status={resp.status_code} url={url}"
        )
    resp.raise_for_status()
    return resp.json()


def _rank(entry: dict[str, Any]) -> float:
    """market_cap_rank as a sortable number; missing/None sorts last."""
    r = entry.get("market_cap_rank")
    return float(r) if isinstance(r, (int, float)) else float("inf")


def _resolve_coin_id(subject: str, headers: dict[str, str]) -> tuple[str, Any]:
    """Resolve a subject name to a CoinGecko coin id via /search.

    Returns (coin_id, raw_search_response). Picks the exact match on **symbol or
    name** (case-insensitive) with the best market_cap_rank — symbols collide
    (registry §4 quirk: a meme coin's ticker can literally be "BITCOIN"), and the
    subject may be a name ("Bitcoin") or a symbol ("BTC"), so tie-break exact hits
    by rank rather than trusting the first symbol match. Falls back to the top
    ranked coin when nothing matches exactly. Raises if /search returns no coins.
    """
    url = f"{BASE}/search?query={subject}"
    raw = _get_json(url, headers)
    coins = raw.get("coins", []) if isinstance(raw, dict) else []
    if not coins:
        raise CoinGeckoFetchError(
            f"subject_not_found_on_coingecko: subject={subject!r}"
        )
    wanted = subject.strip().lower()
    exact = [
        c
        for c in coins
        if wanted in {str(c.get("symbol", "")).lower(), str(c.get("name", "")).lower()}
    ]
    if exact:
        return str(min(exact, key=_rank)["id"]), raw
    # No exact symbol/name hit — /search ranks by relevance, so take the top coin.
    return str(min(coins, key=_rank)["id"]), raw


def fetch(subject: str, subject_type: str, freshness_window: str) -> dict[str, Any]:
    """Fetch raw CoinGecko data for one subject: resolve -> spot -> history.

    subject_type is recorded and passed through (CoinGecko has one endpoint shape
    for any coin); freshness_window maps to the history `days` and is recorded for
    the downstream parser.
    """
    headers = {"User-Agent": PUBLIC_USER_AGENT}

    coin_id, search_raw = _resolve_coin_id(subject, headers)

    spot_url = f"{BASE}/coins/{coin_id}"
    spot_raw = _get_json(spot_url, headers)

    days = _days_from_freshness(freshness_window)
    history_url = f"{BASE}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
    history_raw = _get_json(history_url, headers)

    return {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        "endpoint": spot_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": {
            "search": search_raw,
            "spot": spot_raw,
            "history": history_raw,
        },
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
