"""Unit + smoke tests for tools/fetchers/l2beat_fetch.py (B.1.7).

Unit tests mock the network (no live calls). One live smoke fetch runs last and
is skipped when SKIP_LIVE=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import l2beat_fetch as l2


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


# A minimal summary payload mirroring the live /api/scaling/summary shape.
_SUMMARY = {
    "chart": {"types": ["timestamp", "native"], "data": [], "syncedUntil": 1},
    "projects": {
        "arbitrum": {
            "id": "arbitrum",
            "name": "Arbitrum One",
            "slug": "arbitrum",
            "type": "layer2",
            "stage": "Stage 1",
            "risks": [],
            "tvs": {"breakdown": {"total": 15848173568}},
        },
        "optimism": {
            "id": "optimism",
            "name": "OP Mainnet",
            "slug": "optimism",
            "type": "layer2",
            "stage": "Stage 1",
            "tvs": {"breakdown": {"total": 5000000000}},
        },
        "zksync-era": {
            "id": "zksync-era",
            "name": "ZKsync Era",
            "slug": "zksync-era",
            "type": "layer2",
            "tvs": {"breakdown": {"total": 1000000000}},
        },
    },
}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the 1 req/3s throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(l2.time, "sleep", lambda *_: None)
    monkeypatch.setattr(l2, "_last_request_at", 0.0)


def _mock_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        l2.requests, "get", lambda *a, **k: _FakeResponse(200, _SUMMARY)
    )


# --- _slugify ---------------------------------------------------------------

def test_slugify_simple() -> None:
    assert l2._slugify("Arbitrum") == "arbitrum"


def test_slugify_spaces() -> None:
    assert l2._slugify("Polygon PoS") == "polygon-pos"


# --- subject_type routing ---------------------------------------------------

def test_subject_type_chain_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_summary(monkeypatch)
    payload = l2.fetch("Arbitrum", "chain", "30d")
    assert payload["subject_type"] == "chain"
    assert payload["raw_response"]["resolved_slug"] == "arbitrum"


@pytest.mark.parametrize(
    "bad_type",
    ["stablecoin_issuer", "wallet", "orchestrator", "agentic_payment_layer"],
)
def test_subject_type_non_chain_raises(bad_type: str) -> None:
    with pytest.raises(
        l2.L2BeatFetchError, match="subject_type_not_supported_by_l2beat"
    ):
        l2.fetch("Arbitrum", bad_type, "30d")


def test_subject_type_check_happens_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("network reached before subject_type validation")

    monkeypatch.setattr(l2.requests, "get", _boom)
    with pytest.raises(l2.L2BeatFetchError, match="subject_type_not_supported"):
        l2.fetch("Arbitrum", "wallet", "30d")


# --- subject resolution -----------------------------------------------------

def test_resolve_direct_slug() -> None:
    slug, proj = l2._resolve_project(_SUMMARY["projects"], "Arbitrum")
    assert slug == "arbitrum"
    assert proj["name"] == "Arbitrum One"


def test_resolve_by_display_name() -> None:
    # "OP Mainnet" is the display name; slug is "optimism".
    slug, _ = l2._resolve_project(_SUMMARY["projects"], "OP Mainnet")
    assert slug == "optimism"


def test_resolve_prefix_match_zksync() -> None:
    # "zkSync" -> "zksync" prefixes the "zksync-era" key.
    slug, _ = l2._resolve_project(_SUMMARY["projects"], "zkSync")
    assert slug == "zksync-era"


def test_resolve_unknown_raises() -> None:
    with pytest.raises(l2.L2BeatFetchError, match="l2beat_chain_not_found"):
        l2._resolve_project(_SUMMARY["projects"], "NotAnL2")


# --- fetch flow -------------------------------------------------------------

def test_fetch_full_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_summary(monkeypatch)
    payload = l2.fetch("Arbitrum", "chain", "30d")

    assert set(payload) == {
        "subject",
        "subject_type",
        "freshness_window",
        "endpoint",
        "fetched_at",
        "raw_response",
    }
    assert payload["subject"] == "Arbitrum"
    assert payload["freshness_window"] == "30d"
    assert payload["raw_response"]["summary"]["tvs"]["breakdown"]["total"] == 15848173568


def test_fetch_endpoint_field_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_summary(monkeypatch)
    payload = l2.fetch("Arbitrum", "chain", "30d")
    assert payload["endpoint"] == "https://l2beat.com/api/scaling/summary"


def test_fetch_unresolved_chain_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_summary(monkeypatch)
    with pytest.raises(l2.L2BeatFetchError, match="l2beat_chain_not_found"):
        l2.fetch("Solana", "chain", "30d")


# --- fetch: HTTP errors -----------------------------------------------------

def test_404_chain_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(l2.requests, "get", lambda *a, **k: _FakeResponse(404))
    with pytest.raises(l2.L2BeatFetchError, match="l2beat_chain_not_found"):
        l2.fetch("Arbitrum", "chain", "30d")


def test_5xx_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(l2.requests, "get", lambda *a, **k: _FakeResponse(503))
    with pytest.raises(l2.L2BeatFetchError, match="upstream_5xx_l2beat"):
        l2.fetch("Arbitrum", "chain", "30d")


def test_429_retry_once(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_FakeResponse(429), _FakeResponse(200, _SUMMARY)]
    monkeypatch.setattr(l2.requests, "get", lambda *a, **k: responses.pop(0))

    payload = l2.fetch("Arbitrum", "chain", "30d")

    assert payload["raw_response"]["resolved_slug"] == "arbitrum"
    assert responses == []  # both responses consumed


# --- write_output -----------------------------------------------------------

def test_write_output_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(l2, "RAW_DIR", tmp_path / "meta" / "raw" / "l2beat")
    payload = {
        "subject": "Arbitrum",
        "subject_type": "chain",
        "freshness_window": "30d",
        "endpoint": "https://l2beat.com/api/scaling/summary",
        "fetched_at": "2026-05-25T00:00:00+00:00",
        "raw_response": {"summary": {"name": "Arbitrum One"}, "resolved_slug": "arbitrum"},
    }

    out = l2.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "l2beat"
    assert out.name.startswith("arbitrum_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_arbitrum_chain() -> None:
    payload = l2.fetch("Arbitrum", "chain", "30d")
    assert payload["subject_type"] == "chain"
    project = payload["raw_response"]["summary"]
    assert isinstance(project, dict)
    # Arbitrum's TVS is a multi-billion-dollar number — proves real data flowed.
    total = project["tvs"]["breakdown"]["total"]
    assert total > 1_000_000_000
