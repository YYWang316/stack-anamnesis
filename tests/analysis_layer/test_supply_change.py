"""Unit tests for analysis_layer/derivations/supply_change.py (B.2.9, TD-035).

The change layer derives net 7d / 30d / 90d supply momentum (KEY SIGNAL leg 1/3)
from the DefiLlama historical supply series. These tests use SYNTHETIC series only —
no network, no on-disk envelopes — to pin the arithmetic, the insufficient-history
skip (nothing faked), the non-contemporaneous day-gap honesty, and the direction
dead-band. The real-data end-to-end lives in tests/analysis_layer/test_filler.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from analysis_layer.contract import ReconciledValue
from analysis_layer.derivations.supply_change import compute_supply_change

NOW = datetime(2026, 5, 28, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# synthetic-envelope builders (shape verified against the real DefiLlama
# stablecoin-chart envelope: a list of daily points under "raw_response", each
# carrying totalCirculating.peggedUSD as the nominal supply)
# --------------------------------------------------------------------------- #
def _point(dt: datetime, supply: float) -> dict:
    return {
        "date": str(int(dt.timestamp())),
        "totalCirculating": {"peggedUSD": supply},
        "totalCirculatingUSD": {"peggedUSD": supply},
    }


def _envelope(points: list) -> dict:
    return {"subject": "USDC", "subject_type": "stablecoin", "raw_response": points}


def _daily(supply_fn, n_days: int, end: datetime = NOW) -> dict:
    """A contiguous daily series of ``n_days`` ending at ``end`` (i=0 oldest)."""
    pts = [_point(end - timedelta(days=n_days - 1 - i), supply_fn(i)) for i in range(n_days)]
    return _envelope(pts)


def _by_metric(values):
    return {rv.metric: rv for rv in values}


# --------------------------------------------------------------------------- #
# 1. clean: known series -> correct abs / pct / direction for 7d / 30d / 90d
# --------------------------------------------------------------------------- #
def test_clean_series_correct_abs_pct_direction():
    base, step, n = 100e9, 1e9, 100        # supply(i) = base + i*step (rising)
    env = _daily(lambda i: base + i * step, n)
    values, notes = compute_supply_change(env, None)

    assert notes == []                     # full coverage -> nothing skipped
    by = _by_metric(values)
    assert set(by) == {"net_supply_change_7d", "net_supply_change_30d",
                       "net_supply_change_90d"}

    now_value = base + (n - 1) * step      # 199e9
    for days in (7, 30, 90):
        rv = by[f"net_supply_change_{days}d"]
        assert isinstance(rv, ReconciledValue)
        then_value = base + (n - 1 - days) * step
        assert rv.audit["now_value"] == now_value
        assert rv.audit["then_value"] == then_value
        assert rv.audit["abs_change"] == days * step                 # exact
        assert abs(rv.audit["pct_change"] - days * step / then_value) < 1e-12
        assert abs(rv.value - rv.audit["pct_change"] * 100.0) < 1e-9  # value = % points
        assert rv.audit["actual_days"] == float(days)                # contemporaneous
        assert rv.audit["direction"] == "up"
        assert rv.unit == "%"
        assert rv.source_used == "defillama"
        assert rv.agreement == "single_source"
        assert rv.scope == "multi_chain"                             # series scope
        assert len(rv.inputs) == 2                                   # then + now


# --------------------------------------------------------------------------- #
# 2. short history: ~25-day series -> 7d computed, 30d & 90d SKIPPED w/ a note
# --------------------------------------------------------------------------- #
def test_short_history_skips_long_windows_with_note():
    env = _daily(lambda i: 100e9 + i * 1e9, 25)    # only 25 days of history
    values, notes = compute_supply_change(env, None)

    by = _by_metric(values)
    assert "net_supply_change_7d" in by            # 7d fits in 25 days
    assert "net_supply_change_30d" not in by       # 30d does not
    assert "net_supply_change_90d" not in by       # 90d does not

    # the skips are SURFACED as notes, not silently dropped or faked
    assert any("net_supply_change_30d" in nt and "insufficient history" in nt for nt in notes)
    assert any("net_supply_change_90d" in nt and "insufficient history" in nt for nt in notes)
    # nothing fabricated for the skipped windows
    assert all("net_supply_change_30d" != v.metric for v in values)


# --------------------------------------------------------------------------- #
# 3. non-contemporaneous: no exact point at now-7d -> nearest used, gap recorded
# --------------------------------------------------------------------------- #
def test_non_contemporaneous_records_actual_day_gap():
    # daily points EXCEPT the 7- and 8-day-ago points are missing, so the nearest
    # point to the 7d target is 6 days ago -> a "7d" window over 6.0 real days.
    offsets = [0, 1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15]
    pts = [_point(NOW - timedelta(days=off), 100e9 + (15 - off) * 1e9)
           for off in sorted(offsets, reverse=True)]   # oldest -> newest
    env = _envelope(pts)

    values, _notes = compute_supply_change(env, None, windows=(7,))
    rv = _by_metric(values)["net_supply_change_7d"]

    assert rv.audit["window_days"] == 7
    assert rv.audit["actual_days"] != 7.0          # NOT contemporaneous
    assert rv.audit["actual_days"] == 6.0          # nearest available is 6d ago
    assert rv.audit["then_date"] == (NOW - timedelta(days=6)).date().isoformat()


# --------------------------------------------------------------------------- #
# 4. direction: rising / flat / falling -> correct signs (flat dead-band)
# --------------------------------------------------------------------------- #
def test_direction_rising_flat_falling():
    rising = _daily(lambda i: 100e9 + i * 1e9, 40)
    falling = _daily(lambda i: 140e9 - i * 1e9, 40)
    # flat: a move below the 5bps dead-band over the window -> "flat", not a slope.
    # +0.01% over the whole series is well under flat_band=0.0005.
    flat = _daily(lambda i: 100e9 * (1.0 + 0.0001 * (i / 39)), 40)

    up = _by_metric(compute_supply_change(rising, None, windows=(30,))[0])
    down = _by_metric(compute_supply_change(falling, None, windows=(30,))[0])
    level = _by_metric(compute_supply_change(flat, None, windows=(30,))[0])

    assert up["net_supply_change_30d"].audit["direction"] == "up"
    assert up["net_supply_change_30d"].value > 0
    assert down["net_supply_change_30d"].audit["direction"] == "down"
    assert down["net_supply_change_30d"].value < 0
    assert level["net_supply_change_30d"].audit["direction"] == "flat"
    assert abs(level["net_supply_change_30d"].audit["pct_change"]) < 0.0005


# --------------------------------------------------------------------------- #
# 5. degenerate input -> no fabrication, a note instead
# --------------------------------------------------------------------------- #
def test_too_few_points_returns_note_not_value():
    values, notes = compute_supply_change(_envelope([]), None)
    assert values == []
    assert notes and "insufficient history" in notes[0]
