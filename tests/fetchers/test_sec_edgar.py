"""Unit + smoke tests for tools/fetchers/sec_edgar_fetch.py (B.1.4).

Unit tests mock the network and never use the user's real email. The two
security-critical concerns get dedicated coverage:
  - the two-UA invariant (the I-003 defense — UA selected BY HOST), and
  - the email-PII guard (the email never serializes into the envelope, never echoes
    in an error).
One live smoke fetch runs last; it reads the real email ONLY from
$SEC_EDGAR_TEST_EMAIL and is skipped when SKIP_LIVE=1 or the env var is unset.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.fetchers import sec_edgar_fetch as se

# Fake PII used in every unit test. NEVER the user's real email.
FAKE_EMAIL = "testpii@example.com"
CIRCLE_CIK = "0001876042"


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
_SUBMISSIONS_OK = {"cik": CIRCLE_CIK, "name": "Circle", "filings": {"recent": {}}}
_COMPANYFACTS_OK = {"cik": CIRCLE_CIK, "facts": {"us-gaap": {}}}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the throttle and 429 backoff in unit tests."""
    monkeypatch.setattr(se.time, "sleep", lambda *_: None)
    monkeypatch.setattr(se, "_last_request_at", 0.0)


# --- _slugify ---------------------------------------------------------------

def test_slugify_spaces() -> None:
    assert se._slugify("Coinbase Global") == "coinbase-global"


# --- _resolve_cik -----------------------------------------------------------

def test_resolve_cik_known() -> None:
    assert se._resolve_cik("Circle") == CIRCLE_CIK


def test_resolve_cik_known_case_insensitive() -> None:
    assert se._resolve_cik("COINBASE GLOBAL") == "0001679788"


def test_resolve_cik_10digit_passthrough() -> None:
    assert se._resolve_cik("0001679788") == "0001679788"


def test_resolve_cik_short_numeric_zero_pads() -> None:
    # An unpadded CIK is zero-padded to 10 digits (registry §6 quirk).
    assert se._resolve_cik("1876042") == "0001876042"


def test_resolve_cik_unknown_raises() -> None:
    with pytest.raises(se.EdgarFetchError, match="cik_resolution_failed"):
        se._resolve_cik("Random Inc")


# --- _validate_email --------------------------------------------------------

def test_validate_email_ok() -> None:
    se._validate_email("a@b.co")  # no raise


def test_validate_email_invalid_no_echo() -> None:
    with pytest.raises(se.EdgarFetchError) as exc:
        se._validate_email("not-an-email")
    msg = str(exc.value)
    assert "sec_email_invalid" in msg
    # The rejected value must NOT be echoed back.
    assert "not-an-email" not in msg


def test_validate_email_no_dot_after_at() -> None:
    with pytest.raises(se.EdgarFetchError, match="sec_email_invalid"):
        se._validate_email("user@localhost")


def test_validate_email_declined_token() -> None:
    # "declined" is the canonical Gate-2 decline; defense in depth here.
    with pytest.raises(se.EdgarFetchError, match="sec_email_invalid"):
        se._validate_email("declined")


def test_validate_email_empty() -> None:
    with pytest.raises(se.EdgarFetchError, match="sec_email_invalid"):
        se._validate_email("")


# --- _select_user_agent (THE I-003 DEFENSE) ---------------------------------

def test_select_ua_sec_gov_returns_sec_ua() -> None:
    ua = se._select_user_agent("https://data.sec.gov/submissions/CIK0002000010.json", FAKE_EMAIL)
    assert ua == f"StackAnamnesis/1.0 ({FAKE_EMAIL})"
    assert FAKE_EMAIL in ua


def test_select_ua_subdomain_sec_gov() -> None:
    ua = se._select_user_agent("https://www.sec.gov/cgi-bin/browse-edgar", FAKE_EMAIL)
    assert ua == f"StackAnamnesis/1.0 ({FAKE_EMAIL})"


def test_select_ua_exact_sec_gov() -> None:
    ua = se._select_user_agent("https://sec.gov/foo", FAKE_EMAIL)
    assert FAKE_EMAIL in ua


def test_select_ua_non_sec_returns_public() -> None:
    ua = se._select_user_agent("https://api.llama.fi/protocol/aave", FAKE_EMAIL)
    assert ua == se.PUBLIC_USER_AGENT
    assert FAKE_EMAIL not in ua


def test_select_ua_intuit_returns_public() -> None:
    # The literal I-003 case: the host that triggered the original email leak.
    ua = se._select_user_agent("https://investors.intuit.com/financials", FAKE_EMAIL)
    assert ua == se.PUBLIC_USER_AGENT
    assert FAKE_EMAIL not in ua


def test_select_ua_sec_gov_lookalike_returns_public() -> None:
    # sec.gov.evil.com must NOT match the suffix naively.
    ua = se._select_user_agent("https://sec.gov.evil.com/leak", FAKE_EMAIL)
    assert ua == se.PUBLIC_USER_AGENT
    assert FAKE_EMAIL not in ua


# --- fetch: success ---------------------------------------------------------

def test_fetch_200_returns_full_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        se.requests,
        "get",
        _seq_get([_FakeResponse(200, _SUBMISSIONS_OK), _FakeResponse(200, _COMPANYFACTS_OK)]),
    )

    payload = se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)

    assert set(payload) == {
        "subject",
        "subject_type",
        "freshness_window",
        "endpoint",
        "fetched_at",
        "raw_response",
    }
    assert payload["subject"] == "Circle"
    assert payload["subject_type"] == "stablecoin_issuer"
    assert payload["endpoint"] == "https://data.sec.gov"
    assert set(payload["raw_response"]) == {"submissions", "companyfacts"}
    assert payload["raw_response"]["submissions"] == _SUBMISSIONS_OK
    assert payload["raw_response"]["companyfacts"] == _COMPANYFACTS_OK


def test_fetch_uses_sec_ua_on_both_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both endpoints are *.sec.gov, so both outbound requests must carry the SEC UA.
    headers_seen: list[str] = []

    def fake_get(url: str, headers: dict[str, str], **_: Any) -> _FakeResponse:
        headers_seen.append(headers["User-Agent"])
        return _FakeResponse(200, _SUBMISSIONS_OK)

    monkeypatch.setattr(se.requests, "get", fake_get)

    se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)

    assert headers_seen and all(FAKE_EMAIL in ua for ua in headers_seen)


def test_fetch_email_never_in_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    # The PII guard: the email must NOT appear anywhere in the serialized envelope,
    # even though both outbound headers carry it.
    monkeypatch.setattr(
        se.requests,
        "get",
        _seq_get([_FakeResponse(200, _SUBMISSIONS_OK), _FakeResponse(200, _COMPANYFACTS_OK)]),
    )

    payload = se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)
    serialized = json.dumps(payload)

    assert FAKE_EMAIL not in serialized
    assert "testpii" not in serialized
    assert payload["endpoint"] == "https://data.sec.gov"


def test_fetch_companyfacts_404_soft_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        se.requests,
        "get",
        _seq_get([_FakeResponse(200, _SUBMISSIONS_OK), _FakeResponse(404)]),
    )

    payload = se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)

    assert payload["raw_response"]["companyfacts"] is None
    assert payload["raw_response"]["submissions"] == _SUBMISSIONS_OK


def test_fetch_submissions_404_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(se.requests, "get", lambda *a, **k: _FakeResponse(404))
    with pytest.raises(se.EdgarFetchError, match="subject_not_found_on_sec_edgar"):
        se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)


def test_fetch_403_rate_limited_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_get(*_a: Any, **_k: Any) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(403)

    monkeypatch.setattr(se.requests, "get", fake_get)
    with pytest.raises(se.EdgarFetchError, match="rate_limited_by_sec") as exc:
        se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)
    # No auto-retry: exactly one request was made.
    assert calls["n"] == 1
    # The email must not surface in the error (URL carries no email anyway).
    assert FAKE_EMAIL not in str(exc.value)


def test_fetch_429_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        se.requests,
        "get",
        _seq_get(
            [
                _FakeResponse(429),
                _FakeResponse(200, _SUBMISSIONS_OK),
                _FakeResponse(200, _COMPANYFACTS_OK),
            ]
        ),
    )

    payload = se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)

    assert payload["raw_response"]["submissions"] == _SUBMISSIONS_OK


def test_fetch_500_raises_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(se.requests, "get", lambda *a, **k: _FakeResponse(503))
    with pytest.raises(se.EdgarFetchError, match="upstream_5xx_sec") as exc:
        se.fetch("Circle", "stablecoin_issuer", "30d", FAKE_EMAIL)
    assert FAKE_EMAIL not in str(exc.value)


def test_fetch_invalid_email_halts_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        se.requests,
        "get",
        lambda *a, **k: pytest.fail("network reached despite invalid email"),
    )
    with pytest.raises(se.EdgarFetchError, match="sec_email_invalid"):
        se.fetch("Circle", "stablecoin_issuer", "30d", "bogus")


# --- _load_email_from_run_dir + main (dual-mode input) ----------------------

def _write_gates(run_dir: Path, sec_email_entry: dict[str, Any]) -> None:
    meta = run_dir / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "gates.json").write_text(
        json.dumps({"gates": {"sec_email": sec_email_entry}}), encoding="utf-8"
    )


def test_load_email_from_run_dir_ok(tmp_path: Path) -> None:
    _write_gates(tmp_path, {"value": FAKE_EMAIL, "applies": True})
    assert se._load_email_from_run_dir(tmp_path) == FAKE_EMAIL


def test_load_email_gates_missing(tmp_path: Path) -> None:
    with pytest.raises(se.EdgarFetchError, match="gates_file_unreadable"):
        se._load_email_from_run_dir(tmp_path)


def test_load_email_gates_malformed_json(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir(parents=True)
    (meta / "gates.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(se.EdgarFetchError, match="gates_file_unreadable"):
        se._load_email_from_run_dir(tmp_path)


def test_load_email_gates_applies_false(tmp_path: Path) -> None:
    _write_gates(tmp_path, {"value": "email_provided", "applies": False})
    with pytest.raises(se.EdgarFetchError, match="sec_email_gate_skipped"):
        se._load_email_from_run_dir(tmp_path)


def test_load_email_gates_declined(tmp_path: Path) -> None:
    _write_gates(tmp_path, {"value": "declined", "applies": True})
    with pytest.raises(se.EdgarFetchError, match="sec_email_declined_by_user"):
        se._load_email_from_run_dir(tmp_path)


def test_main_sec_email_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_fetch(subject, subject_type, freshness_window, sec_email):
        captured.update(
            subject=subject, sec_email=sec_email, subject_type=subject_type
        )
        return {"subject": subject}

    monkeypatch.setattr(se, "fetch", fake_fetch)
    monkeypatch.setattr(se, "write_output", lambda p: tmp_path / "out.json")

    rc = se.main(
        [
            "--subject", "Circle",
            "--subject-type", "stablecoin_issuer",
            "--freshness-window", "30d",
            "--sec-email", FAKE_EMAIL,
        ]
    )
    assert rc == 0
    assert captured["sec_email"] == FAKE_EMAIL
    assert captured["subject"] == "Circle"


def test_main_run_dir_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_gates(tmp_path, {"value": FAKE_EMAIL, "applies": True})
    captured: dict[str, Any] = {}

    def fake_fetch(subject, subject_type, freshness_window, sec_email):
        captured["sec_email"] = sec_email
        return {"subject": subject}

    monkeypatch.setattr(se, "fetch", fake_fetch)
    monkeypatch.setattr(se, "write_output", lambda p: tmp_path / "out.json")

    rc = se.main(
        [
            "--subject", "Circle",
            "--subject-type", "stablecoin_issuer",
            "--freshness-window", "30d",
            "--run-dir", str(tmp_path),
        ]
    )
    assert rc == 0
    assert captured["sec_email"] == FAKE_EMAIL


def test_main_both_modes_conflict() -> None:
    # argparse mutually-exclusive group rejects both modes together.
    with pytest.raises(SystemExit):
        se.main(
            [
                "--subject", "Circle",
                "--subject-type", "stablecoin_issuer",
                "--freshness-window", "30d",
                "--sec-email", FAKE_EMAIL,
                "--run-dir", "/tmp/whatever",
            ]
        )


def test_main_neither_mode() -> None:
    # argparse requires exactly one of the two.
    with pytest.raises(SystemExit):
        se.main(
            [
                "--subject", "Circle",
                "--subject-type", "stablecoin_issuer",
                "--freshness-window", "30d",
            ]
        )


# --- write_output -----------------------------------------------------------

def test_write_output_lands_under_meta_raw_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(se, "RAW_DIR", tmp_path / "meta" / "raw" / "sec_edgar")
    payload = {
        "subject": "Circle",
        "subject_type": "stablecoin_issuer",
        "freshness_window": "30d",
        "endpoint": "https://data.sec.gov",
        "fetched_at": "2026-05-25T00:00:00+00:00",
        "raw_response": {"submissions": {}, "companyfacts": None},
    }

    out = se.write_output(payload)

    assert out.parent == tmp_path / "meta" / "raw" / "sec_edgar"
    assert out.name.startswith(f"circle_cik{CIRCLE_CIK}_") and out.suffix == ".json"
    assert json.loads(out.read_text(encoding="utf-8")) == payload


# --- live smoke -------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="SKIP_LIVE=1 set")
def test_live_smoke_circle() -> None:
    # Reads the REAL email ONLY from $SEC_EDGAR_TEST_EMAIL (skipped if unset).
    email = os.environ.get("SEC_EDGAR_TEST_EMAIL")
    if not email:
        pytest.skip("SEC_EDGAR_TEST_EMAIL unset")
    assert "@" in email, "SEC_EDGAR_TEST_EMAIL must be a real email"
    payload = se.fetch("Circle", "stablecoin_issuer", "30d", email)
    assert payload["subject"] == "Circle"
    assert payload["endpoint"] == "https://data.sec.gov"
    assert set(payload["raw_response"]) == {"submissions", "companyfacts"}
    subs = payload["raw_response"]["submissions"]
    assert isinstance(subs, dict) and str(subs.get("cik", "")).lstrip("0") == "1876042"
    # The real email must not have leaked into the envelope.
    assert email not in json.dumps(payload)
