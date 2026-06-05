"""B.4 (TD-040) — the pure markdown→HTML renderer + its --html wiring.

No network. The unit tests run a synthetic report that contains every status
marker the filler emits plus an Evidence Table; the e2e test renders the real
USDC report and skips when its on-disk envelopes are absent.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis_layer.render.html import render_html

ROOT = Path(__file__).resolve().parents[2]

# A synthetic report mirroring the real template's markers (see meta/reports/).
SYNTHETIC = """# USDC (Circle) — automated data snapshot

## Part 1 — Thesis & Framing

### 1.4 Evidence Table

| # | Claim | Source | Confidence |
|---|-------|--------|------------|
| 1 | USDC single-chain supply 52.08B | alchemy | High |
| 2 | Net 30d supply down 1.71% | defillama | Medium |
| 3 | Payment adoption share | manual | Low |

## Part 5 — On-Chain Metrics

#### A. Supply & Distribution

- Total supply / mint / burn `[AUTO ✓ FILLED: DefiLlama stablecoins]`
    - **single-chain (ethereum)** — 52.08B USDC · source `alchemy` · confidence **High** (agree)
    - **cross-chain** — 76.02B USDC · source `coingecko` · confidence **High** (agree)
- Net 7d / 30d supply change `[SEMI-AUTO ✓ COMPUTED: DefiLlama historical]`
- Per-chain supply breakdown `[AUTO: DefiLlama by chain]`  → ⚠ **UNFILLED [AUTO]** — left flagged, NOT fabricated
- Native vs bridged supply `[SEMI-AUTO: DefiLlama + issuer docs]`  → ⚠ **NEEDS HUMAN REVIEW [SEMI-AUTO]** — verify manually
- Historical depeg events `[MANUAL: incident research]`  → ⚠ **MANUAL** — researcher must fill

> Confidence downgrade triggers: supply up but usage flat → mechanical growth risk.

---
"""


def _render():
    return render_html(SYNTHETIC)


# A Part-0-bearing report exercising the ④.1 design header, the coaching-strip
# backstop, and the ⭐→★ KEY SIGNAL normalisation.
DESIGN_DOC = """# Crypto Research Report Template

# REPORT BODY — the deliverable

## Part 0 — Meta `[Both]`

> **[AUTO subject_ref]** subject **USDC** · subject_type stablecoin · issuer Circle · decimals 6 · sec_cik=`0001876042`

- **Title**: USDC (Circle) — automated data snapshot `[AUTO subject_ref]`
- **Date**: 2026-05-28 (data as_of) `[AUTO — latest reconciled as_of]`

## Part 5 — On-Chain Metrics `[Mode A required]`

#### ⭐⭐ KEY SIGNAL — Supply Momentum: organic vs mechanical

Supply slope is the only demand signal a $1-pegged asset emits.

> GUIDANCE: think about whether supply growth is organic — coaching, strip it.
> a second coaching line in the same blockquote.

> TRAP: do not confuse trading volume with real demand.

> ↳ Cap check: single_source metrics are capped at MEDIUM.

> **[AUTO module-aware]** rendered for subject_type stablecoin — a normal blockquote, keep it.

- Total supply `[AUTO ✓ FILLED: DefiLlama stablecoins]`
"""


def test_headers_become_h_tags():
    html = _render()
    assert re.search(r"<h1[^>]*>.*USDC \(Circle\)", html)
    assert re.search(r"<h2[^>]*>.*Part 1", html)
    assert re.search(r"<h3[^>]*>.*Evidence Table", html)
    assert re.search(r"<h4[^>]*>.*Supply", html)


def test_evidence_table_rendered_as_table():
    html = _render()
    # ④.1 — the design styles table.memo, so the table now carries a class
    assert "<table" in html and "</table>" in html
    assert "<thead>" in html and "<th>" in html
    assert "<tbody>" in html and "<td>" in html
    assert "Claim" in html and "52.08B" in html


def test_lists_and_nesting_become_ul_li():
    html = _render()
    assert "<ul>" in html and "<li>" in html
    # the nested sub-bullets produce a nested <ul> inside an <li>
    assert "<li>" in html and html.count("<ul>") >= 2


def test_blockquote_rendered():
    html = _render()
    assert "<blockquote>" in html


def test_filled_markers_get_green_badge():
    html = _render()
    assert "badge-filled" in html
    # both the AUTO-FILLED and SEMI-AUTO-COMPUTED markers
    assert html.count("badge-filled") >= 2
    assert "AUTO ✓ FILLED" in html
    assert "SEMI-AUTO ✓ COMPUTED" in html


def test_needs_human_markers_get_amber_badge():
    html = _render()
    assert "badge-warn" in html
    assert "NEEDS HUMAN REVIEW" in html
    assert "UNFILLED [AUTO]" in html
    assert "MANUAL" in html
    # the [MANUAL: …] source tag gets its own amber badge
    assert "badge-manual" in html


def test_planned_tags_get_neutral_badge():
    html = _render()
    # [AUTO: …] / [SEMI-AUTO: …] planned-but-unfilled tags are neutral, not green
    assert "badge-tag" in html


def test_confidence_chips_present():
    html = _render()
    # running-text "confidence **High**" → chip
    assert "chip-high" in html
    # Evidence Table Medium / Low cells → chips
    assert "chip-med" in html
    assert "chip-low" in html


def test_self_contained_no_external_resources():
    html = _render()
    assert "<style>" in html
    assert "<link" not in html
    assert "src=" not in html
    assert "<script" not in html
    assert "@import" not in html
    assert "cdn" not in html.lower()
    assert "http://" not in html and "https://" not in html


def test_well_formed_document():
    html = _render()
    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html and "</html>" in html
    assert "<title>" in html


def test_title_override_used():
    html = render_html(SYNTHETIC, title="My Custom Title")
    assert "<title>My Custom Title</title>" in html


def test_title_defaults_to_first_h1():
    html = _render()
    assert "<title>USDC (Circle) — automated data snapshot</title>" in html


def test_deterministic():
    assert render_html(SYNTHETIC) == render_html(SYNTHETIC)


def test_no_raw_markers_leak_outside_badges():
    """A green-filled marker must not also appear as a bare backtick code span —
    i.e. the badge pass consumed it, the generic inline-code pass did not re-wrap."""
    html = _render()
    assert "<code>[AUTO ✓ FILLED" not in html


# --------------------------------------------------------------------------- #
# ④.1 — institutional-clean design adoption + coaching-strip backstop
# --------------------------------------------------------------------------- #
def test_design_classes_present():
    """The renderer emits the wrapper markup the design CSS targets."""
    html = _render()
    assert 'class="page"' in html
    assert 'class="part-title"' in html          # h2
    assert 'class="sub-title"' in html           # h3
    assert 'class="minor-title"' in html         # h4
    assert '<table class="memo">' in html
    assert 'class="table-wrap"' in html
    assert 'class="legend-item"' in html
    # the embedded design system carries its CSS-variable :root + print block
    assert ":root" in html and "@media print" in html


def test_design_header_renders_with_snapshot():
    """A Part-0 report gets a .report-head block with the title pulled from the
    'Title' line and an as_of snapshot pulled from the 'Date' line."""
    html = render_html(DESIGN_DOC)
    assert 'class="report-head"' in html
    assert 'class="snapshot"' in html
    assert "as_of" in html and "2026-05-28" in html
    # title comes from the Part 0 "- **Title**:" line, not the boilerplate h1
    assert "<title>USDC (Circle) — automated data snapshot</title>" in html
    assert re.search(r'<header class="report-head">.*<h1>USDC \(Circle\)', html, re.S)
    # subject_type / issuer surfaced in the snapshot when cleanly present
    assert "stablecoin" in html and "Circle" in html
    # the level-1 boilerplate headers are promoted out of the body, not duplicated
    assert "<h1>REPORT BODY" not in html and "Crypto Research Report Template" not in html


def test_header_title_only_when_no_date():
    """No clean Part-0 Date line → title only, no snapshot subline (graceful)."""
    html = render_html("# Just A Title\n\nsome body text.\n")
    assert 'class="report-head"' in html
    assert 'class="snapshot"' not in html
    assert "<title>Just A Title</title>" in html


def test_coaching_strip_backstop():
    """GUIDANCE / TRAP / ↳ Cap check blockquotes are removed whole; a normal
    blockquote in the same document survives."""
    html = render_html(DESIGN_DOC)
    assert "GUIDANCE" not in html
    assert "TRAP" not in html
    assert "Cap check" not in html
    assert "do not confuse trading volume" not in html   # TRAP body gone
    assert "capped at MEDIUM" not in html                # Cap-check body gone
    assert "second coaching line" not in html            # multi-line run fully removed
    # the normal [AUTO module-aware] blockquote was preserved
    assert "module-aware" in html
    assert "<blockquote>" in html


def test_normal_blockquote_not_stripped():
    html = _render()  # SYNTHETIC's "Confidence downgrade triggers:" blockquote
    assert "<blockquote>" in html
    assert "Confidence downgrade triggers" in html


def test_keysignal_star_normalization():
    """⭐ markers are normalised to ★ on output (display only)."""
    html = render_html(DESIGN_DOC)
    assert "★★ KEY SIGNAL" in html
    assert "⭐" not in html


def test_design_doc_deterministic():
    assert render_html(DESIGN_DOC) == render_html(DESIGN_DOC)


def test_e2e_research_writes_md_and_html(tmp_path):
    """research('USDC', html=True) over the on-disk envelopes writes BOTH a .md
    and a valid self-contained .html. Skips if no envelopes are present."""
    raw = ROOT / "meta" / "raw"
    if not list(raw.glob("*/*.json")):
        pytest.skip("no envelopes on disk under meta/raw/ — skipping e2e")

    from analysis_layer.orchestrate import research

    md_path = research("USDC", html=True, out_dir=tmp_path)
    assert md_path.exists() and md_path.suffix == ".md"

    html_path = md_path.with_suffix(".html")
    assert html_path.exists(), "html=True must write a .html next to the .md"
    html = html_path.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "<table" in html
    assert "badge" in html
    assert 'class="report-head"' in html  # ④.1 institutional header
    assert "<link" not in html and "src=" not in html
