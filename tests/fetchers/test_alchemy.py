"""Unit + smoke tests for tools/fetchers/alchemy_fetch.py (B.1.5).

Unit tests mock the network and the on-disk URL (no live calls, NEVER the real URL).
One live smoke fetch runs last and is skipped when SKIP_LIVE=1; it alone reads the real
Alchemy URL from the standard path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import alchemy_fetch as al

# Sentinel URL used everywhere in the unit tests. NEVER the real URL. The /v2/ segment is
# deliberately long enough to look key-like for the leak-guard assertions.
FAKE_URL = "https://eth-mainnet.g.alchemy.com/v2/FAKE_KEY_FOR_TESTS"
REDACTED = "https://eth-mainnet.g.alchemy.com/v2/<REDACTED>"

# A canonical mainnet token + wallet address for routing tests.
USDC_ADDR = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _seq_post(responses: list[_FakeResponse]):
    """Return a fake requests.post that yields the given responses in order."""

    def fake_post(*_a: Any, **_k: Any) -> _FakeResponse:
        return responses.pop(0)

    return fake_post


# Minimal valid JSON-RPC result payloads.
def _rpc_ok(result: Any, request_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(al.time, "sleep", lambda *_: None)
    monkeypatch.setattr(al, "_last_request_at", 0.0)


@pytest.fixture()
def _fake_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point KEY_PATH at a tmp file holding FAKE_URL."""
    key_file = tmp_path / "alchemy.key"
    key_file.write_text(FAKE_URL + "\n", encoding="utf-8")
    monkeypatch.setattr(al, "KEY_PATH", key_file)
    return key_file


# --- _slugify ---------------------------------------------------------------

def test_slugify_address() -> None:
    assert al._slugify(USDC_ADDR) == USDC_ADDR


def test_slugify_empty_subject_falls_back_to_chain() -> None:
    # chain subject is empty/placeholder; the slug must still be a usable filename token.
    assert al._slugify("") == "chain"


# --- _redact_url (security-critical) ----------------------------------------

def test_redact_url() -> None:
    assert al._redact_url(FAKE_URL) == REDACTED


def test_redact_url_other_chain() -> None:
    url = "https://base-mainnet.g.alchemy.com/v2/SomeLongKey_1234"
    assert al._redact_url(url) == "https://base-mainnet.g.alchemy.com/v2/<REDACTED>"


# --- _read_rpc_url ----------------------------------------------------------

def test_read_url_present(_fake_url: Path) -> None:
    assert al._read_rpc_url() == FAKE_URL


def test_read_url_strips_whitespace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "alchemy.key"
    key_file.write_text(f"  {FAKE_URL}  \n", encoding="utf-8")
    monkeypatch.setattr(al, "KEY_PATH", key_file)
    assert al._read_rpc_url() == FAKE_URL


def test_read_url_missing_no_path_echo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "secret_dir" / "alchemy.key"
    monkeypatch.setattr(al, "KEY_PATH", missing)
    with pytest.raises(al.AlchemyFetchError, match="alchemy_key_missing") as exc:
        al._read_rpc_url()
    msg = str(exc.value)
    assert str(missing) not in msg
    assert str(Path.home()) not in msg
    assert "secret_dir" not in msg


def test_read_url_empty_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "alchemy.key"
    key_file.write_text("   \n", encoding="utf-8")
    monkeypatch.setattr(al, "KEY_PATH", key_file)
    with pytest.raises(al.AlchemyFetchError, match="alchemy_key_missing"):
        al._read_rpc_url()


def test_read_url_malformed_no_echo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "alchemy.key"
    key_file.write_text("not-a-url\n", encoding="utf-8")
    monkeypatch.setattr(al, "KEY_PATH", key_file)
    with pytest.raises(al.AlchemyFetchError, match="alchemy_url_malformed") as exc:
        al._read_rpc_url()
    # The malformed value must never be echoed (it may be a mistyped real key).
    assert "not-a-url" not in str(exc.value)


# --- _select_user_agent -----------------------------------------------------

def test_select_user_agent_always_public() -> None:
    # Alchemy never gets the SEC email UA — the helper exists only for call-site parity.
    assert al._select_user_agent(FAKE_URL) == al.PUBLIC_USER_AGENT


# --- _block_tag -------------------------------------------------------------

def test_block_tag_since_tge_is_earliest() -> None:
    assert al._block_tag("since_TGE") == "earliest"


def test_block_tag_other_windows_latest() -> None:
    assert al._block_tag("30d") == "latest"
    assert al._block_tag("1 year") == "latest"


# --- _rpc_request_body ------------------------------------------------------

def test_rpc_request_body_shape() -> None:
    body = al._rpc_request_body("eth_blockNumber", [], 1)
    assert body == {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}


def test_substitute_placeholders() -> None:
    params = [{"to": "<address>", "data": "0x18160ddd"}, "<blockTag>"]
    out = al._substitute(params, USDC_ADDR, "latest")
    assert out == [{"to": USDC_ADDR, "data": "0x18160ddd"}, "latest"]


# --- _resolve_address -------------------------------------------------------

def test_resolve_address_chain_empty() -> None:
    assert al._resolve_address("ethereum", "chain") == ""


def test_resolve_address_0x_lowercased() -> None:
    addr = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
    assert al._resolve_address(addr, "wallet") == addr.lower()


def test_resolve_address_non_address_raises() -> None:
    with pytest.raises(al.AlchemyFetchError, match="address_resolution_failed"):
        al._resolve_address("USDC", "stablecoin_issuer")


# --- fetch: routing ---------------------------------------------------------

def test_calls_chain_subject(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    bodies: list[dict[str, Any]] = []

    def fake_post(url: str, **kw: Any) -> _FakeResponse:
        bodies.append(kw["json"])
        return _rpc_resp(kw["json"])

    def _rpc_resp(body: dict[str, Any]) -> _FakeResponse:
        return _FakeResponse(200, _rpc_ok("0x10", body["id"]))

    monkeypatch.setattr(al.requests, "post", fake_post)

    payload = al.fetch("ethereum", "chain", "30d")

    methods = [b["method"] for b in bodies]
    assert methods == ["eth_blockNumber", "eth_gasPrice"]
    assert set(payload["raw_response"]) == {"eth_blockNumber", "eth_gasPrice"}
    # chain calls take no address param.
    assert all(b["params"] == [] for b in bodies)


def test_calls_wallet_subject(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    bodies: list[dict[str, Any]] = []

    def fake_post(url: str, **kw: Any) -> _FakeResponse:
        bodies.append(kw["json"])
        return _FakeResponse(200, _rpc_ok("0x0", kw["json"]["id"]))

    monkeypatch.setattr(al.requests, "post", fake_post)

    al.fetch(USDC_ADDR, "wallet", "30d")

    methods = [b["method"] for b in bodies]
    assert methods == ["eth_getBalance", "eth_getTransactionCount"]
    # the address is substituted into the first positional param, with "latest" blockTag.
    assert bodies[0]["params"] == [USDC_ADDR, "latest"]


def test_calls_stablecoin_subject(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    bodies: list[dict[str, Any]] = []

    def fake_post(url: str, **kw: Any) -> _FakeResponse:
        bodies.append(kw["json"])
        return _FakeResponse(200, _rpc_ok("0x", kw["json"]["id"]))

    monkeypatch.setattr(al.requests, "post", fake_post)

    al.fetch(USDC_ADDR, "stablecoin_issuer", "30d")

    methods = [b["method"] for b in bodies]
    assert methods == ["eth_getCode", "eth_call"]
    # eth_call carries the totalSupply() selector against the contract address.
    call_params = bodies[1]["params"]
    assert call_params[0] == {"to": USDC_ADDR, "data": al.TOTAL_SUPPLY_SELECTOR}
    assert call_params[1] == "latest"


def test_block_tag_threads_through_since_tge(
    monkeypatch: pytest.MonkeyPatch, _fake_url: Path
) -> None:
    bodies: list[dict[str, Any]] = []

    def fake_post(url: str, **kw: Any) -> _FakeResponse:
        bodies.append(kw["json"])
        return _FakeResponse(200, _rpc_ok("0x0", kw["json"]["id"]))

    monkeypatch.setattr(al.requests, "post", fake_post)

    al.fetch(USDC_ADDR, "wallet", "since_TGE")

    assert bodies[0]["params"] == [USDC_ADDR, "earliest"]


def test_unsupported_subject_type(_fake_url: Path) -> None:
    with pytest.raises(al.AlchemyFetchError, match="subject_type_unsupported"):
        al.fetch("anything", "agentic_payment_layer", "30d")


# --- fetch: success envelope + key-leak guard (security-critical) -----------

def test_fetch_returns_full_envelope(
    monkeypatch: pytest.MonkeyPatch, _fake_url: Path
) -> None:
    monkeypatch.setattr(
        al.requests,
        "post",
        _seq_post([_FakeResponse(200, _rpc_ok("0x10")), _FakeResponse(200, _rpc_ok("0x5"))]),
    )

    payload = al.fetch("ethereum", "chain", "30d")

    assert set(payload) == {
        "subject",
        "subject_type",
        "freshness_window",
        "endpoint",
        "fetched_at",
        "raw_response",
    }
    assert payload["subject"] == "ethereum"
    assert payload["subject_type"] == "chain"
    assert payload["freshness_window"] == "30d"
    assert payload["endpoint"] == REDACTED


def test_fetch_url_never_in_envelope(
    monkeypatch: pytest.MonkeyPatch, _fake_url: Path
) -> None:
    # THE security guard: the unredacted URL (key in path) must not appear ANYWHERE in the
    # serialized envelope, even though every outbound POST targets it.
    monkeypatch.setattr(
        al.requests,
        "post",
        _seq_post([_FakeResponse(200, _rpc_ok("0x10")), _FakeResponse(200, _rpc_ok("0x5"))]),
    )

    payload = al.fetch("ethereum", "chain", "30d")
    serialized = json.dumps(payload)

    assert FAKE_URL not in serialized
    assert "FAKE_KEY_FOR_TESTS" not in serialized
    assert payload["endpoint"] == REDACTED


def test_fetch_posts_to_full_url(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    # The full URL DOES go out on the wire (it is the endpoint) — it just never lands on disk.
    urls: list[str] = []

    def fake_post(url: str, **kw: Any) -> _FakeResponse:
        urls.append(url)
        return _FakeResponse(200, _rpc_ok("0x10", kw["json"]["id"]))

    monkeypatch.setattr(al.requests, "post", fake_post)

    al.fetch("ethereum", "chain", "30d")

    assert urls and all(u == FAKE_URL for u in urls)


def test_fetch_sends_public_user_agent(
    monkeypatch: pytest.MonkeyPatch, _fake_url: Path
) -> None:
    seen: list[str] = []

    def fake_post(url: str, **kw: Any) -> _FakeResponse:
        seen.append(kw["headers"]["User-Agent"])
        return _FakeResponse(200, _rpc_ok("0x10", kw["json"]["id"]))

    monkeypatch.setattr(al.requests, "post", fake_post)

    al.fetch("ethereum", "chain", "30d")

    assert seen and all(ua == al.PUBLIC_USER_AGENT for ua in seen)


# --- fetch: error contract --------------------------------------------------

def test_rpc_error_response_halts(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    err = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "boom"}}
    monkeypatch.setattr(al.requests, "post", lambda *a, **k: _FakeResponse(200, err))
    with pytest.raises(al.AlchemyFetchError, match="alchemy_rpc_error") as exc:
        al.fetch("ethereum", "chain", "30d")
    # carries code + message, never the URL.
    assert "-32000" in str(exc.value)
    assert FAKE_URL not in str(exc.value)


def test_rpc_401_unauthorized_no_url_echo(
    monkeypatch: pytest.MonkeyPatch, _fake_url: Path
) -> None:
    monkeypatch.setattr(al.requests, "post", lambda *a, **k: _FakeResponse(401))
    with pytest.raises(al.AlchemyFetchError, match="alchemy_unauthorized") as exc:
        al.fetch("ethereum", "chain", "30d")
    assert FAKE_URL not in str(exc.value)
    assert "FAKE_KEY_FOR_TESTS" not in str(exc.value)


def test_rpc_403_unauthorized(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    monkeypatch.setattr(al.requests, "post", lambda *a, **k: _FakeResponse(403))
    with pytest.raises(al.AlchemyFetchError, match="alchemy_unauthorized"):
        al.fetch("ethereum", "chain", "30d")


def test_429_retry_once_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, _fake_url: Path
) -> None:
    monkeypatch.setattr(
        al.requests,
        "post",
        _seq_post(
            [
                _FakeResponse(429),
                _FakeResponse(200, _rpc_ok("0x10")),
                _FakeResponse(200, _rpc_ok("0x5")),
            ]
        ),
    )

    payload = al.fetch("ethereum", "chain", "30d")

    assert set(payload["raw_response"]) == {"eth_blockNumber", "eth_gasPrice"}


def test_500_upstream(monkeypatch: pytest.MonkeyPatch, _fake_url: Path) -> None:
    monkeypatch.setattr(al.requests, "post", lambda *a, **k: _FakeResponse(503))
    with pytest.raises(al.AlchemyFetchError, match="upstream_5xx_alchemy") as exc:
        al.fetch("ethereum", "chain", "30d")
    # the redacted URL may appear, but never the key.
    assert "FAKE_KEY_FOR_TESTS" not in str(exc.value)


def test_fetch_missing_url_halts_before_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "nope" / "alchemy.key"
    monkeypatch.setattr(al, "KEY_PATH", missing)
    monkeypatch.setattr(
        al.requests,
        "post",
        lambda *a, **k: pytest.fail("network reached despite missing url"),
    )
    with pytest.raises(al.AlchemyFetchError, match="alchemy_key_missing"):
        al.fetch("ethereum", "chain", "30d")


# --- write_output -----------------------------------------------------------

def test_write_output_lands_under_meta_raw_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(al, "RAW_DIR", tmp_path / "meta" / "raw" / "alchemy")
    payload = {
        "subject": "ethereum",
        "subject_type": "chain",
        "freshness_window": "30d",
        "endpoint": REDACTED,
        "fetched_at": "2026-05-25T00:00:00+00:00",
        "raw_response": {"eth_blockNumber": {}, "eth_gasPrice": {}},
    }

    out = al.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "alchemy"
    assert out.name.startswith("ethereum_chaineth_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_chain() -> None:
    # Reads the REAL Alchemy URL from the standard path (skipped if absent). Chain-level
    # reads only (eth_blockNumber + eth_gasPrice) — minimal CU cost.
    if not al.KEY_PATH.exists():
        pytest.skip("no alchemy url at the standard location")
    try:
        payload = al.fetch("ethereum", "chain", "30d")
    except al.AlchemyFetchError as exc:
        # An unmet live precondition (network not enabled on the app, key revoked) is a
        # 403 surfaced as alchemy_unauthorized — skip rather than fail, the same way the
        # missing-key case skips. The auth-rejection path itself is covered by the unit
        # tests test_rpc_401_unauthorized_no_url_echo / test_rpc_403_unauthorized.
        if "alchemy_unauthorized" in str(exc):
            pytest.skip("alchemy app reachable but the network/key is not enabled (403)")
        raise
    assert payload["subject_type"] == "chain"
    assert set(payload["raw_response"]) == {"eth_blockNumber", "eth_gasPrice"}
    assert payload["endpoint"].endswith("/v2/<REDACTED>")
    # the real URL must never appear in the serialized envelope.
    real = al.KEY_PATH.read_text(encoding="utf-8").strip()
    assert real not in json.dumps(payload)
    block = payload["raw_response"]["eth_blockNumber"]
    assert isinstance(block, dict) and isinstance(block.get("result"), str)
    assert block["result"].startswith("0x")
