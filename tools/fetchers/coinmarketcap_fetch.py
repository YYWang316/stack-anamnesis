"""CoinMarketCap fetcher — B.1.6.

Fetches spot price / market cap / 24h volume (and, where the tier allows, historical
quotes) for any token CoinMarketCap covers, via the Pro v1 API on the Basic (free)
tier. Copies the coingecko_fetch reference pattern (B.1.2) for the price/market-cap
surface and the etherscan_fetch pattern (B.1.3) for runtime API-key handling.

CMC is the cross-check / fallback price source — CoinGecko (§4) is primary.

Source contract: references/data_source_registry.md §13.
  - Auth: API key required on EVERY tier, including Basic free. Sent in the
    `X-CMC_PRO_API_KEY` HEADER (not a query param), read at runtime from
    ~/.config/anamnesis/coinmarketcap.key. The key is NEVER logged, NEVER persisted in
    the envelope, and NEVER printed in errors.
  - User-Agent: public_user_agent (PII-free) — NEVER the SEC email-bearing UA (this
    host is not *.sec.gov).
  - CMC ids are numeric and differ from CoinGecko slugs, and symbols collide — resolve
    the subject to a CMC id slug-first (via /quotes/latest?slug=, since /map ignores a
    slug param) with a /map?symbol= fallback, before the spot/history calls.
  - Rate limit: Basic free is 30 req/min + credit-metered; harness ceiling is
    1 req/2 sec with 100ms jitter, single concurrent request.
  - Errors: missing/empty key file -> cmc_key_missing; 401/403 -> cmc_unauthorized
    (no key echo); empty /map -> subject_not_found_on_cmc; 429 -> wait 60s + retry
    once; 5xx -> upstream_5xx_cmc; historical 401 (free-tier restriction) -> soft skip
    (quotes_historical is null).

Output: meta/raw/coinmarketcap/<subject_slug>_<utc_iso>.json containing
  {subject, subject_type, freshness_window, endpoint, fetched_at, raw_response},
  where raw_response is {resolve, quotes_latest, quotes_historical} keyed by call
  (`resolve` holds the slug or symbol lookup that resolved the id). The key lives in
  the request header only, so the persisted URL is already key-free.

Usage:
    python tools/fetchers/coinmarketcap_fetch.py \
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

# PII-free public User-Agent (references/data_source_registry.md §6 / Cross-cutting
# rules). CoinMarketCap is NOT a *.sec.gov host, so the SEC email UA must never reach
# it; matches tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"
BASE = "https://pro-api.coinmarketcap.com/v1"

# API key on disk, outside the repo (registry §13 / Cross-cutting: keys never in code
# or logs). Read into memory at runtime, passed via header only; never persisted,
# never printed.
KEY_PATH = Path.home() / ".config" / "anamnesis" / "coinmarketcap.key"

RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "coinmarketcap"

# Harness pacing contract (registry §13): Basic free tier is 30 req/min + credit-
# metered, so cap at 1 req/2 sec + 100ms jitter (well under 30/min), single concurrent
# request. Pace BEFORE every outbound call (map, quotes_latest, quotes_historical).
RATE_LIMIT_SECONDS = 2.0
JITTER_SECONDS = 0.1
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

SUBJECT_TYPES = ("stablecoin", "protocol", "chain")
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")

# freshness_window -> /quotes/historical `count`. since_TGE -> "max".
_COUNT_BY_WINDOW: dict[str, int | str] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "quarter": 90,
    "1 year": 365,
    "since_TGE": "max",
}

_last_request_at = 0.0


class CmcFetchError(RuntimeError):
    """Raised on a halting condition (missing/invalid key, unauthorized, subject not
    found, 5xx). Error messages NEVER carry the key value or the resolved key path."""


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "-").replace("/", "_")


def _days_from_freshness(window: str) -> int | str:
    """Map a freshness_window to the /quotes/historical `count` parameter."""
    try:
        return _COUNT_BY_WINDOW[window]
    except KeyError:
        raise CmcFetchError(f"unknown freshness_window: {window!r}")


def _read_key() -> str:
    """Read and return the API key from KEY_PATH, stripped of whitespace.

    Raises CmcFetchError("cmc_key_missing") if the file is absent or empty. CRITICAL:
    the error message NEVER includes the key value or the resolved path (which would
    leak the OS username) — it points at the registry instead.
    """
    try:
        key = KEY_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise CmcFetchError(
            "cmc_key_missing: coinmarketcap key required at the standard location, "
            "see registry §13"
        )
    if not key:
        raise CmcFetchError(
            "cmc_key_missing: coinmarketcap key required at the standard location, "
            "see registry §13"
        )
    return key


def _throttle() -> None:
    """Block until at least RATE_LIMIT_SECONDS (+jitter) since the last call."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = RATE_LIMIT_SECONDS + random.uniform(0, JITTER_SECONDS) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _get_json(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    """GET with the registry §13 error contract. Returns (status_code, parsed_json).

    Halts on 5xx (upstream_5xx_cmc); retries once after 60s on 429. 401/403 is returned
    to the caller — most calls treat it as cmc_unauthorized, but the historical leg
    treats it as a free-tier soft skip. The key rides in the header, never the URL, so
    error messages may safely include the URL.
    """
    _throttle()
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code >= 500:
        raise CmcFetchError(f"upstream_5xx_cmc: status={resp.status_code} url={url}")
    try:
        data = resp.json()
    except ValueError:
        data = None
    return resp.status_code, data


def _rank(c: dict[str, Any]) -> float:
    """Market-cap rank as a sortable number; missing/None sorts last. /map calls it
    `rank`, /quotes/latest calls it `cmc_rank` — check both. Real high-cap tokens
    always carry a rank, meme-symbol collisions are rank ~900+ or rank-less."""
    r = c.get("cmc_rank")
    if r is None:
        r = c.get("rank")
    return float(r) if isinstance(r, (int, float)) else float("inf")


def _resolve_cmc_id(subject: str, headers: dict[str, str]) -> tuple[int, Any]:
    """Resolve a subject (name OR ticker) to a CoinMarketCap numeric id.

    Returns (cmc_id, resolve_raw). Symbols collide (registry §13 quirk: a meme coin's
    symbol is literally "BITCOIN", so symbol=Bitcoin returns the meme coin and only
    symbol=BTC reaches real Bitcoin), so we resolve slug-first because slug is unique
    in CMC's namespace:

      1. Try /quotes/latest?slug=<subject lowercased, spaces->dashes>. NOTE: /map
         silently IGNORES a `slug` param (returns the full list), so slug resolution
         must go through /quotes/latest, which DOES filter by slug and returns a
         {id: quote} dict. Non-empty -> take that id. (Accepts human names:
         "Bitcoin"->bitcoin->id 1, "USD Coin"->usd-coin->id 3408.) An invalid slug
         (e.g. a ticker like "btc") returns HTTP 400 with empty data -> fall through.
      2. Else fall back to /map?symbol=<subject uppercased>, which DOES filter by
         symbol; tie-break colliding candidates by lowest rank so a high-cap real coin
         beats a low-cap collision. (Accepts tickers: "BTC"->id 1, "USDC"->id 3408.)
      3. If both are empty -> subject_not_found_on_cmc.

    Raises cmc_unauthorized on 401/403 (bad key). Never echoes the key.
    """
    slug = subject.lower().strip().replace(" ", "-")
    slug_url = f"{BASE}/cryptocurrency/quotes/latest?slug={slug}"
    status, raw = _get_json(slug_url, headers)
    if status in (401, 403):
        # Never echo the key — the rejected request carried it only in the header.
        raise CmcFetchError("cmc_unauthorized")
    data = raw.get("data") if isinstance(raw, dict) else None
    if data:
        # /quotes/latest?slug= returns a {id_str: coin} dict; slug is unique so there
        # is exactly one entry. (An invalid slug yields empty data -> skipped here.)
        coin = next(iter(data.values()))
        return int(coin["id"]), raw

    symbol = subject.upper().strip()
    symbol_url = f"{BASE}/cryptocurrency/map?symbol={symbol}"
    status, raw = _get_json(symbol_url, headers)
    if status in (401, 403):
        raise CmcFetchError("cmc_unauthorized")
    candidates = raw.get("data") if isinstance(raw, dict) else None
    if candidates:
        # /map?symbol= returns a list that can collide -> tie-break by lowest rank.
        best = min(candidates, key=_rank)
        return int(best["id"]), raw

    # Neither slug nor symbol matched — CMC does not track this subject.
    raise CmcFetchError(f"subject_not_found_on_cmc: subject={subject!r}")


def fetch(subject: str, subject_type: str, freshness_window: str) -> dict[str, Any]:
    """Fetch raw CMC data for one subject: resolve -> quotes/latest -> quotes/historical.

    Reads the key once into the header, resolves the CMC id, then makes the three calls
    sequentially through the throttle. The historical leg is a soft skip on 401 (Basic
    free tier excludes it -> quotes_historical is null). Returns the 6-key envelope; the
    persisted endpoint and raw_response never carry the key (it rides in the header).
    """
    key = _read_key()
    headers = {
        "X-CMC_PRO_API_KEY": key,
        "User-Agent": PUBLIC_USER_AGENT,
        "Accept": "application/json",
    }

    cmc_id, resolve_raw = _resolve_cmc_id(subject, headers)

    spot_url = f"{BASE}/cryptocurrency/quotes/latest?id={cmc_id}"
    spot_status, spot_raw = _get_json(spot_url, headers)
    if spot_status in (401, 403):
        raise CmcFetchError("cmc_unauthorized")

    count = _days_from_freshness(freshness_window)
    history_url = f"{BASE}/cryptocurrency/quotes/historical?id={cmc_id}&count={count}"
    history_status, history_raw = _get_json(history_url, headers)
    if history_status in (401, 403):
        # Basic free tier excludes the historical endpoint — soft skip, not an error.
        history_raw = None

    envelope = {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        # Resolved spot URL — key-free because the key rides in the header only.
        "endpoint": spot_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": {
            # `resolve` holds whichever call resolved the id: a /quotes/latest?slug=
            # response (slug path) or a /map?symbol= response (symbol-fallback path).
            "resolve": resolve_raw,
            "quotes_latest": spot_raw,
            "quotes_historical": history_raw,
        },
    }

    # Defensive key-leak guard: the key must never reach disk via the envelope.
    if key in json.dumps(envelope):
        raise CmcFetchError("cmc_key_leak_detected: key present in envelope")

    return envelope


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
