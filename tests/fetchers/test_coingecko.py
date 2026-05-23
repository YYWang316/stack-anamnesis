"""Unit + smoke tests for tools/fetchers/coingecko_fetch.py (B.1.2).

Unit tests mock the network (no live calls). One live smoke fetch runs last and
is skipped when SKIP_LIVE=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import coingecko_fetch as cg


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(
                f"raise_for_status reached for {self.status_code} — "
                "status should have been handled before this"
            )


# A /search response with bitcoin ranked first.
_SEARCH_BTC = {"coins": [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}]}


def _seq_get(responses: list[_FakeResponse]):
    """Return a fake requests.get that yields the given responses in order."""

    def fake_get(*_a: Any, **_k: Any) -> _FakeResponse:
        return responses.pop(0)

    return fake_get


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the 1 req/2.5 sec throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(cg.time, "sleep", lambda *_: None)
    monkeypatch.setattr(cg, "_last_request_at", 0.0)


# --- _slugify ---------------------------------------------------------------

def test_slugify_simple() -> None:
    assert cg._slugify("USDC") == "usdc"


def test_slugify_spaces() -> None:
    assert cg._slugify("USD Coin") == "usd-coin"


# --- _days_from_freshness ---------------------------------------------------

def test_days_from_freshness_numeric_windows() -> None:
    assert cg._days_from_freshness("7d") == 7
    assert cg._days_from_freshness("30d") == 30
    assert cg._days_from_freshness("90d") == 90


def test_days_from_freshness_aliases() -> None:
    assert cg._days_from_freshness("quarter") == 90
    assert cg._days_from_freshness("1 year") == 365
    assert cg._days_from_freshness("since_TGE") == "max"


def test_days_from_freshness_unknown_raises() -> None:
    with pytest.raises(cg.CoinGeckoFetchError):
        cg._days_from_freshness("forever")


# --- _resolve_coin_id -------------------------------------------------------

def test_resolve_coin_id_exact_symbol_match(monkeypatch: pytest.MonkeyPatch) -> None:
    search = {
        "coins": [
            {"id": "wrapped-bitcoin", "symbol": "wbtc", "name": "Wrapped Bitcoin", "market_cap_rank": 15},
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap_rank": 1},
        ]
    }
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: _FakeResponse(200, search))

    coin_id, raw = cg._resolve_coin_id("BTC", {"User-Agent": "x"})

    assert coin_id == "bitcoin"  # only btc matches the symbol
    assert raw == search


def test_resolve_coin_id_name_match_beats_symbol_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: a meme coin's ticker is literally "BITCOIN" (registry §4 quirk).
    # Subject "Bitcoin" must resolve to the rank-1 real coin via name match, not
    # the low-cap collision via symbol match.
    search = {
        "coins": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap_rank": 1},
            {"id": "harrypotterobamasonic10in", "symbol": "BITCOIN", "name": "HarryPotter…", "market_cap_rank": 900},
        ]
    }
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: _FakeResponse(200, search))

    coin_id, _ = cg._resolve_coin_id("Bitcoin", {"User-Agent": "x"})

    assert coin_id == "bitcoin"


def test_resolve_coin_id_falls_back_to_best_rank(monkeypatch: pytest.MonkeyPatch) -> None:
    # Subject matches no symbol or name; fall back to the best-ranked candidate.
    search = {
        "coins": [
            {"id": "lowcap", "symbol": "lc", "name": "Low Cap", "market_cap_rank": 800},
            {"id": "topcap", "symbol": "tc", "name": "Top Cap", "market_cap_rank": 3},
        ]
    }
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: _FakeResponse(200, search))

    coin_id, _ = cg._resolve_coin_id("SomethingElse", {"User-Agent": "x"})

    assert coin_id == "topcap"


def test_resolve_coin_id_empty_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: _FakeResponse(200, {"coins": []}))
    with pytest.raises(cg.CoinGeckoFetchError, match="subject_not_found_on_coingecko"):
        cg._resolve_coin_id("NotACoin", {"User-Agent": "x"})


# --- fetch: success ---------------------------------------------------------

def test_fetch_200_returns_full_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    spot = {"id": "bitcoin", "name": "Bitcoin", "market_data": {}}
    history = {"prices": [[1, 2]], "market_caps": [], "total_volumes": []}
    monkeypatch.setattr(
        cg.requests,
        "get",
        _seq_get([_FakeResponse(200, _SEARCH_BTC), _FakeResponse(200, spot), _FakeResponse(200, history)]),
    )

    payload = cg.fetch("Bitcoin", "chain", "30d")

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
    assert payload["endpoint"] == "https://api.coingecko.com/api/v3/coins/bitcoin"
    assert set(payload["raw_response"]) == {"search", "spot", "history"}
    assert payload["raw_response"]["search"] == _SEARCH_BTC
    assert payload["raw_response"]["spot"] == spot
    assert payload["raw_response"]["history"] == history


def test_fetch_history_url_maps_freshness_to_days(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    def fake_get(url: str, **_: Any) -> _FakeResponse:
        urls.append(url)
        if "search" in url:
            return _FakeResponse(200, _SEARCH_BTC)
        if "market_chart" in url:
            return _FakeResponse(200, {"prices": []})
        return _FakeResponse(200, {"id": "bitcoin"})

    monkeypatch.setattr(cg.requests, "get", fake_get)

    cg.fetch("Bitcoin", "chain", "1 year")

    assert any("market_chart?vs_currency=usd&days=365" in u for u in urls)


# --- fetch: errors ----------------------------------------------------------

def test_fetch_search_empty_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: _FakeResponse(200, {"coins": []}))
    with pytest.raises(cg.CoinGeckoFetchError, match="subject_not_found_on_coingecko"):
        cg.fetch("Nope", "chain", "30d")


def test_fetch_coin_id_404_raises_coin_id_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    # /search resolves, but /coins/<id> 404s.
    monkeypatch.setattr(
        cg.requests,
        "get",
        _seq_get([_FakeResponse(200, _SEARCH_BTC), _FakeResponse(404)]),
    )
    with pytest.raises(cg.CoinGeckoFetchError, match="coin_id_invalid"):
        cg.fetch("Bitcoin", "chain", "30d")


def test_fetch_500_raises_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cg.requests,
        "get",
        _seq_get([_FakeResponse(200, _SEARCH_BTC), _FakeResponse(503)]),
    )
    with pytest.raises(cg.CoinGeckoFetchError, match="upstream_5xx_coingecko"):
        cg.fetch("Bitcoin", "chain", "30d")


def test_fetch_429_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    # First /search call 429s, retry succeeds; then spot + history succeed.
    spot = {"id": "bitcoin", "name": "Bitcoin"}
    history = {"prices": []}
    monkeypatch.setattr(
        cg.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(429),
                _FakeResponse(200, _SEARCH_BTC),
                _FakeResponse(200, spot),
                _FakeResponse(200, history),
            ]
        ),
    )

    payload = cg.fetch("Bitcoin", "chain", "30d")

    assert payload["raw_response"]["spot"] == spot
    assert payload["raw_response"]["history"] == history


# --- write_output -----------------------------------------------------------

def test_write_output_lands_under_meta_raw_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cg, "RAW_DIR", tmp_path / "meta" / "raw" / "coingecko")
    payload = {
        "subject": "Bitcoin",
        "subject_type": "chain",
        "freshness_window": "30d",
        "endpoint": "https://api.coingecko.com/api/v3/coins/bitcoin",
        "fetched_at": "2026-05-23T00:00:00+00:00",
        "raw_response": {"search": {}, "spot": {}, "history": {}},
    }

    out = cg.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "coingecko"
    assert out.name.startswith("bitcoin_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_bitcoin() -> None:
    payload = cg.fetch("Bitcoin", "chain", "30d")
    assert payload["subject_type"] == "chain"
    assert set(payload["raw_response"]) == {"search", "spot", "history"}
    # /coins/<id> always carries the coin id; resolve should land on bitcoin.
    assert payload["raw_response"]["spot"].get("id") == "bitcoin"
