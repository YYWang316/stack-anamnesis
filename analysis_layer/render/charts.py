"""analysis_layer/render/charts.py — inline-SVG chart builders (④.2 TD-047).

PURE, self-contained, deterministic SVG drawing for the report renderer. Each
builder reads ONLY the facts bundle's structured fields (``build_facts_bundle``
output, TD-041) and returns an inline ``<svg>`` string — or ``None`` when the
data it needs is absent/empty, so the caller can render an honest "no data this
run" placeholder instead of a fabricated chart.

★ SUBJECT-AGNOSTIC by construction. Nothing here is keyed to USDC, to Circle, or
to any literal value: the charts are driven entirely by the bundle's FIELD NAMES
(``supply_momentum[].net_change_pct`` / ``issuer_financials[<concept>].value``).
Any future subject whose bundle carries those fields gets the chart automatically
with ITS numbers; a subject missing them gets ``None`` here (→ placeholder).

Constraints (same as ④.1): inline SVG only — no external resources, no ``<script>``,
no JavaScript; stdlib only — no chart library, no new dependency; deterministic —
no clock, no randomness, fixed ``viewBox`` and fixed number formatting, so the
same facts always produce byte-identical SVG. Colours reference the document's
CSS custom properties (``fill="var(--ok-ink)"`` …): they resolve because the SVG
is inlined into the same HTML document that embeds the design's ``:root`` palette.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# tiny SVG primitives + deterministic formatters
# --------------------------------------------------------------------------- #
_MINUS = "−"  # U+2212 MINUS SIGN — matches the renderer's signed-delta style


def _n(v: float) -> str:
    """A coordinate / length → fixed 2-decimal string (deterministic, no -0.00)."""
    s = f"{v:.2f}"
    return "0.00" if s == "-0.00" else s


def _xesc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_pct(v: float) -> str:
    """Signed percent with 2 decimals: ``+0.24%`` / ``−1.62%`` (U+2212 minus)."""
    sign = "+" if v >= 0 else _MINUS
    return f"{sign}{abs(v):.2f}%"


def _fmt_usd(v: float) -> str:
    """Signed magnitude-suffixed dollars: ``$2.75B`` / ``−$69.5M`` / ``$78.71B``.

    Subject-agnostic: just scales whatever number it is handed; the unit label is
    carried separately from the bundle field's own ``unit``.
    """
    sign = _MINUS if v < 0 else ""
    a = abs(float(v))
    if a >= 1e9:
        body = f"${a / 1e9:.2f}B"
    elif a >= 1e6:
        body = f"${a / 1e6:.1f}M"
    elif a >= 1e3:
        body = f"${a / 1e3:.1f}K"
    else:
        body = f"${a:.0f}"
    return sign + body


def _rect(x: float, y: float, w: float, h: float, fill: str) -> str:
    return (
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" '
        f'fill="{fill}" rx="1.5"/>'
    )


def _line(x1: float, y1: float, x2: float, y2: float, stroke: str,
          width: float = 1.0, dash: Optional[str] = None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
        f'stroke="{stroke}" stroke-width="{_n(width)}"{d}/>'
    )


def _text(x: float, y: float, s: str, size: float, anchor: str, fill: str,
          weight: str = "400") -> str:
    return (
        f'<text x="{_n(x)}" y="{_n(y)}" font-family="var(--font-ui)" '
        f'font-size="{_n(size)}" text-anchor="{anchor}" fill="{fill}" '
        f'font-weight="{weight}">{_xesc(s)}</text>'
    )


def _svg_open(w: float, h: float, title: str) -> str:
    # NB: no xmlns — inline SVG in an HTML5 document needs none, and omitting it
    # keeps the http:// namespace URI out of the otherwise self-contained file.
    return (
        f'<svg viewBox="0 0 {_n(w)} {_n(h)}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="{_xesc(title)}"><title>{_xesc(title)}</title>'
    )


# --------------------------------------------------------------------------- #
# 1 · supply momentum — signed vertical bars around a zero baseline
# --------------------------------------------------------------------------- #
def supply_momentum_svg(supply_momentum: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """One signed bar per window from ``facts["supply_momentum"]``.

    Each bar's height ∝ ``|net_change_pct|`` around a central zero baseline;
    positive → ``var(--ok-ink)``, negative → ``var(--bad-ink)``. Every bar is
    labelled with its window (``7d`` / ``30d`` / ``90d`` / whatever is present)
    and its signed value. Returns ``None`` when no window carries a usable
    ``net_change_pct`` (caller then renders the empty placeholder)."""
    if not supply_momentum:
        return None
    items: List[Tuple[float, str, float]] = []
    for w in supply_momentum:
        if not isinstance(w, Mapping):
            continue
        pct = w.get("net_change_pct")
        if not isinstance(pct, (int, float)):
            continue
        wd = w.get("window_days")
        order = float(wd) if isinstance(wd, (int, float)) else 0.0
        label = str(w.get("window") or (f"{int(order)}d" if order else "?"))
        items.append((order, label, float(pct)))
    if not items:
        return None
    items.sort(key=lambda t: (t[0], t[1]))

    W, H = 360.0, 220.0
    x0, x1 = 30.0, 342.0
    plot_top, plot_bot = 44.0, 166.0
    baseline = (plot_top + plot_bot) / 2.0
    half = (plot_bot - plot_top) / 2.0
    max_abs = max(abs(p) for _, _, p in items) or 1.0
    n = len(items)
    slot = (x1 - x0) / n
    bar_w = min(slot * 0.5, 54.0)

    out: List[str] = [_svg_open(W, H, "Supply momentum — net supply change by window")]
    out.append(_text(x0, 22.0, "Supply momentum", 12.0, "start",
                     "var(--color-ink)", "650"))
    out.append(_text(x1, 22.0, "net change %", 10.0, "end", "var(--color-muted)"))
    # zero baseline
    out.append(_line(x0, baseline, x1, baseline, "var(--color-rule-strong)", 1.0,
                     dash="2 3"))
    out.append(_text(x0 - 2.0, baseline - 3.0, "0%", 8.5, "start",
                     "var(--color-faint)"))

    for i, (_, label, pct) in enumerate(items):
        cx = x0 + slot * (i + 0.5)
        h = abs(pct) / max_abs * half
        if pct >= 0:
            by = baseline - h
            fill = "var(--ok-ink)"
            vy = by - 6.0
        else:
            by = baseline
            fill = "var(--bad-ink)"
            vy = baseline + h + 13.0
        out.append(_rect(cx - bar_w / 2.0, by, bar_w, h, fill))
        out.append(_text(cx, vy, _fmt_pct(pct), 10.0, "middle",
                         "var(--color-ink)", "600"))
        out.append(_text(cx, H - 12.0, label, 10.0, "middle", "var(--color-muted)"))
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# 2 · issuer financials — flow vs stock, each on its OWN scale (no mixed axis)
# --------------------------------------------------------------------------- #
# (bundle field, display label) — the float-business shape. Flow ($ over a fiscal
# year) and stock ($ at fiscal-year-end) are drawn as SEPARATE panels so the two
# unit kinds never share one misleading axis (the ④.2 CAUTION).
_FLOW_FIELDS = (("revenues", "Revenue"), ("net_income", "Net income"))
_STOCK_FIELDS = (("assets", "Assets"), ("liabilities", "Liabilities"),
                 ("equity", "Equity"))


def _pick(financials: Mapping[str, Any],
          fields: Sequence[Tuple[str, str]]) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for key, label in fields:
        cell = financials.get(key)
        if isinstance(cell, Mapping) and isinstance(cell.get("value"), (int, float)):
            out.append((label, float(cell["value"])))
    return out


def _unit_of(financials: Mapping[str, Any],
             fields: Sequence[Tuple[str, str]]) -> str:
    for key, _ in fields:
        cell = financials.get(key)
        if isinstance(cell, Mapping) and cell.get("unit"):
            return str(cell["unit"])
    return ""


def _hbar_panel(items: Sequence[Tuple[str, float]], title: str,
                y0: float) -> Tuple[List[str], float]:
    """A horizontal signed-bar sub-panel scaled to ITS OWN max. Returns the SVG
    fragments and the y after the panel. Positive bars → navy accent; a negative
    bar (e.g. net loss) → ``var(--bad-ink)`` red. Each row labelled + valued."""
    label_x = 14.0
    bar_left, bar_right = 104.0, 286.0
    row_h = 26.0
    bar_h = 13.0

    vals = [v for _, v in items]
    max_pos = max((v for v in vals if v > 0), default=0.0)
    max_neg = max((-v for v in vals if v < 0), default=0.0)
    has_neg = max_neg > 0
    zero_x = bar_left + 38.0 if has_neg else bar_left
    right_span = bar_right - zero_x
    left_span = zero_x - bar_left
    scale = float("inf")
    if max_pos > 0:
        scale = min(scale, right_span / max_pos)
    if max_neg > 0:
        scale = min(scale, left_span / max_neg)
    if scale == float("inf"):
        scale = 0.0

    out: List[str] = []
    title_y = y0 + 12.0
    out.append(_text(label_x, title_y, title, 11.0, "start",
                     "var(--color-accent)", "700"))
    rows_top = title_y + 8.0
    rows_bot = rows_top + row_h * len(items)
    if has_neg:
        out.append(_line(zero_x, rows_top, zero_x, rows_bot,
                         "var(--color-rule-strong)", 1.0))
    for i, (label, v) in enumerate(items):
        cy = rows_top + row_h * (i + 0.5)
        out.append(_text(label_x, cy + 3.5, label, 10.0, "start",
                         "var(--color-ink-soft)"))
        w = abs(v) * scale
        if v >= 0:
            out.append(_rect(zero_x, cy - bar_h / 2.0, w, bar_h,
                             "var(--color-accent)"))
            out.append(_text(zero_x + w + 5.0, cy + 3.5, _fmt_usd(v), 10.0,
                             "start", "var(--color-ink)", "600"))
        else:
            out.append(_rect(zero_x - w, cy - bar_h / 2.0, w, bar_h,
                             "var(--bad-ink)"))
            out.append(_text(zero_x - w - 5.0, cy + 3.5, _fmt_usd(v), 10.0,
                             "end", "var(--bad-ink)", "600"))
    return out, rows_bot


def issuer_financials_svg(issuer_financials: Optional[Mapping[str, Any]]) -> Optional[str]:
    """The issuer's float-business shape from ``facts["issuer_financials"]``.

    Flow facts (``revenues`` / ``net_income``) and stock facts (``assets`` /
    ``liabilities`` / ``equity``) are drawn in SEPARATE panels, each on its own
    scale, so the two unit kinds are never mixed on one misleading axis. Units +
    fiscal year are labelled; a negative ``net_income`` bar is red. Returns
    ``None`` when neither group has any numeric field (→ placeholder)."""
    if not issuer_financials:
        return None
    flow = _pick(issuer_financials, _FLOW_FIELDS)
    stock = _pick(issuer_financials, _STOCK_FIELDS)
    if not flow and not stock:
        return None

    fy = issuer_financials.get("fiscal_year")
    fy_txt = f"FY{fy}" if fy is not None else "FY n/a"

    W, H = 360.0, 240.0
    out: List[str] = [_svg_open(W, H, f"Issuer financials — {fy_txt}")]
    out.append(_text(14.0, 18.0, "Issuer financials", 12.0, "start",
                     "var(--color-ink)", "650"))
    out.append(_text(W - 14.0, 18.0, fy_txt, 10.0, "end", "var(--color-muted)"))

    y = 26.0
    if flow:
        unit = _unit_of(issuer_financials, _FLOW_FIELDS)
        title = f"Flow · {fy_txt} annual" + (f" ({unit})" if unit else "")
        frag, y = _hbar_panel(flow, title, y)
        out.extend(frag)
        y += 14.0
    if stock:
        unit = _unit_of(issuer_financials, _STOCK_FIELDS)
        title = f"Stock · {fy_txt} year-end" + (f" ({unit})" if unit else "")
        frag, y = _hbar_panel(stock, title, y)
        out.extend(frag)
    out.append("</svg>")
    return "".join(out)
