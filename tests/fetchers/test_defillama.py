"""Unit + smoke tests for tools/fetchers/defillama_fetch.py (B.1.1).

Unit tests mock the network (no live calls). One live smoke fetch runs last and
is skipped when SKIP_LIVE=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import defillama_fetch as dl


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


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the 1 req/sec throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(dl.time, "sleep", lambda *_: None)
    monkeypatch.setattr(dl, "_last_request_at", 0.0)


# --- _slugify ---------------------------------------------------------------

def test_slugify_simple() -> None:
    assert dl._slugify("USDC") == "usdc"


def test_slugify_spaces() -> None:
    assert dl._slugify("Lido Finance") == "lido-finance"


# --- _endpoint --------------------------------------------------------------

def test_endpoint_protocol() -> None:
    assert dl._endpoint("Aave", "protocol") == "https://api.llama.fi/protocol/aave"


def test_endpoint_chain() -> None:
    assert (
        dl._endpoint("Ethereum", "chain")
        == "https://api.llama.fi/v2/historicalChainTvl/ethereum"
    )


def test_endpoint_stablecoin_is_list_lookup() -> None:
    # Stablecoins are served from the dedicated subdomain, NOT api.llama.fi.
    assert dl._endpoint("USDC", "stablecoin") == (
        "https://stablecoins.llama.fi/stablecoins?includePrices=true"
    )


def test_endpoint_unknown_type_raises() -> None:
    with pytest.raises(dl.DefiLlamaFetchError):
        dl._endpoint("USDC", "nonsense")


# --- base-host routing (regression: stablecoins live on their own subdomain) --

def test_stablecoin_endpoint_routes_to_stablecoins_host() -> None:
    assert dl._endpoint("USDC", "stablecoin").startswith(dl.BASE_STABLECOINS)
    assert "stablecoins.llama.fi" in dl._endpoint("USDC", "stablecoin")


def test_protocol_and_chain_endpoints_route_to_api_host() -> None:
    assert dl._endpoint("Aave", "protocol").startswith(dl.BASE_API)
    assert dl._endpoint("Ethereum", "chain").startswith(dl.BASE_API)
    # api host must not be the stablecoins subdomain
    assert "stablecoins.llama.fi" not in dl._endpoint("Aave", "protocol")


# --- fetch: success ---------------------------------------------------------

def test_fetch_protocol_200_returns_full_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dl.requests, "get", lambda *a, **k: _FakeResponse(200, {"tvl": 123})
    )

    payload = dl.fetch("Aave", "protocol", "30d")

    assert set(payload) == {
        "subject",
        "subject_type",
        "freshness_window",
        "endpoint",
        "fetched_at",
        "raw_response",
    }
    assert payload["subject"] == "Aave"
    assert payload["subject_type"] == "protocol"
    assert payload["freshness_window"] == "30d"
    assert payload["endpoint"] == "https://api.llama.fi/protocol/aave"
    assert payload["raw_response"] == {"tvl": 123}


def test_fetch_stablecoin_resolves_id_then_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = {"peggedAssets": [{"id": "2", "name": "USD Coin", "symbol": "USDC"}]}
    chart = [{"date": "1", "totalCirculating": {"peggedUSD": 1}}]
    calls: list[str] = []

    def fake_get(url: str, **_: Any) -> _FakeResponse:
        calls.append(url)
        # Discriminate on a path-unique token: the host is now stablecoins.llama.fi
        # for BOTH legs, so match the list endpoint by its query string instead.
        return _FakeResponse(200, listing if "includePrices" in url else chart)

    monkeypatch.setattr(dl.requests, "get", fake_get)

    payload = dl.fetch("USDC", "stablecoin", "90d")

    # Both legs of the two-step stablecoin path hit stablecoins.llama.fi.
    assert calls[0] == "https://stablecoins.llama.fi/stablecoins?includePrices=true"
    assert all("stablecoins.llama.fi" in u for u in calls)
    assert payload["endpoint"] == (
        "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=2"
    )
    assert payload["raw_response"] == chart


def test_fetch_stablecoin_unresolved_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dl.requests, "get", lambda *a, **k: _FakeResponse(200, {"peggedAssets": []})
    )
    with pytest.raises(dl.DefiLlamaFetchError, match="subject_not_found_on_defillama"):
        dl.fetch("NotAStable", "stablecoin", "30d")


# --- fetch: errors ----------------------------------------------------------

def test_fetch_404_raises_subject_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dl.requests, "get", lambda *a, **k: _FakeResponse(404))
    with pytest.raises(dl.DefiLlamaFetchError, match="subject_not_found_on_defillama"):
        dl.fetch("Nope", "protocol", "30d")


def test_fetch_500_raises_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dl.requests, "get", lambda *a, **k: _FakeResponse(503))
    with pytest.raises(dl.DefiLlamaFetchError, match="upstream_5xx_defillama"):
        dl.fetch("Aave", "protocol", "30d")


def test_fetch_429_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_FakeResponse(429), _FakeResponse(200, {"tvl": 1})]
    monkeypatch.setattr(dl.requests, "get", lambda *a, **k: responses.pop(0))

    payload = dl.fetch("Aave", "protocol", "30d")

    assert payload["raw_response"] == {"tvl": 1}
    assert responses == []  # both responses consumed


# --- write_output -----------------------------------------------------------

def test_write_output_lands_under_meta_raw_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(dl, "RAW_DIR", tmp_path / "meta" / "raw" / "defillama")
    payload = {
        "subject": "Aave",
        "subject_type": "protocol",
        "freshness_window": "30d",
        "endpoint": "https://api.llama.fi/protocol/aave",
        "fetched_at": "2026-05-23T00:00:00+00:00",
        "raw_response": {"tvl": 123},
    }

    out = dl.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "defillama"
    assert out.name.startswith("aave_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_aave_protocol() -> None:
    payload = dl.fetch("Aave", "protocol", "30d")
    assert payload["subject_type"] == "protocol"
    assert isinstance(payload["raw_response"], dict)
    # DefiLlama /protocol/<slug> always carries the protocol name.
    assert payload["raw_response"].get("name")


@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_usdc_stablecoin() -> None:
    # Regression for the api.llama.fi -> stablecoins.llama.fi host bug: this call
    # 404'd before the fix. USDC must resolve and return a non-empty supply chart.
    payload = dl.fetch("USDC", "stablecoin", "30d")
    assert payload["subject_type"] == "stablecoin"
    assert payload["endpoint"].startswith("https://stablecoins.llama.fi/stablecoincharts/all")
    chart = payload["raw_response"]
    assert isinstance(chart, list) and chart, "stablecoin chart must be a non-empty list"
    # Each entry carries a date + total circulating supply.
    assert "date" in chart[-1]
    assert "totalCirculating" in chart[-1] or "totalCirculatingUSD" in chart[-1]
