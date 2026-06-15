"""Tests for analysis_layer/orchestrate.py (B.2.10) — the pipeline FRONT DOOR.

The orchestrator centralises the wiring the filler/change tests duplicated
(resolve → load newest envelope per source → extract → reconcile → derive →
fill → write) behind ``research()``. These tests prove:

  * ★ a real e2e ``research("USDC")`` produces the SAME clean stablecoin report
    the filler e2e proves (chain modules omitted, Part 5.5 kept, supply [AUTO]
    filled, 5.5 A net-change [SEMI-AUTO ✓ COMPUTED], Evidence Table present) AND
    now ALSO carries the sec_edgar-sourced Circle financials;
  * the source→extractor map names all SIX sources (drop-guard);
  * an unresolvable subject raises a clear error;
  * determinism — two runs on the same envelopes produce byte-identical CONTENT.

All PURE — no network, reads only the on-disk envelopes. glob+skip when absent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analysis_layer import orchestrate

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "meta" / "raw"
TEMPLATE_V14 = ROOT / "references" / "templates" / "crypto_research_v1.3.md"
TEMPLATE_V2 = ROOT / "references" / "templates" / "crypto_research_v2.md"
TEMPLATE_V3 = ROOT / "references" / "templates" / "crypto_research_v3.md"


def _have_usdc_envelopes() -> bool:
    """True when at least the on-chain + aggregator envelopes USDC needs exist."""
    return any((RAW / s).exists() and any((RAW / s).glob("*.json"))
               for s in ("coingecko", "etherscan", "alchemy"))


def test_source_extractor_map_names_all_six_sources():
    # guards against silently dropping a source from the pipeline.
    assert set(orchestrate.SOURCE_EXTRACTORS) == {
        "alchemy", "etherscan", "coingecko", "coinmarketcap", "defillama",
        "sec_edgar",
    }
    # every value is callable (an adapter to the uniform shape)
    assert all(callable(fn) for fn in orchestrate.SOURCE_EXTRACTORS.values())


def test_unresolvable_subject_raises_clear_error(tmp_path):
    with pytest.raises(ValueError, match="not in subject_ref registry"):
        orchestrate.research("NOT_A_REAL_SUBJECT", out_dir=tmp_path)


def test_real_usdc_end_to_end(tmp_path, capsys):
    """★ the LEGACY v2 pipeline e2e — pinned to the v2 template (still supported via
    --template). research(template=v2) → the clean stablecoin report + Circle SEC
    facts. (The live default is now v3; its scaffold is covered by
    test_real_usdc_v3_default_scaffold below.)"""
    if not TEMPLATE_V2.exists():
        pytest.skip("v2 template absent")
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")

    path = orchestrate.research("USDC", out_dir=tmp_path, template_path=TEMPLATE_V2)
    assert path.exists() and path.parent == tmp_path
    md = path.read_text(encoding="utf-8")

    # ---- SAME clean stablecoin report the filler e2e proves ---------------- #
    # chain / payment / DeFi modules + the Mode-B News Hook are GONE
    assert "通用指标" not in md            # 5.1 generic chain metrics
    assert "Utilization rate" not in md    # 5.4 DeFi-protocol metric
    assert "News Hook" not in md           # Part 2 (Mode B only)
    # the Stablecoin module + the subject-agnostic sections KEPT
    assert "Stablecoin module" in md       # 5.5
    assert "Reserve & Backing" in md       # 5.5 D
    assert "Path C" in md                  # stablecoin valuation path
    # supply [AUTO] filled, 5.5 A net-change computed, faithfulness flags intact
    assert "[AUTO ✓ FILLED" in md
    assert "[SEMI-AUTO ✓ COMPUTED" in md
    assert "UNFILLED [AUTO]" in md
    assert "NEEDS HUMAN REVIEW [SEMI-AUTO]" in md
    assert "**MANUAL** — researcher must fill" in md
    assert "Auto Evidence Table" in md
    assert "[AUTO subject_ref]" in md and "Circle" in md

    # ---- NOW ALSO: sec_edgar Circle financials in the Evidence Table ------- #
    # (the orchestrator wires sec_edgar, which the filler e2e omitted)
    table = md.split("Auto Evidence Table", 1)[1]
    assert "sec_edgar" in table
    assert "Revenues" in table and "Assets" in table

    # ---- TD-037: the Circle facts are the latest CONSISTENT fiscal year ----- #
    # (data-driven selection, not a mixed/stale set). Ground truth = the
    # 2026-05-27 manual draft off the SAME envelope: FY2025, 2025-12-31.
    sec_rows = [r for r in table.splitlines() if "sec_edgar" in r]
    assert len(sec_rows) == 5
    # every SEC fact dated to the same latest fiscal-year end — no mixed years
    assert all("2025-12-31" in r for r in sec_rows), sec_rows
    # the swing-to-loss is now visible, and the right-year flows/stocks land
    assert "-69508000" in table      # NetIncomeLoss FY2025 = LOSS (was +155.7M FY2024)
    assert "2746642000" in table     # Revenues FY2025 $2.747B (was $1.676B FY2024)
    assert "3329327000" in table     # StockholdersEquity FY2025 $3.329B (was $570.5M)
    assert "78713207000" in table    # Assets $78.71B (already correct)
    assert "75382434000" in table    # Liabilities $75.38B (already correct)
    # the stale FY2024 values must be GONE
    assert "155667000" not in table and "1676253000" not in table
    assert "570529000" not in table

    with capsys.disabled():
        print(f"\n=== orchestrate e2e: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} ===")
        print("clean stablecoin report + sec_edgar Circle facts present")


def test_real_usdc_v3_default_scaffold(tmp_path):
    """★ the LIVE path — research("USDC") on the DEFAULT (v3) template auto-produces
    the scaffold: the machine facts table injected at <!-- MODULE: metrics -->, the
    writer's MODULE anchors left intact, and NO legacy v2 [AUTO]/Evidence-Table
    artifacts (those belong to the v2 fill path)."""
    if not TEMPLATE_V3.exists():
        pytest.skip("v3 skeleton absent")
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")

    # default template is now v3 — no template_path override
    path = orchestrate.research("USDC", out_dir=tmp_path, bundle=True)
    md = path.read_text(encoding="utf-8")

    # the 2a filler placed the machine facts table (subject-agnostic sub-tables)
    assert "**Spot metrics**" in md
    assert "**Supply momentum**" in md
    assert "**Issuer financials** (Circle · FY2025)" in md
    # machine numbers present (a spot-check the ⑤.1 gate would also enforce)
    assert "$2.75B" in md and "-1.62%" in md and "#6" in md
    # the metrics anchor was CONSUMED; the writer's anchors remain for the narrative
    import re as _re
    assert not _re.search(r"(?m)^<!-- MODULE: metrics -->[ \t]*$", md)
    for anchor in ("metrics-analysis", "mechanism", "comparison-matrix",
                   "valuation", "risk-rows", "thesis-breakers", "charts"):
        assert f"<!-- MODULE: {anchor} -->" in md
    # the legacy v2 fill artifacts must NOT appear on the v3 path
    assert "Auto Evidence Table" not in md
    assert "[AUTO module-aware]" not in md
    # the bundle was written next to the .md (same stem)
    assert path.with_suffix(".facts.json").exists()


def test_v3_live_path_scaffold_renders_and_traces(tmp_path):
    """★ the LIVE path end-to-end (deterministic half): research("USDC", html=True,
    bundle=True) on the default v3 template auto-produces the scaffold .md + .html +
    .facts.json; the HTML write is fail-closed behind ④.3 (so its existence proves
    ④.3 passed), the scaffold carries every machine number (⑤.1 traces clean), and
    the charts + provenance render from facts=. (The writer's narrative half needs
    the LLM subagent and is exercised by the /research command, not pytest.)"""
    if not TEMPLATE_V3.exists():
        pytest.skip("v3 skeleton absent")
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    import json
    from analysis_layer.qc.numbers import check_numbers_trace

    path = orchestrate.research("USDC", out_dir=tmp_path, html=True, bundle=True)
    html_path = path.with_suffix(".html")
    bundle_path = path.with_suffix(".facts.json")
    # ④.3 fail-closed: _run RAISES before writing the .html if validation fails, so
    # the file existing IS the proof the gate passed.
    assert html_path.exists()
    assert bundle_path.exists()

    # the 2a filler placed the machine facts table
    md = path.read_text(encoding="utf-8")
    assert "**Spot metrics**" in md and "**Issuer financials**" in md

    # ⑤.1: every machine value traces into the scaffold
    facts = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert check_numbers_trace(md, facts) == []

    # charts (④.2) + provenance (TD-051) rendered from facts=
    html = html_path.read_text(encoding="utf-8")
    assert 'class="chart-at-glance"' in html and html.count("<svg") == 2
    assert 'class="data-sources"' in html
    assert html.count('<span class="src" ') > 0


def test_research_is_deterministic_in_content(tmp_path):
    """Two runs on the same envelopes → byte-identical report CONTENT (only the
    filename's UTC stamp may differ)."""
    if not TEMPLATE_V14.exists():
        pytest.skip("v1.4 template absent")
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")

    p1 = orchestrate.research("USDC", out_dir=tmp_path)
    p2 = orchestrate.research("USDC", out_dir=tmp_path)
    assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")


def test_load_and_extract_wires_all_present_sources():
    """The reusable building block extracts from every present source, including
    sec_edgar (so the fetch front, B.2.11, can reuse it)."""
    if not _have_usdc_envelopes():
        pytest.skip("no real USDC envelopes on disk")
    values = orchestrate.load_and_extract("USDC", raw_dir=RAW)
    assert values, "expected extracted values from on-disk envelopes"
    sources = {v.source for v in values}
    # on-chain supply + aggregator spot metrics + SEC financials all present
    assert "sec_edgar" in sources
    assert {"coingecko", "etherscan"} & sources
