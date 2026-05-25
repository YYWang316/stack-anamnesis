"""Unit + smoke tests for tools/fetchers/etherscan_fetch.py (B.1.3).

Unit tests mock the network and the on-disk key (no live calls, never the real key).
One live smoke fetch runs last and is skipped when SKIP_LIVE=1; it alone reads the
real key from the standard path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import etherscan_fetch as es

# Sentinel key used everywhere in the unit tests. NEVER the real key.
FAKE_KEY = "FAKE_KEY_FOR_TESTS"

# Canonical mainnet USDC address from the in-fetcher registry.
USDC_ADDR = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _seq_get(responses: list[_FakeResponse]):
    """Return a fake requests.get that yields the given responses in order."""

    def fake_get(*_a: Any, **_k: Any) -> _FakeResponse:
        return responses.pop(0)

    return fake_get


# Minimal valid sub-call payloads.
_SUPPLY_OK = {"status": "1", "message": "OK", "result": "44000000000000"}
_INFO_OK = {"status": "1", "message": "OK", "result": [{"symbol": "USDC"}]}
_TOKENTX_OK = {"status": "1", "message": "OK", "result": [{"hash": "0xabc"}]}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(es.time, "sleep", lambda *_: None)
    monkeypatch.setattr(es, "_last_request_at", 0.0)


@pytest.fixture()
def _fake_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point KEY_PATH at a tmp file holding FAKE_KEY."""
    key_file = tmp_path / "etherscan.key"
    key_file.write_text(FAKE_KEY + "\n", encoding="utf-8")
    monkeypatch.setattr(es, "KEY_PATH", key_file)
    return key_file


# --- _slugify ---------------------------------------------------------------

def test_slugify_simple() -> None:
    assert es._slugify("USDC") == "usdc"


# --- _read_key --------------------------------------------------------------

def test_read_key_present(_fake_key: Path) -> None:
    assert es._read_key() == FAKE_KEY


def test_read_key_strips_whitespace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "etherscan.key"
    key_file.write_text("  spaced_key  \n", encoding="utf-8")
    monkeypatch.setattr(es, "KEY_PATH", key_file)
    assert es._read_key() == "spaced_key"


def test_read_key_missing_raises_and_hides_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "secret_dir" / "etherscan.key"
    monkeypatch.setattr(es, "KEY_PATH", missing)
    with pytest.raises(es.EtherscanFetchError, match="etherscan_key_missing") as exc:
        es._read_key()
    msg = str(exc.value)
    # The error must not leak the attempted path (home/username).
    assert str(missing) not in msg
    assert str(Path.home()) not in msg
    assert "secret_dir" not in msg


def test_read_key_empty_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "etherscan.key"
    key_file.write_text("   \n", encoding="utf-8")
    monkeypatch.setattr(es, "KEY_PATH", key_file)
    with pytest.raises(es.EtherscanFetchError, match="etherscan_key_missing"):
        es._read_key()


# --- _strip_key -------------------------------------------------------------

def test_strip_key_trailing() -> None:
    url = "https://api.etherscan.io/v2/api?chainid=1&module=stats&apikey=ABC123"
    assert es._strip_key(url) == (
        "https://api.etherscan.io/v2/api?chainid=1&module=stats"
    )


def test_strip_key_midquery() -> None:
    url = "https://api.etherscan.io/v2/api?apikey=ABC123&chainid=1"
    out = es._strip_key(url)
    assert "ABC123" not in out
    assert "apikey" not in out
    assert "chainid=1" in out


# --- _resolve_address -------------------------------------------------------

def test_resolve_address_known_symbol() -> None:
    assert es._resolve_address("USDC", 1) == USDC_ADDR


def test_resolve_address_0x_lowercased() -> None:
    addr = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
    assert es._resolve_address(addr, 1) == addr.lower()


def test_resolve_address_unknown_symbol_raises() -> None:
    with pytest.raises(es.EtherscanFetchError, match="address_resolution_failed"):
        es._resolve_address("NOTACOIN", 1)


def test_resolve_address_known_symbol_wrong_chain_raises() -> None:
    # USDC is only registered on chain 1 for B.1.3.
    with pytest.raises(es.EtherscanFetchError, match="address_resolution_failed"):
        es._resolve_address("USDC", 137)


# --- fetch: success ---------------------------------------------------------

def test_fetch_200_returns_full_envelope(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    monkeypatch.setattr(
        es.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(200, _SUPPLY_OK),
                _FakeResponse(200, _INFO_OK),
                _FakeResponse(200, _TOKENTX_OK),
            ]
        ),
    )

    payload = es.fetch("USDC", "stablecoin", "30d", chain_id=1)

    assert set(payload) == {
        "subject",
        "subject_type",
        "freshness_window",
        "endpoint",
        "fetched_at",
        "raw_response",
    }
    assert payload["subject"] == "USDC"
    assert payload["subject_type"] == "stablecoin"
    assert payload["freshness_window"] == "30d"
    assert payload["endpoint"] == "https://api.etherscan.io/v2/api?chainid=1"
    assert set(payload["raw_response"]) == {"tokensupply", "tokeninfo", "tokentx"}
    assert payload["raw_response"]["tokensupply"] == _SUPPLY_OK
    assert payload["raw_response"]["tokeninfo"] == _INFO_OK
    assert payload["raw_response"]["tokentx"] == _TOKENTX_OK


def test_fetch_strips_key_from_envelope(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # The key-leak guard: FAKE_KEY must not appear ANYWHERE in the serialized payload,
    # including the endpoint field, even though every outbound URL carries it.
    monkeypatch.setattr(
        es.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(200, _SUPPLY_OK),
                _FakeResponse(200, _INFO_OK),
                _FakeResponse(200, _TOKENTX_OK),
            ]
        ),
    )

    payload = es.fetch("USDC", "stablecoin", "30d", chain_id=1)
    serialized = json.dumps(payload)

    assert FAKE_KEY not in serialized
    assert "apikey" not in serialized
    assert payload["endpoint"] == "https://api.etherscan.io/v2/api?chainid=1"


def test_fetch_sends_apikey_in_request_url(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # The key DOES go out on the wire (query param) — it just never lands on disk.
    urls: list[str] = []

    def fake_get(url: str, **_: Any) -> _FakeResponse:
        urls.append(url)
        return _FakeResponse(200, _SUPPLY_OK)

    monkeypatch.setattr(es.requests, "get", fake_get)

    es.fetch("USDC", "stablecoin", "30d", chain_id=1)

    assert all(f"apikey={FAKE_KEY}" in u for u in urls)
    assert all("chainid=1" in u for u in urls)


def test_fetch_handles_invalid_key(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    monkeypatch.setattr(
        es.requests,
        "get",
        lambda *a, **k: _FakeResponse(
            200, {"status": "0", "message": "NOTOK", "result": "Invalid API Key"}
        ),
    )
    with pytest.raises(es.EtherscanFetchError, match="etherscan_key_invalid") as exc:
        es.fetch("USDC", "stablecoin", "30d", chain_id=1)
    # The rejection error must never echo the key.
    assert FAKE_KEY not in str(exc.value)


def test_fetch_tokeninfo_404_soft_skip(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # tokeninfo 404s (legacy Pro endpoint on free tier) but supply + tokentx succeed.
    monkeypatch.setattr(
        es.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(200, _SUPPLY_OK),
                _FakeResponse(404),
                _FakeResponse(200, _TOKENTX_OK),
            ]
        ),
    )

    payload = es.fetch("USDC", "stablecoin", "30d", chain_id=1)

    assert payload["raw_response"]["tokeninfo"] is None
    assert payload["raw_response"]["tokensupply"] == _SUPPLY_OK
    assert payload["raw_response"]["tokentx"] == _TOKENTX_OK


def test_fetch_tokeninfo_notok_soft_skip(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # tokeninfo returns status=0 NOTOK (free-tier rejection) -> soft skip, not error.
    notok = {"status": "0", "message": "NOTOK", "result": "Missing/Invalid Pro plan"}
    monkeypatch.setattr(
        es.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(200, _SUPPLY_OK),
                _FakeResponse(200, notok),
                _FakeResponse(200, _TOKENTX_OK),
            ]
        ),
    )

    payload = es.fetch("USDC", "stablecoin", "30d", chain_id=1)

    assert payload["raw_response"]["tokeninfo"] is None


def test_fetch_429_retries_once_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    monkeypatch.setattr(
        es.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(429),
                _FakeResponse(200, _SUPPLY_OK),
                _FakeResponse(200, _INFO_OK),
                _FakeResponse(200, _TOKENTX_OK),
            ]
        ),
    )

    payload = es.fetch("USDC", "stablecoin", "30d", chain_id=1)

    assert payload["raw_response"]["tokensupply"] == _SUPPLY_OK
    assert payload["raw_response"]["tokentx"] == _TOKENTX_OK


def test_fetch_500_raises_upstream_5xx(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    monkeypatch.setattr(
        es.requests, "get", lambda *a, **k: _FakeResponse(503)
    )
    with pytest.raises(es.EtherscanFetchError, match="upstream_5xx_etherscan") as exc:
        es.fetch("USDC", "stablecoin", "30d", chain_id=1)
    # 5xx error message strips the apikey from the URL it reports.
    assert FAKE_KEY not in str(exc.value)
    assert "apikey" not in str(exc.value)


def test_fetch_subject_type_chain_unsupported(_fake_key: Path) -> None:
    with pytest.raises(es.EtherscanFetchError, match="subject_type_unsupported"):
        es.fetch("Ethereum", "chain", "30d", chain_id=1)


def test_fetch_missing_key_halts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "nope" / "etherscan.key"
    monkeypatch.setattr(es, "KEY_PATH", missing)
    # No network call should be reached; key read happens first.
    monkeypatch.setattr(
        es.requests,
        "get",
        lambda *a, **k: pytest.fail("network reached despite missing key"),
    )
    with pytest.raises(es.EtherscanFetchError, match="etherscan_key_missing"):
        es.fetch("USDC", "stablecoin", "30d", chain_id=1)


# --- write_output -----------------------------------------------------------

def test_write_output_lands_under_meta_raw_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(es, "RAW_DIR", tmp_path / "meta" / "raw" / "etherscan")
    payload = {
        "subject": "USDC",
        "subject_type": "stablecoin",
        "freshness_window": "30d",
        "endpoint": "https://api.etherscan.io/v2/api?chainid=1",
        "fetched_at": "2026-05-25T00:00:00+00:00",
        "raw_response": {"tokensupply": {}, "tokeninfo": None, "tokentx": {}},
    }

    out = es.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "etherscan"
    assert out.name.startswith("usdc_chain1_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_usdc_chain1() -> None:
    # Reads the REAL key from the standard path (skipped if absent).
    if not es.KEY_PATH.exists():
        pytest.skip("no etherscan key at the standard location")
    payload = es.fetch("USDC", "stablecoin", "30d", chain_id=1)
    assert payload["subject_type"] == "stablecoin"
    assert set(payload["raw_response"]) == {"tokensupply", "tokeninfo", "tokentx"}
    assert payload["endpoint"] == "https://api.etherscan.io/v2/api?chainid=1"
    # tokensupply is a free-tier endpoint and should return a numeric result string.
    supply = payload["raw_response"]["tokensupply"]
    assert isinstance(supply, dict) and str(supply.get("status")) == "1"
