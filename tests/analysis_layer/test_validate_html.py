"""④.3 (TD-047) — the fail-closed rendered-HTML validator + design drift-guard.

PURE, no network. A clean rendered report validates to []; each injected
violation is caught; the geometry check is scoped to SVG ATTRIBUTES (prose words
like "financials"/"covenant" that contain nan/… substrings do NOT trip it); and
a SHA pin on the embedded design CSS makes design drift a conscious act.
"""
from __future__ import annotations

import hashlib

import pytest

from analysis_layer.render.html import _DESIGN_CSS, render_html
from analysis_layer.render.validate import validate_report_html

# Reuse the synthetic fixtures the renderer tests already exercise.
from tests.analysis_layer.test_render_html import FACTS, SYNTHETIC


# --------------------------------------------------------------------------- #
# clean reports validate to []
# --------------------------------------------------------------------------- #
def test_clean_report_no_facts_validates_clean():
    html = render_html(SYNTHETIC)  # has an Evidence Table + every status marker
    assert validate_report_html(html, facts_present=False) == []


def test_clean_report_with_charts_validates_clean():
    html = render_html(SYNTHETIC, facts=FACTS)
    assert validate_report_html(html, facts_present=True) == []


# --------------------------------------------------------------------------- #
# each violation is caught
# --------------------------------------------------------------------------- #
def test_coaching_leak_caught():
    html = render_html(SYNTHETIC)
    leaked = html.replace(
        "<body>", "<body>\n<blockquote>GUIDANCE: leaked coaching</blockquote>"
    )
    out = validate_report_html(leaked)
    assert any("coaching leak" in v and "GUIDANCE" in v for v in out)


def test_coaching_mention_in_prose_not_flagged():
    """A blockquote that merely NAMES the channel (not a coaching blockquote) is
    fine — the check anchors to a marker LEADING a blockquote."""
    html = render_html(
        "# T\n\n> VERSION NOTE — the GUIDANCE / TRAP channel is writer-facing.\n"
    )
    assert not any("coaching leak" in v for v in validate_report_html(html))


def test_external_script_caught():
    html = render_html(SYNTHETIC).replace("</body>", "<script>x()</script></body>")
    out = validate_report_html(html)
    assert any("external resource" in v and "<script" in v for v in out)


def test_external_cdn_url_caught():
    html = render_html(SYNTHETIC).replace(
        "</head>", '<link href="https://cdn.example.com/x.css"></head>'
    )
    out = validate_report_html(html)
    # both the https:// and the <link / cdn markers register
    assert any("external resource" in v for v in out)
    assert any("https://" in v for v in out)


def test_negative_svg_width_caught():
    html = render_html(SYNTHETIC, facts=FACTS).replace(
        "</body>", '<svg viewBox="0 0 10 10"><rect width="-5" height="3"/></svg></body>'
    )
    out = validate_report_html(html, facts_present=True)
    assert any("chart geometry" in v and "negative" in v for v in out)


def test_nan_svg_coord_caught():
    html = render_html(SYNTHETIC, facts=FACTS).replace(
        "</body>", '<svg viewBox="0 0 10 10"><rect x="NaN" width="3" height="3"/></svg></body>'
    )
    out = validate_report_html(html, facts_present=True)
    assert any("chart geometry" in v and "non-finite" in v for v in out)


def test_missing_report_head_caught():
    html = render_html(SYNTHETIC).replace('class="report-head"', 'class="xxx"')
    out = validate_report_html(html)
    assert any("report-head" in v for v in out)


# --------------------------------------------------------------------------- #
# false-positive guard — geometry check is scoped to SVG ATTRIBUTES, not text
# --------------------------------------------------------------------------- #
def test_geometry_false_positive_guard():
    """PROSE containing nan/… substrings ('financials', 'covenant') with CLEAN SVG
    geometry must validate []. Proves the check reads attribute values, not text."""
    html = render_html(
        "# Issuer financials\n\nThe covenant on the issuer financials is fine.\n",
        facts=FACTS,
    )
    out = validate_report_html(html, facts_present=True)
    assert "financials" in html and "covenant" in html       # the nan-substring prose is present
    assert not any("chart geometry" in v for v in out)        # but geometry is clean


def test_facts_absent_skips_chart_integrity():
    """facts_present=False skips the chart-integrity check — even a broken SVG and
    a missing 'At a glance' section are NOT reported (no facts → no charts asked)."""
    html = render_html(SYNTHETIC).replace(
        "</body>", '<svg><rect width="-9" height="1"/></svg></body>'
    )
    out = validate_report_html(html, facts_present=False)
    assert not any("chart geometry" in v for v in out)
    assert not any("At a glance" in v for v in out)


def test_wellformed_checks():
    out = validate_report_html("<div>not a document</div>")
    assert any("<!DOCTYPE html>" in v for v in out)
    assert any("<html>" in v for v in out)
    assert any("</html>" in v for v in out)


# --------------------------------------------------------------------------- #
# locked-design drift-guard — pin the SHA-256 of the embedded design CSS
# --------------------------------------------------------------------------- #
# If the design CSS legitimately changes, update this pin in the SAME commit —
# that makes design drift a conscious, reviewed act rather than a silent one.
DESIGN_CSS_SHA = "48f4ef4b01beb373e8f0ee2edcb89fc713d0cd31ea424b4ade8615dc278e4bb8"


def test_design_css_sha_pin():
    actual = hashlib.sha256(_DESIGN_CSS.encode("utf-8")).hexdigest()
    assert actual == DESIGN_CSS_SHA, (
        "design CSS changed — if intentional, update DESIGN_CSS_SHA "
        f"(new sha {actual})"
    )
