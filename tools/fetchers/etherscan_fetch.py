"""Etherscan fetcher — B.1.3 (first key-based fetcher).

Fetches chain-side data — token total supply, token info, and recent token-transfer
stats — for any token the Etherscan family covers, across EVM chains, via the V2
unified (chainid-keyed) API. Extends the coingecko_fetch reference pattern (B.1.2)
with runtime API-key reading.

Source contract: references/data_source_registry.md §3.
  - Auth: API key in the `apikey=<key>` query param, read at runtime from
    ~/.config/anamnesis/etherscan.key. The key is NEVER logged, NEVER persisted in
    the envelope (the saved `endpoint` strips apikey), and NEVER printed in errors.
  - User-Agent: public_user_agent (PII-free) — NEVER the SEC email-bearing UA
    (this host is not *.sec.gov).
  - Resolve the subject to a contract address: a 0x address (42 chars) is taken
    verbatim (lowercased), else a small in-fetcher symbol registry (USDC/USDT/DAI/
    WETH, chain 1 only for B.1.3).
  - Rate limit: free tier is 5 req/sec, per-chain quota; harness ceiling is
    1 req/0.25 sec with 50ms jitter, single concurrent request.
  - Errors: missing/empty key file -> etherscan_key_missing; status=0 "Invalid API
    Key" -> etherscan_key_invalid; subject_type=="chain" -> subject_type_unsupported;
    unknown subject -> address_resolution_failed; tokeninfo 404/NOTOK -> soft skip
    (null); 429 -> wait 60s + retry once; 5xx -> upstream_5xx_etherscan.

Output: meta/raw/etherscan/<subject_slug>_chain<id>_<utc_iso>.json containing
  {subject, subject_type, freshness_window, endpoint, fetched_at, raw_response},
  where raw_response is {tokensupply, tokeninfo, tokentx} keyed by action and the
  endpoint is the base URL with chainid but WITHOUT apikey.

Usage:
    python tools/fetchers/etherscan_fetch.py \
        --subject USDC --subject-type stablecoin --freshness-window 30d --chain-id 1
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# PII-free public User-Agent (references/data_source_registry.md §6 / Cross-cutting
# rules). Etherscan is NOT a *.sec.gov host, so the SEC email UA must never reach it;
# matches tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"
BASE = "https://api.etherscan.io/v2/api"

# API key on disk, outside the repo (registry §3 / Cross-cutting: keys never in code
# or logs). Read into memory at runtime; never persisted, never printed.
KEY_PATH = Path.home() / ".config" / "anamnesis" / "etherscan.key"

RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "etherscan"

# Harness pacing contract (registry §3): free tier is 5 req/sec, burst-unforgiving,
# so cap at 1 req/0.25 sec + 50ms jitter (~3 req/sec), single concurrent request.
# Pace BEFORE every outbound call (tokensupply, tokeninfo, tokentx).
RATE_LIMIT_SECONDS = 0.25
JITTER_SECONDS = 0.05
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

SUBJECT_TYPES = ("stablecoin", "protocol", "chain")
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")
CHAIN_IDS = (1, 137, 56, 42161, 10, 8453)

# Mini token registry — chain 1 (Ethereum mainnet) only for B.1.3. Broader, multi-chain
# resolution is a future TD. Keyed by (lowercased symbol, chain_id).
TOKEN_ADDRESSES: dict[tuple[str, int], str] = {
    ("usdc", 1): "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    ("usdt", 1): "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    ("dai", 1): "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    ("weth", 1): "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
}

_last_request_at = 0.0


class EtherscanFetchError(RuntimeError):
    """Raised on a halting condition (missing/invalid key, unsupported subject,
    address resolution failure, 5xx). Error messages NEVER carry the key value."""


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "-").replace("/", "_")


def _read_key() -> str:
    """Read and return the API key from KEY_PATH, stripped of whitespace.

    Raises EtherscanFetchError("etherscan_key_missing") if the file is absent or
    empty. CRITICAL: the error message NEVER includes the key value or the resolved
    path (which would leak the OS username) — it points at the registry instead.
    """
    try:
        key = KEY_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise EtherscanFetchError(
            "etherscan_key_missing: etherscan key required at the standard location, "
            "see registry §3"
        )
    if not key:
        raise EtherscanFetchError(
            "etherscan_key_missing: etherscan key required at the standard location, "
            "see registry §3"
        )
    return key


def _strip_key(url: str) -> str:
    """Remove the apikey=... query param from a URL before persisting/logging it."""
    # Drop `apikey=...` whether it sits mid-query (trailing &) or at the end.
    stripped = re.sub(r"([?&])apikey=[^&]*&?", r"\1", url)
    # Tidy any dangling separator left by the removal.
    return stripped.rstrip("?&")


def _resolve_address(subject: str, chain_id: int) -> str:
    """Resolve a subject to a contract address.

    A 0x address (42 chars) is returned lowercased. Otherwise the symbol is looked up
    in TOKEN_ADDRESSES for this chain. Raises address_resolution_failed if neither.
    """
    s = subject.strip()
    if s.lower().startswith("0x") and len(s) == 42:
        return s.lower()
    addr = TOKEN_ADDRESSES.get((s.lower(), chain_id))
    if addr is not None:
        # Lowercase to match the 0x path — registry §3 quirk: always lowercase
        # before hashing/comparing (some endpoints are checksum-case-sensitive).
        return addr.lower()
    raise EtherscanFetchError(
        f"address_resolution_failed: subject={subject!r} chain_id={chain_id}"
    )


def _throttle() -> None:
    """Block until at least RATE_LIMIT_SECONDS (+jitter) since the last call."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = RATE_LIMIT_SECONDS + random.uniform(0, JITTER_SECONDS) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _is_invalid_key(data: Any) -> bool:
    """True if an Etherscan response is the status=0 'Invalid API Key' rejection.

    Etherscan reports a bad key as {status:"0", message:"NOTOK", result:"Invalid API
    Key"} — the diagnostic lands in `result`, with the generic NOTOK in `message` —
    so scan both fields. The tokeninfo free-tier NOTOK ("Missing/Invalid Pro plan")
    does not contain this phrase and stays a soft skip.
    """
    if not (isinstance(data, dict) and str(data.get("status")) == "0"):
        return False
    blob = f"{data.get('message', '')} {data.get('result', '')}".lower()
    return "invalid api key" in blob


def _get_json(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    """GET with the registry §3 error contract. Returns (status_code, parsed_json).

    Halts on 5xx (upstream_5xx_etherscan) and on the Invalid API Key rejection;
    retries once after 60s on 429. 404 is returned to the caller (tokeninfo treats it
    as a soft skip). Error messages NEVER include the URL's apikey — they are stripped.
    """
    _throttle()
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code >= 500:
        raise EtherscanFetchError(
            f"upstream_5xx_etherscan: status={resp.status_code} url={_strip_key(url)}"
        )
    data = resp.json() if resp.status_code != 404 else None
    if _is_invalid_key(data):
        # Never echo the key — the rejected URL carries it, so omit the URL entirely.
        raise EtherscanFetchError("etherscan_key_invalid")
    return resp.status_code, data


def fetch(
    subject: str,
    subject_type: str,
    freshness_window: str,
    chain_id: int = 1,
) -> dict[str, Any]:
    """Fetch raw Etherscan data for one subject: tokensupply -> tokeninfo -> tokentx.

    Reads the key once, resolves the address, then makes the three calls sequentially
    through the throttle. tokeninfo 404/NOTOK is a soft skip (null). Returns the 6-key
    envelope; the persisted `endpoint` has apikey stripped.
    """
    if subject_type == "chain":
        raise EtherscanFetchError(
            "subject_type_unsupported: chain-level reads use the RPC fetcher (B.1.5)"
        )

    key = _read_key()
    address = _resolve_address(subject, chain_id)
    headers = {"User-Agent": PUBLIC_USER_AGENT}

    def _url(params: str) -> str:
        return f"{BASE}?chainid={chain_id}&{params}&apikey={key}"

    supply_url = _url(f"module=stats&action=tokensupply&contractaddress={address}")
    _, supply_raw = _get_json(supply_url, headers)

    info_url = _url(f"module=token&action=tokeninfo&contractaddress={address}")
    info_status, info_raw = _get_json(info_url, headers)
    # tokeninfo is a legacy Pro endpoint — 404 or status=0 NOTOK on the free tier is a
    # soft skip, not an error (registry §3).
    if info_status == 404 or (
        isinstance(info_raw, dict)
        and str(info_raw.get("status")) == "0"
        and str(info_raw.get("message", "")).upper() == "NOTOK"
    ):
        info_raw = None

    tokentx_url = _url(
        f"module=account&action=tokentx&contractaddress={address}"
        "&page=1&offset=100&sort=desc"
    )
    _, tokentx_raw = _get_json(tokentx_url, headers)

    return {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        # Base URL with chainid but WITHOUT apikey — the key never lands on disk.
        "endpoint": f"{BASE}?chainid={chain_id}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": {
            "tokensupply": supply_raw,
            "tokeninfo": info_raw,
            "tokentx": tokentx_raw,
        },
    }


def write_output(payload: dict[str, Any]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(payload["subject"])
    # chain id is recorded in the filename; fall back to parsing the endpoint if absent.
    chain_id = payload.get("chain_id")
    if chain_id is None:
        m = re.search(r"chainid=(\d+)", payload.get("endpoint", ""))
        chain_id = m.group(1) if m else "?"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RAW_DIR / f"{slug}_chain{chain_id}_{ts}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--subject", required=True)
    p.add_argument("--subject-type", required=True, choices=list(SUBJECT_TYPES))
    p.add_argument("--freshness-window", required=True, choices=list(FRESHNESS_WINDOWS))
    p.add_argument("--chain-id", type=int, default=1, choices=list(CHAIN_IDS))
    args = p.parse_args(argv)

    payload = fetch(
        args.subject, args.subject_type, args.freshness_window, args.chain_id
    )
    path = write_output(payload)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
