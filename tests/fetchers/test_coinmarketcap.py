"""Unit + smoke tests for tools/fetchers/coinmarketcap_fetch.py (B.1.6).

Unit tests mock the network and the on-disk key (no live calls, never the real key).
One live smoke fetch runs last and is skipped when SKIP_LIVE=1; it alone reads the
real key from the standard path.

Resolution is slug-first via /quotes/latest?slug= (returns a {id: quote} dict) with a
/map?symbol= fallback (returns a candidate list) — see the fetcher docstring for why
/map?slug= cannot be used (it silently ignores the slug param).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import coinmarketcap_fetch as cmc

# Sentinel key used everywhere in the unit tests. NEVER the real key.
FAKE_CMC_KEY = "FAKE_CMC_KEY_FOR_TESTS"


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


# --- canonical sub-call payloads (CMC Pro v1 shapes) ------------------------
# /quotes/latest?slug=bitcoin -> data is a {id_str: coin} dict (slug is unique).
_SLUG_BTC = {
    "status": {"error_code": 0, "error_message": None},
    "data": {"1": {"id": 1, "name": "Bitcoin", "symbol": "BTC", "slug": "bitcoin", "cmc_rank": 1}},
}
# /quotes/latest?id=... -> spot quote, keyed by id.
_LATEST_OK = {
    "status": {"error_code": 0},
    "data": {"1": {"id": 1, "quote": {"USD": {"price": 68000.0, "market_cap": 1.3e12}}}},
}
_HISTORICAL_OK = {
    "status": {"error_code": 0},
    "data": {"quotes": [{"timestamp": "2026-05-01T00:00:00Z"}]},
}
# /map?symbol=BTC -> candidate list; `rank` (NOT cmc_rank) on the map endpoint.
_MAP_SYMBOL_BTC = {
    "status": {"error_code": 0},
    "data": [
        {"id": 25220, "symbol": "BITCOIN", "slug": "harrypotter...", "rank": 900},
        {"id": 1, "symbol": "BTC", "slug": "bitcoin", "rank": 1},
    ],
}
# /map?symbol=USDC -> single candidate.
_MAP_SYMBOL_USDC = {
    "status": {"error_code": 0},
    "data": [{"id": 3408, "symbol": "USDC", "slug": "usd-coin", "rank": 7}],
}
# Empty data (an invalid slug 400s with empty data, triggering the symbol fallback).
_EMPTY = {"status": {"error_code": 400, "error_message": "Invalid value for 'slug'"}, "data": []}


def _make_get(
    slug: Any = _SLUG_BTC,
    slug_status: int = 200,
    symbol: Any = None,
    symbol_status: int = 200,
    latest: Any = _LATEST_OK,
    latest_status: int = 200,
    hist: Any = _HISTORICAL_OK,
    hist_status: int = 200,
    record: list | None = None,
):
    """A fake requests.get that routes by URL across the 3-4 calls a fetch makes:
    slug resolve (/quotes/latest?slug=), symbol fallback (/map?symbol=), spot
    (/quotes/latest?id=), and history (/quotes/historical)."""

    def fake_get(url: str, headers: dict[str, str] | None = None, **_: Any) -> _FakeResponse:
        if record is not None:
            record.append((url, headers or {}))
        if "slug=" in url:
            return _FakeResponse(slug_status, slug)
        if "/map" in url:
            return _FakeResponse(symbol_status, symbol)
        if "historical" in url:
            return _FakeResponse(hist_status, hist)
        return _FakeResponse(latest_status, latest)

    return fake_get


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the 1 req/2 sec throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(cmc.time, "sleep", lambda *_: None)
    monkeypatch.setattr(cmc, "_last_request_at", 0.0)


@pytest.fixture()
def _fake_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point KEY_PATH at a tmp file holding FAKE_CMC_KEY."""
    key_file = tmp_path / "coinmarketcap.key"
    key_file.write_text(FAKE_CMC_KEY + "\n", encoding="utf-8")
    monkeypatch.setattr(cmc, "KEY_PATH", key_file)
    return key_file


# --- _slugify ---------------------------------------------------------------

def test_slugify_simple() -> None:
    assert cmc._slugify("USDC") == "usdc"


def test_slugify_spaces() -> None:
    assert cmc._slugify("USD Coin") == "usd-coin"


# --- _days_from_freshness ---------------------------------------------------

def test_days_from_freshness_numeric_windows() -> None:
    assert cmc._days_from_freshness("7d") == 7
    assert cmc._days_from_freshness("30d") == 30
    assert cmc._days_from_freshness("90d") == 90


def test_days_from_freshness_aliases() -> None:
    assert cmc._days_from_freshness("quarter") == 90
    assert cmc._days_from_freshness("1 year") == 365
    assert cmc._days_from_freshness("since_TGE") == "max"


def test_days_from_freshness_unknown_raises() -> None:
    with pytest.raises(cmc.CmcFetchError):
        cmc._days_from_freshness("forever")


# --- _rank ------------------------------------------------------------------

def test_rank_prefers_cmc_rank_then_rank_then_inf() -> None:
    assert cmc._rank({"cmc_rank": 1}) == 1.0          # quotes/latest field
    assert cmc._rank({"rank": 7}) == 7.0              # /map field
    assert cmc._rank({"cmc_rank": 1, "rank": 9}) == 1.0  # cmc_rank wins
    assert cmc._rank({}) == float("inf")              # rank-less sorts last


# --- _read_key --------------------------------------------------------------

def test_read_key_present(_fake_key: Path) -> None:
    assert cmc._read_key() == FAKE_CMC_KEY


def test_read_key_strips_whitespace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "coinmarketcap.key"
    key_file.write_text("  spaced_key  \n", encoding="utf-8")
    monkeypatch.setattr(cmc, "KEY_PATH", key_file)
    assert cmc._read_key() == "spaced_key"


def test_read_key_missing_raises_and_hides_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "secret_dir" / "coinmarketcap.key"
    monkeypatch.setattr(cmc, "KEY_PATH", missing)
    with pytest.raises(cmc.CmcFetchError, match="cmc_key_missing") as exc:
        cmc._read_key()
    msg = str(exc.value)
    # The error must not leak the attempted path (home/username).
    assert str(missing) not in msg
    assert str(Path.home()) not in msg
    assert "secret_dir" not in msg


def test_read_key_empty_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "coinmarketcap.key"
    key_file.write_text("   \n", encoding="utf-8")
    monkeypatch.setattr(cmc, "KEY_PATH", key_file)
    with pytest.raises(cmc.CmcFetchError, match="cmc_key_missing"):
        cmc._read_key()


# --- _resolve_cmc_id --------------------------------------------------------

def test_resolve_cmc_id_slug_first_for_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subject 'Bitcoin' must resolve via the slug endpoint -> id=1, never touching
    /map?symbol= (which would return the symbol='BITCOIN' meme coin; registry §13)."""
    calls: list[str] = []

    def fake_get(url, *args, **kwargs):
        calls.append(url)
        return _FakeResponse(200, _SLUG_BTC)

    monkeypatch.setattr(cmc.requests, "get", fake_get)
    coin_id, raw = cmc._resolve_cmc_id("Bitcoin", {"User-Agent": "x"})

    assert coin_id == 1
    assert raw == _SLUG_BTC
    # Verify the slug endpoint was hit (on /quotes/latest), NOT the symbol fallback.
    assert any("slug=bitcoin" in u for u in calls)
    assert not any("symbol=" in u for u in calls)


def test_resolve_cmc_id_symbol_fallback_when_slug_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subject 'BTC' — slug=btc returns empty (invalid slug), then /map?symbol=BTC
    must resolve to the rank-1 real coin, not the rank-900 meme collision."""
    responses = iter([
        _FakeResponse(400, _EMPTY),          # /quotes/latest?slug=btc -> empty
        _FakeResponse(200, _MAP_SYMBOL_BTC),  # /map?symbol=BTC -> collision list
    ])
    calls: list[str] = []

    def fake_get(url, *args, **kwargs):
        calls.append(url)
        return next(responses)

    monkeypatch.setattr(cmc.requests, "get", fake_get)
    coin_id, raw = cmc._resolve_cmc_id("BTC", {"User-Agent": "x"})

    assert coin_id == 1  # rank-1 wins the tiebreak over the rank-900 meme coin
    assert raw == _MAP_SYMBOL_BTC
    assert any("slug=btc" in u for u in calls)
    assert any("/map?symbol=BTC" in u for u in calls)


def test_resolve_cmc_id_both_empty_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both slug and symbol return empty -> raise subject_not_found_on_cmc."""
    monkeypatch.setattr(
        cmc.requests, "get",
        lambda *a, **k: _FakeResponse(200, {"status": {"error_code": 0}, "data": []}),
    )
    with pytest.raises(cmc.CmcFetchError, match="subject_not_found_on_cmc"):
        cmc._resolve_cmc_id("DoesNotExist", {"User-Agent": "x"})


def test_resolve_cmc_id_401_unauthorized_no_key_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cmc.requests,
        "get",
        lambda *a, **k: _FakeResponse(401, {"status": {"error_code": 1001}}),
    )
    with pytest.raises(cmc.CmcFetchError, match="cmc_unauthorized") as exc:
        cmc._resolve_cmc_id("Bitcoin", {"X-CMC_PRO_API_KEY": FAKE_CMC_KEY})
    assert FAKE_CMC_KEY not in str(exc.value)


# --- fetch: success ---------------------------------------------------------

def test_fetch_full_flow(monkeypatch: pytest.MonkeyPatch, _fake_key: Path) -> None:
    # Slug path: slug resolve -> spot -> history (3 calls).
    monkeypatch.setattr(cmc.requests, "get", _make_get())

    payload = cmc.fetch("Bitcoin", "chain", "30d")

    assert set(payload) == {
        "subject",
        "subject_type",
        "freshness_window",
        "endpoint",
        "fetched_at",
        "raw_response",
    }
    assert payload["subject"] == "Bitcoin"
    assert payload["subject_type"] == "chain"
    assert payload["freshness_window"] == "30d"
    assert payload["endpoint"] == (
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1"
    )
    assert set(payload["raw_response"]) == {"resolve", "quotes_latest", "quotes_historical"}
    assert payload["raw_response"]["resolve"] == _SLUG_BTC
    assert payload["raw_response"]["quotes_latest"] == _LATEST_OK
    assert payload["raw_response"]["quotes_historical"] == _HISTORICAL_OK


def test_fetch_via_symbol_fallback(monkeypatch: pytest.MonkeyPatch, _fake_key: Path) -> None:
    # Ticker subject 'USDC': slug=usdc empty -> /map?symbol=USDC -> id 3408 -> spot.
    monkeypatch.setattr(
        cmc.requests,
        "get",
        _make_get(slug=_EMPTY, slug_status=400, symbol=_MAP_SYMBOL_USDC),
    )

    payload = cmc.fetch("USDC", "stablecoin", "30d")

    assert payload["endpoint"] == (
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=3408"
    )
    assert payload["raw_response"]["resolve"] == _MAP_SYMBOL_USDC
    assert payload["raw_response"]["quotes_latest"] == _LATEST_OK


def test_fetch_history_count_maps_freshness(monkeypatch: pytest.MonkeyPatch, _fake_key: Path) -> None:
    record: list = []
    monkeypatch.setattr(cmc.requests, "get", _make_get(record=record))

    cmc.fetch("Bitcoin", "chain", "1 year")

    urls = [u for u, _ in record]
    assert any("historical?id=1&count=365" in u for u in urls)


def test_fetch_strips_key_from_envelope(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # The key-leak guard: FAKE_CMC_KEY must not appear ANYWHERE in the serialized
    # payload — it rides in the header only, never in the persisted envelope.
    monkeypatch.setattr(cmc.requests, "get", _make_get())

    payload = cmc.fetch("Bitcoin", "chain", "30d")
    serialized = json.dumps(payload)

    assert FAKE_CMC_KEY not in serialized
    assert "X-CMC_PRO_API_KEY" not in serialized


def test_fetch_sends_key_in_header(monkeypatch: pytest.MonkeyPatch, _fake_key: Path) -> None:
    # The key DOES go out on the wire (header) — it just never lands on disk or in URLs.
    record: list = []
    monkeypatch.setattr(cmc.requests, "get", _make_get(record=record))

    cmc.fetch("Bitcoin", "chain", "30d")

    assert record  # at least one call was made
    assert all(h.get("X-CMC_PRO_API_KEY") == FAKE_CMC_KEY for _, h in record)
    assert all(h.get("User-Agent") == cmc.PUBLIC_USER_AGENT for _, h in record)
    # The key must never appear in any request URL (header-only auth).
    assert all(FAKE_CMC_KEY not in u for u, _ in record)


def test_fetch_historical_401_soft_skip(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # Basic free tier excludes the historical endpoint (401) -> soft skip, fetch still
    # succeeds with quotes_historical = None.
    monkeypatch.setattr(cmc.requests, "get", _make_get(hist=None, hist_status=401))

    payload = cmc.fetch("Bitcoin", "chain", "30d")

    assert payload["raw_response"]["quotes_historical"] is None
    assert payload["raw_response"]["resolve"] == _SLUG_BTC
    assert payload["raw_response"]["quotes_latest"] == _LATEST_OK


# --- fetch: errors ----------------------------------------------------------

def test_cmc_unauthorized_no_key_echo(monkeypatch: pytest.MonkeyPatch, _fake_key: Path) -> None:
    # 401 on the first (slug resolve) call -> cmc_unauthorized; key never echoed.
    monkeypatch.setattr(cmc.requests, "get", _make_get(slug=None, slug_status=401))
    with pytest.raises(cmc.CmcFetchError, match="cmc_unauthorized") as exc:
        cmc.fetch("Bitcoin", "chain", "30d")
    assert FAKE_CMC_KEY not in str(exc.value)


def test_fetch_spot_403_unauthorized(monkeypatch: pytest.MonkeyPatch, _fake_key: Path) -> None:
    # slug resolves, but the spot quotes/latest?id call 403s -> cmc_unauthorized.
    monkeypatch.setattr(cmc.requests, "get", _make_get(latest=None, latest_status=403))
    with pytest.raises(cmc.CmcFetchError, match="cmc_unauthorized") as exc:
        cmc.fetch("Bitcoin", "chain", "30d")
    assert FAKE_CMC_KEY not in str(exc.value)


def test_fetch_429_retries_once_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    # First slug call 429s, the in-call retry succeeds; then spot + history succeed.
    slug_responses = [_FakeResponse(429), _FakeResponse(200, _SLUG_BTC)]

    def fake_get(url: str, **_: Any) -> _FakeResponse:
        if "slug=" in url:
            return slug_responses.pop(0)
        if "historical" in url:
            return _FakeResponse(200, _HISTORICAL_OK)
        return _FakeResponse(200, _LATEST_OK)

    monkeypatch.setattr(cmc.requests, "get", fake_get)

    payload = cmc.fetch("Bitcoin", "chain", "30d")

    assert payload["raw_response"]["quotes_latest"] == _LATEST_OK
    assert payload["raw_response"]["quotes_historical"] == _HISTORICAL_OK


def test_fetch_500_raises_upstream_5xx(
    monkeypatch: pytest.MonkeyPatch, _fake_key: Path
) -> None:
    monkeypatch.setattr(cmc.requests, "get", lambda *a, **k: _FakeResponse(503))
    with pytest.raises(cmc.CmcFetchError, match="upstream_5xx_cmc") as exc:
        cmc.fetch("Bitcoin", "chain", "30d")
    # The key never rides in the URL, so the 5xx message cannot leak it.
    assert FAKE_CMC_KEY not in str(exc.value)


def test_fetch_missing_key_halts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "coinmarketcap.key"
    monkeypatch.setattr(cmc, "KEY_PATH", missing)
    # No network call should be reached; the key read happens first.
    monkeypatch.setattr(
        cmc.requests,
        "get",
        lambda *a, **k: pytest.fail("network reached despite missing key"),
    )
    with pytest.raises(cmc.CmcFetchError, match="cmc_key_missing"):
        cmc.fetch("Bitcoin", "chain", "30d")


# --- write_output -----------------------------------------------------------

def test_write_output_lands_under_meta_raw_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cmc, "RAW_DIR", tmp_path / "meta" / "raw" / "coinmarketcap")
    payload = {
        "subject": "Bitcoin",
        "subject_type": "chain",
        "freshness_window": "30d",
        "endpoint": "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1",
        "fetched_at": "2026-05-25T00:00:00+00:00",
        "raw_response": {"resolve": {}, "quotes_latest": {}, "quotes_historical": None},
    }

    out = cmc.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "coinmarketcap"
    assert out.name.startswith("bitcoin_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_btc() -> None:
    # Reads the REAL key from the standard path (skipped if absent). Uses the human
    # name "Bitcoin" to exercise the slug-first path live — it must resolve to the
    # real Bitcoin (id 1), NOT the symbol="BITCOIN" meme-coin collision.
    if not cmc.KEY_PATH.exists():
        pytest.skip("no coinmarketcap key at the standard location")
    payload = cmc.fetch("Bitcoin", "chain", "30d")
    assert payload["subject_type"] == "chain"
    assert set(payload["raw_response"]) == {"resolve", "quotes_latest", "quotes_historical"}
    # slug=bitcoin is unique on /quotes/latest → the resolved coin must be real Bitcoin.
    resolved = next(iter(payload["raw_response"]["resolve"]["data"].values()))
    assert resolved["id"] == 1
    assert resolved["name"] == "Bitcoin"
    assert resolved["symbol"] == "BTC"
    assert resolved["slug"] == "bitcoin"
    assert isinstance(payload["raw_response"]["quotes_latest"], dict)
