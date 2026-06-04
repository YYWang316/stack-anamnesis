"""Tests for analysis_layer/bundle.py (B.2.12, TD-041) — the FACTS BUNDLE (①).

The bundle packs the orchestrator's DETERMINISTIC reconciled facts into one
clean, self-contained, prose-free "facts folder" for a downstream LLM
report-writer. These tests prove, off the REAL on-disk USDC envelopes:

  * the bundle carries reconciled spot metrics WITH provenance (source + as_of),
    the supply-momentum windows, the issuer's SEC financials, and the source list;
  * it carries NO analysis / prose / verdict / ``[MANUAL]`` text — facts only;
  * it is deterministic — built twice, byte-identical;
  * e2e: ``research("USDC", bundle=True)`` writes a valid ``.facts.json`` next to
    the canonical ``.md``.

All PURE — no network; glob+skip when the envelopes are absent.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_layer import orchestrate
from analysis_layer.bundle import build_facts_bundle, serialize_bundle

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "meta" / "raw"
TEMPLATE_V14 = ROOT / "references" / "templates" / "crypto_research_v1.3.md"

# Keys that would mean the bundle leaked ANALYSIS or PROSE — it must carry none.
_FORBIDDEN_KEYS = {
    "markdown", "report", "prose", "narrative", "thesis", "analysis",
    "verdict", "confirmation", "divergence", "commentary", "note", "notes",
    "manual", "conclusion", "position", "recommendation",
}


def _have_usdc_envelopes() -> bool:
    """True when at least the on-chain + aggregator envelopes USDC needs exist."""
    return any((RAW / s).exists() and any((RAW / s).glob("*.json"))
               for s in ("coingecko", "etherscan", "alchemy"))


def _build_usdc_bundle():
    """Build the USDC facts bundle from the REAL on-disk envelopes (the same
    reconciled + supply_change the orchestrator feeds the report)."""
    _md, sref, sources_loaded, reconciled, supply_change, _notes = (
        orchestrate.build_report("USDC", raw_dir=RAW)
    )
    return build_facts_bundle(
        sref, reconciled, supply_change, sources_loaded=sources_loaded
    ), sref


def _all_keys(obj):
    """Every dict key appearing anywhere in a nested JSON structure (lowercased)."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k).lower())
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_bundle_carries_reconciled_metrics_with_provenance():
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    bundle, sref = _build_usdc_bundle()

    # subject identity + key identifiers
    assert bundle["subject"] == "USDC"
    assert bundle["subject_type"] == "stablecoin"
    assert bundle["issuer"] == "Circle"
    assert bundle["decimals"] == 6
    assert bundle["contract"] == sref.identifiers["eth_contract"]

    # reconciled spot metrics: every one carries provenance (source + as_of)
    assert bundle["metrics"], "expected reconciled spot metrics"
    metric_names = {m["metric"] for m in bundle["metrics"]}
    assert {"price", "total_supply"} & metric_names
    for m in bundle["metrics"]:
        assert m["source"] and m["as_of"]              # provenance present
        assert "value" in m and m["unit"]
        assert m["confidence"] in {"High", "Medium", "Low", "Unknown"}
        assert m["agreement"]                          # confidence signal kept


def test_bundle_carries_supply_momentum_with_windows():
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    bundle, _ = _build_usdc_bundle()

    momentum = bundle["supply_momentum"]
    assert momentum, "expected supply-momentum windows"
    windows = {w["window"] for w in momentum}
    assert windows & {"7d", "30d", "90d"}
    # ascending by window length, each with the actual-day honesty + provenance
    assert [w["window_days"] for w in momentum] == sorted(
        w["window_days"] for w in momentum
    )
    for w in momentum:
        assert w["source"] == "defillama" and w["as_of"]
        assert w["actual_days"] is not None
        assert w["direction"] in {"up", "down", "flat"}


def test_bundle_carries_issuer_financials_with_provenance():
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    bundle, _ = _build_usdc_bundle()

    fin = bundle["issuer_financials"]
    if fin is None:
        pytest.skip("no SEC envelope on disk for the issuer")
    assert fin["issuer"] == "Circle"
    assert fin["fiscal_year"]
    # the snake_case financial facts, each with its own provenance
    for key in ("revenues", "net_income", "assets", "liabilities", "equity"):
        assert key in fin, key
        assert fin[key]["source"] == "sec_edgar" and fin[key]["as_of"]
        assert "value" in fin[key] and fin[key]["unit"] == "USD"


def test_bundle_lists_sources():
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    bundle, _ = _build_usdc_bundle()
    assert bundle["sources"] == sorted(bundle["sources"])  # deterministic order
    assert {"coingecko", "etherscan"} & set(bundle["sources"])


def test_bundle_contains_no_analysis_or_prose():
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    bundle, _ = _build_usdc_bundle()

    # no analysis/prose KEYS anywhere in the structure
    leaked = _all_keys(bundle) & _FORBIDDEN_KEYS
    assert not leaked, f"bundle leaked analysis/prose keys: {leaked}"

    # and no leftover template placeholder TEXT in any string value
    blob = serialize_bundle(bundle)
    assert "[MANUAL" not in blob
    assert "UNFILLED" not in blob and "NEEDS HUMAN REVIEW" not in blob


def test_bundle_is_deterministic():
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    b1, _ = _build_usdc_bundle()
    b2, _ = _build_usdc_bundle()
    assert b1 == b2
    # byte-identical serialisation (same input -> same bytes)
    assert serialize_bundle(b1) == serialize_bundle(b2)


def test_research_bundle_e2e_writes_valid_facts_json(tmp_path):
    """e2e: research("USDC", bundle=True) writes a valid .facts.json beside the .md."""
    if not TEMPLATE_V14.exists():
        pytest.skip("v1.4 template absent")
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")

    md_path = orchestrate.research("USDC", out_dir=tmp_path, bundle=True)
    bundle_path = md_path.with_suffix(".facts.json")
    assert bundle_path.exists(), "facts bundle written next to the .md"

    loaded = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert loaded["subject"] == "USDC"
    assert loaded["metrics"] and loaded["sources"]
    # the .md is the canonical artifact and is also present
    assert md_path.exists() and md_path.suffix == ".md"


def test_research_without_bundle_writes_no_facts_json(tmp_path):
    """Default is OFF — the .md is the canonical artifact, no bundle written."""
    if not TEMPLATE_V14.exists():
        pytest.skip("v1.4 template absent")
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    md_path = orchestrate.research("USDC", out_dir=tmp_path)
    assert not md_path.with_suffix(".facts.json").exists()
