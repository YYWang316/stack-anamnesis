"""Alchemy RPC fetcher — B.1.5 (first JSON-RPC fetcher).

Fetches chain-side state via JSON-RPC — latest block number, gas price, native + token
balances, contract code, raw eth_call (e.g. totalSupply) — by POSTing JSON-RPC bodies to
a single Alchemy endpoint. This is the "deep" on-chain layer that Etherscan's API tier
does not cover (raw eth_call, eth_getStorageAt). Extends the etherscan_fetch key-handling
pattern (B.1.3) with the URL-as-key variant.

Source contract: references/data_source_registry.md §5.
  - Auth: URL-embedded key. Alchemy puts the API key in the URL PATH (/v2/<key>), so the
    whole URL is the secret. Read at runtime from ~/.config/anamnesis/alchemy.key. The URL
    is NEVER logged, NEVER persisted unredacted (the saved `endpoint` shows /v2/<REDACTED>),
    and NEVER printed in errors — everything routes through _redact_url first.
  - User-Agent: public_user_agent (PII-free) — NEVER the SEC email-bearing UA (not a
    *.sec.gov host). _select_user_agent mirrors the SEC 2-UA pattern but always returns the
    public UA for Alchemy.
  - Routing: subject_type picks a default JSON-RPC call set (CALLS). chain -> blockNumber +
    gasPrice; wallet -> getBalance + getTransactionCount; stablecoin_issuer / orchestrator
    (token contract) -> getCode + eth_call(totalSupply). agentic_payment_layer is
    unsupported in B.1.5 (broader coverage is a future TD).
  - freshness_window informs blockTag: since_TGE -> "earliest", else "latest".
  - Rate limit: free tier is 300 CU/sec (billing by compute unit, not request); harness
    ceiling is 0.5 req/sec with 50ms jitter, single concurrent request.
  - Errors: missing/empty key file -> alchemy_key_missing; URL not matching the pattern ->
    alchemy_url_malformed (URL never echoed); JSON-RPC error field -> alchemy_rpc_error
    (code + message, no URL); 401/403 -> alchemy_unauthorized; 429 -> wait 60s + retry once;
    5xx -> upstream_5xx_alchemy; agentic_payment_layer -> subject_type_unsupported.

Output: meta/raw/alchemy/<subject_slug>_chain<id>_<utc_iso>.json containing
  {subject, subject_type, freshness_window, endpoint, fetched_at, raw_response}, where
  raw_response is keyed by JSON-RPC method name and the endpoint is the REDACTED URL.

Usage:
    python tools/fetchers/alchemy_fetch.py \
        --subject ethereum --subject-type chain --freshness-window 30d
    python tools/fetchers/alchemy_fetch.py \
        --subject 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 \
        --subject-type stablecoin_issuer --freshness-window 30d
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

# PII-free public User-Agent (references/data_source_registry.md §6 / Cross-cutting rules).
# Alchemy is NOT a *.sec.gov host, so the SEC email UA must never reach it; matches
# tools/audit/user_agent_pii.py's PUBLIC_USER_AGENT.
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"

# Full Alchemy URL on disk, outside the repo (registry §5 / Cross-cutting: keys never in
# code or logs). The key is embedded in the URL PATH, so the whole file IS the secret.
# Read into memory at runtime; never persisted or printed unredacted.
KEY_PATH = Path.home() / ".config" / "anamnesis" / "alchemy.key"

# The expected Alchemy URL shape: https://<chain>-mainnet.g.alchemy.com/v2/<key>.
# Used to validate the file contents before any network call.
URL_PATTERN = re.compile(r"^https://[a-z0-9-]+\.g\.alchemy\.com/v2/[A-Za-z0-9_-]+$")

RAW_DIR = Path(__file__).resolve().parents[2] / "meta" / "raw" / "alchemy"

# Harness pacing contract (registry §5): free tier is 300 CU/sec (billing by compute unit).
# A conservative 0.5 req/sec (1 req / 2 sec) + 50ms jitter keeps a typical method mix under
# ~150 CU/sec. Pace BEFORE every outbound JSON-RPC call; single concurrent request.
RATE_LIMIT_SECONDS = 2.0
JITTER_SECONDS = 0.05
RETRY_AFTER_429_SECONDS = 60
TIMEOUT_SECONDS = 30

SUBJECT_TYPES = (
    "stablecoin_issuer",
    "orchestrator",
    "wallet",
    "chain",
    "agentic_payment_layer",
)
FRESHNESS_WINDOWS = ("7d", "30d", "90d", "quarter", "1 year", "since_TGE")

# totalSupply() ERC-20 function selector (first 4 bytes of keccak("totalSupply()")).
TOTAL_SUPPLY_SELECTOR = "0x18160ddd"

# Per-subject_type default JSON-RPC calls. Each entry is (method, params); params may carry
# the "<address>" and "<blockTag>" placeholders, substituted per-request in fetch(). For
# B.1.5: chain / wallet / token-contract reads (stablecoin_issuer and its orchestrator
# alias). agentic_payment_layer is intentionally absent -> subject_type_unsupported.
CALLS: dict[str, list[tuple[str, list[Any]]]] = {
    "chain": [
        ("eth_blockNumber", []),
        ("eth_gasPrice", []),
    ],
    "wallet": [
        ("eth_getBalance", ["<address>", "<blockTag>"]),
        ("eth_getTransactionCount", ["<address>", "<blockTag>"]),
    ],
    "stablecoin_issuer": [
        ("eth_getCode", ["<address>", "<blockTag>"]),
        ("eth_call", [{"to": "<address>", "data": TOTAL_SUPPLY_SELECTOR}, "<blockTag>"]),
    ],
    # orchestrators that have deployed contracts read the same way as a token contract
    # (registry §5 "agentic_payment_layer ... settlement-contract reads"); alias to the
    # stablecoin_issuer call set rather than duplicating it.
    "orchestrator": [
        ("eth_getCode", ["<address>", "<blockTag>"]),
        ("eth_call", [{"to": "<address>", "data": TOTAL_SUPPLY_SELECTOR}, "<blockTag>"]),
    ],
}

_last_request_at = 0.0


class AlchemyFetchError(RuntimeError):
    """Raised on a halting condition (missing/malformed key URL, unsupported subject,
    JSON-RPC error, 401/403, 5xx). Error messages NEVER carry the URL or the key value."""


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "-").replace("/", "_") or "chain"


def _redact_url(url: str) -> str:
    """Replace the /v2/<key> path segment with /v2/<REDACTED>.

    The single chokepoint for making the endpoint safe to persist or log. Used for the
    envelope's `endpoint` field AND in every error path (defense in depth). If the URL has
    no /v2/<key> segment, it is returned unchanged — callers that handle untrusted input
    (e.g. a malformed key file) must NOT pass it here; they omit the value entirely.
    """
    return re.sub(r"(/v2/)[A-Za-z0-9_-]+", r"\1<REDACTED>", url)


def _read_rpc_url() -> str:
    """Read and return the full Alchemy URL from KEY_PATH, stripped of whitespace.

    Raises AlchemyFetchError("alchemy_key_missing") if the file is absent or empty, and
    AlchemyFetchError("alchemy_url_malformed") if the contents do not match URL_PATTERN.
    CRITICAL: neither error echoes the attempted path (would leak the OS username) nor the
    malformed URL value (which may still be a mistyped real key).
    """
    try:
        url = KEY_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise AlchemyFetchError(
            "alchemy_key_missing: alchemy RPC URL required at the standard location, "
            "see registry §5"
        )
    if not url:
        raise AlchemyFetchError(
            "alchemy_key_missing: alchemy RPC URL required at the standard location, "
            "see registry §5"
        )
    if not URL_PATTERN.match(url):
        # Do NOT echo the value — it may be a mistyped real key.
        raise AlchemyFetchError(
            "alchemy_url_malformed: file at the standard location is not a valid "
            "https://<chain>-mainnet.g.alchemy.com/v2/<key> URL"
        )
    return url


def _select_user_agent(url: str) -> str:
    """User-Agent selector, mirroring the SEC fetcher's 2-UA pattern for consistency.

    Alchemy is never a *.sec.gov host, so this ALWAYS returns the PII-free public UA; the
    email-bearing SEC UA must never reach Alchemy (I-003 / registry §6). The helper exists
    so the call site reads the same as sec_edgar_fetch's, not because Alchemy needs a choice.
    """
    return PUBLIC_USER_AGENT


def _block_tag(freshness_window: str) -> str:
    """Map a freshness window to a JSON-RPC blockTag. since_TGE -> earliest, else latest.

    Full historical state at arbitrary blocks is too expensive on the free tier (registry
    §5); only the two endpoint tags are exposed here.
    """
    return "earliest" if freshness_window == "since_TGE" else "latest"


def _substitute(value: Any, address: str, block_tag: str) -> Any:
    """Recursively replace the "<address>" / "<blockTag>" placeholders in RPC params."""
    if isinstance(value, str):
        if value == "<address>":
            return address
        if value == "<blockTag>":
            return block_tag
        return value
    if isinstance(value, list):
        return [_substitute(v, address, block_tag) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, address, block_tag) for k, v in value.items()}
    return value


def _rpc_request_body(method: str, params: list[Any], request_id: int) -> dict[str, Any]:
    """Build a standard JSON-RPC 2.0 request body."""
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}


def _resolve_address(subject: str, subject_type: str) -> str:
    """Resolve the subject to an address (or "" for chain-level reads).

    chain reads ignore the subject. Every other supported subject_type requires a 0x… (42
    char) address taken verbatim, lowercased. Raises address_resolution_failed otherwise.
    """
    if subject_type == "chain":
        return ""
    s = subject.strip()
    if s.lower().startswith("0x") and len(s) == 42:
        return s.lower()
    raise AlchemyFetchError(
        f"address_resolution_failed: subject_type={subject_type} expects a 0x… address"
    )


def _call_rpc(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """POST one JSON-RPC body to the Alchemy endpoint with the registry §5 error contract.

    Throttles before the call; retries once after 60s on 429; halts on 401/403
    (alchemy_unauthorized), 5xx (upstream_5xx_alchemy), and a JSON-RPC `error` field
    (alchemy_rpc_error). NONE of these errors include the URL — it carries the key.
    """
    _throttle()
    resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429:
        time.sleep(RETRY_AFTER_429_SECONDS)
        _throttle()
        resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code in (401, 403):
        # Never echo the URL or key — report the status only.
        raise AlchemyFetchError(
            f"alchemy_unauthorized: status={resp.status_code} (key revoked or wrong network)"
        )
    if resp.status_code >= 500:
        raise AlchemyFetchError(
            f"upstream_5xx_alchemy: status={resp.status_code} url={_redact_url(url)}"
        )
    data = resp.json()
    if isinstance(data, dict) and data.get("error") is not None:
        err = data["error"]
        code = err.get("code") if isinstance(err, dict) else None
        message = err.get("message") if isinstance(err, dict) else str(err)
        # Carry code + message, NEVER the URL.
        raise AlchemyFetchError(
            f"alchemy_rpc_error: method={body.get('method')} code={code} message={message!r}"
        )
    return data


def _throttle() -> None:
    """Block until at least RATE_LIMIT_SECONDS (+jitter) since the last call."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = RATE_LIMIT_SECONDS + random.uniform(0, JITTER_SECONDS) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def fetch(
    subject: str,
    subject_type: str,
    freshness_window: str,
) -> dict[str, Any]:
    """Fetch raw Alchemy JSON-RPC state for one subject.

    Reads the URL once, resolves the address (or "" for chain), looks up the default call
    set for the subject_type, then issues each call sequentially through the throttle.
    Returns the 6-key envelope with the REDACTED URL as `endpoint`. CRITICAL: the unredacted
    URL is asserted to be absent from the serialized envelope before returning.
    """
    if subject_type == "agentic_payment_layer":
        raise AlchemyFetchError(
            "subject_type_unsupported: agentic_payment_layer RPC coverage is a future TD"
        )
    calls = CALLS.get(subject_type)
    if calls is None:
        raise AlchemyFetchError(f"subject_type_unsupported: {subject_type}")

    url = _read_rpc_url()
    address = _resolve_address(subject, subject_type)
    block_tag = _block_tag(freshness_window)
    headers = {"User-Agent": _select_user_agent(url)}

    raw_response: dict[str, Any] = {}
    for request_id, (method, params) in enumerate(calls, start=1):
        concrete = _substitute(params, address, block_tag)
        body = _rpc_request_body(method, concrete, request_id)
        raw_response[method] = _call_rpc(url, body, headers)

    envelope = {
        "subject": subject,
        "subject_type": subject_type,
        "freshness_window": freshness_window,
        # REDACTED URL — the key never lands on disk.
        "endpoint": _redact_url(url),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": raw_response,
    }

    # Defense in depth: the unredacted URL must NEVER appear in the persisted envelope.
    assert url not in json.dumps(envelope), "alchemy URL leaked into envelope"
    return envelope


def write_output(payload: dict[str, Any]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(payload["subject"])
    # Derive the chain id from the redacted endpoint's <chain>-mainnet subdomain.
    m = re.search(r"https://([a-z0-9-]+)-mainnet\.g\.alchemy\.com", payload.get("endpoint", ""))
    chain = m.group(1) if m else "eth"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RAW_DIR / f"{slug}_chain{chain}_{ts}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--subject", required=True)
    p.add_argument("--subject-type", required=True, choices=list(SUBJECT_TYPES))
    p.add_argument("--freshness-window", required=True, choices=list(FRESHNESS_WINDOWS))
    # Alchemy's chain is fixed by the URL the user provisioned (chain selected at Alchemy
    # app creation), so --chain-id is informational only; the URL is the source of truth.
    p.add_argument("--chain-id", type=int, default=1)
    args = p.parse_args(argv)

    payload = fetch(args.subject, args.subject_type, args.freshness_window)
    path = write_output(payload)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
