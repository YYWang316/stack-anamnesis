"""Tests for analysis_layer/fetch_front.py (B.2.11) — the IMPURE fetch front.

NO real network: the per-fetcher subprocess runner is STUBBED. These prove:
  * wiring — for subject_type="stablecoin", exactly the 6 Part-11.5 sources are
    selected and each invocation is built with the RIGHT identifier (on-chain →
    contract address, SEC → issuer + an email arg, market sources → the canonical
    subject name);
  * ★ best-effort tolerance — a fetcher that fails / raises / times out is noted
    and SKIPPED; the others still run; the call never raises;
  * no-secret-leak — the SEC email never appears in the returned notes;
  * research(fetch=False) stays the pure offline path (no fetcher invoked).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analysis_layer import fetch_front
from analysis_layer.resolvers.subject_ref import resolve_subject

SREF = resolve_subject("USDC")
CONTRACT = SREF.identifiers["eth_contract"]
ISSUER = SREF.issuer  # "Circle"
EMAIL = "operator@example.com"


def _stub(record, *, fail=(), raise_on=(), timeout_on=()):
    """A runner stub: records (name, argv) and returns (ok, reason) per config."""
    def runner(name, argv, timeout):
        record.append((name, list(argv)))
        if name in raise_on:
            raise RuntimeError("boom in runner")
        if name in timeout_on:
            return False, f"timeout after {timeout}s"
        if name in fail:
            return False, "subject_not_found_on_x"
        return True, f"wrote meta/raw/{name}/...json"
    return runner


# --------------------------------------------------------------------------- #
# wiring
# --------------------------------------------------------------------------- #
def test_stablecoin_selects_exactly_the_six_sources(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []
    notes = fetch_front.fetch_subject("USDC", runner=_stub(record))

    got = [name for name, _ in record]
    assert got == ["defillama", "coingecko", "coinmarketcap",
                   "etherscan", "alchemy", "sec_edgar"]
    assert all("ok" in n for n in notes)


def test_each_invocation_built_with_the_right_identifier(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []
    fetch_front.fetch_subject("USDC", freshness_window="30d", runner=_stub(record))
    argv = {name: a for name, a in record}

    def subj(name):  # the --subject value for a source
        a = argv[name]
        return a[a.index("--subject") + 1]

    def stype(name):
        a = argv[name]
        return a[a.index("--subject-type") + 1]

    # market sources → the CANONICAL NAME (so the written file matches the
    # orchestrator's <subject>_*.json glob; the fetchers resolve by name).
    assert subj("coingecko") == "USDC"
    assert subj("coinmarketcap") == "USDC"
    assert subj("defillama") == "USDC"
    assert stype("coingecko") == "stablecoin"

    # on-chain sources → the contract address; alchemy's token read = stablecoin_issuer
    assert subj("etherscan") == CONTRACT and "--chain-id" in argv["etherscan"]
    assert subj("alchemy") == CONTRACT
    assert stype("etherscan") == "stablecoin"
    assert stype("alchemy") == "stablecoin_issuer"

    # SEC → issuer name + the email arg + its own subject_type
    assert subj("sec_edgar") == ISSUER
    assert stype("sec_edgar") == "stablecoin_issuer"
    sec_argv = argv["sec_edgar"]
    assert "--sec-email" in sec_argv
    assert sec_argv[sec_argv.index("--sec-email") + 1] == EMAIL

    # every invocation carries the freshness window
    for a in argv.values():
        assert "--freshness-window" in a and a[a.index("--freshness-window") + 1] == "30d"


# --------------------------------------------------------------------------- #
# ★ best-effort tolerance
# --------------------------------------------------------------------------- #
def test_one_failing_fetcher_does_not_stop_the_others(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []
    notes = fetch_front.fetch_subject(
        "USDC", runner=_stub(record, fail=("coingecko",)))

    # all six still invoked
    assert [n for n, _ in record] == ["defillama", "coingecko", "coinmarketcap",
                                      "etherscan", "alchemy", "sec_edgar"]
    cg = next(n for n in notes if n.startswith("coingecko:"))
    assert "FAILED" in cg and "subject_not_found" in cg
    # the rest succeeded
    assert sum("FAILED" in n for n in notes) == 1


def test_a_runner_that_raises_is_caught_per_source(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []
    notes = fetch_front.fetch_subject(
        "USDC", runner=_stub(record, raise_on=("etherscan",)))
    # the raise was absorbed into a FAILED note; later sources still ran
    eth = next(n for n in notes if n.startswith("etherscan:"))
    assert "FAILED" in eth and "runner error" in eth
    record_names = [x for x, _ in record]
    assert "alchemy" in record_names and "sec_edgar" in record_names


def test_timeout_is_noted_not_fatal(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []
    notes = fetch_front.fetch_subject(
        "USDC", timeout=5, runner=_stub(record, timeout_on=("alchemy",)))
    al = next(n for n in notes if n.startswith("alchemy:"))
    assert "FAILED" in al and "timeout" in al


def test_missing_email_skips_only_sec(monkeypatch):
    monkeypatch.delenv(fetch_front.SEC_EMAIL_ENV, raising=False)
    record = []
    notes = fetch_front.fetch_subject("USDC", runner=_stub(record))
    # sec_edgar skipped before any subprocess; the other five still invoked
    assert "sec_edgar" not in [n for n, _ in record]
    sec = next(n for n in notes if n.startswith("sec_edgar:"))
    assert "SKIPPED" in sec and fetch_front.SEC_EMAIL_ENV in sec


# --------------------------------------------------------------------------- #
# no-secret-leak
# --------------------------------------------------------------------------- #
def test_email_never_appears_in_notes(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []

    # a hostile stub that tries to surface the email in its reason string
    def leaky_runner(name, argv, timeout):
        record.append((name, list(argv)))
        if name == "sec_edgar":
            # the email is in argv; a buggy fetcher might echo it — we must scrub
            return False, f"error contacting SEC as {argv[argv.index('--sec-email') + 1]}"
        return True, "ok"

    notes = fetch_front.fetch_subject("USDC", runner=leaky_runner)
    assert all(EMAIL not in n for n in notes), notes
    assert any("<sec-email redacted>" in n for n in notes)


def test_unresolvable_subject_raises():
    with pytest.raises(ValueError, match="not in subject_ref registry"):
        fetch_front.fetch_subject("NOT_A_SUBJECT")


def test_unknown_subject_type_skips_fetch_gracefully(monkeypatch):
    monkeypatch.setenv(fetch_front.SEC_EMAIL_ENV, EMAIL)
    record = []
    notes = fetch_front.fetch_subject(
        "USDC", subject_type="wallet", runner=_stub(record))
    assert record == []                       # nothing invoked
    assert len(notes) == 1 and "no fetcher set" in notes[0]


# --------------------------------------------------------------------------- #
# research(fetch=False) stays the pure offline path
# --------------------------------------------------------------------------- #
def test_research_fetch_false_invokes_no_fetcher(monkeypatch, tmp_path):
    # if anything tried to fetch, this would explode the test loudly.
    import analysis_layer.fetch_front as ff

    def boom(*a, **k):
        raise AssertionError("fetch_subject must NOT run when fetch=False")

    monkeypatch.setattr(ff, "fetch_subject", boom)

    from analysis_layer import orchestrate
    raw = ROOT_RAW
    if not (raw / "coingecko").exists():
        pytest.skip("no envelopes on disk")
    path = orchestrate.research("USDC", out_dir=tmp_path)  # default fetch=False
    assert path.exists()


ROOT_RAW = Path(__file__).resolve().parents[2] / "meta" / "raw"
