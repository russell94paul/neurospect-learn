"""Unit tests for the pure expectancy math (Phase 5f) — NO DB.

This is the evidence-gated core of the proof-of-edge loop, so it is tested
against HAND-BUILT fixtures with answers worked out by hand, mirroring
services/scheduler.py's no-DB unit tests. Two independent checks guard the
formula: (1) the by-hand win%/avgWinR/avgLossR/expectancy/break-even, and
(2) the algebraic identity expectancy == mean(closed r).
"""

import statistics

from app.services.expectancy import (
    POOLED,
    SAMPLE_TARGET,
    TradeR,
    compute_groups,
    compute_mode_summaries,
    compute_pooled,
    compute_r_distribution,
)


def _r(model, mode, r, rr=None):
    return TradeR(entry_model=model, mode=mode, r_multiple=r, rr_planned=rr)


def test_expectancy_hand_built():
    # london/backtest: 2 winners of +2R, 3 losers of -1R, each planned 2R:R.
    #   win_rate = 2/5 = 0.4;  avg win R = 2.0;  avg loss R = 1.0
    #   expectancy = 0.4·2 − 0.6·1 = 0.8 − 0.6 = 0.2
    #   break-even = 1/(1+2) = 0.3333;  0.4 ≥ 0.3333 → above
    trades = [
        _r("london", "backtest", 2.0, 2.0),
        _r("london", "backtest", 2.0, 2.0),
        _r("london", "backtest", -1.0, 2.0),
        _r("london", "backtest", -1.0, 2.0),
        _r("london", "backtest", -1.0, 2.0),
    ]
    (g,) = compute_groups(trades)
    assert (g.entry_model, g.mode) == ("london", "backtest")
    assert g.logged == 5 and g.n == 5
    assert (g.wins, g.losses, g.breakevens) == (2, 3, 0)
    assert g.win_rate == 0.4
    assert g.avg_win_r == 2.0
    assert g.avg_loss_r == 1.0
    assert g.expectancy == 0.2
    assert g.avg_rr_planned == 2.0
    assert g.break_even == round(1 / 3, 4)  # 0.3333
    assert g.above_break_even is True
    assert g.sample_target == SAMPLE_TARGET and g.sample_met is False


def test_expectancy_equals_mean_of_r():
    # Independent identity check on an irregular set.
    rs = [3.0, -1.0, -1.0, 2.0, 0.0, -1.0, 1.5, -0.5]
    trades = [_r("model_2022_ote", "live", r) for r in rs]
    (g,) = compute_groups(trades)
    assert g.n == len(rs)
    assert g.expectancy == round(statistics.mean(rs), 3)


def test_open_trades_excluded_from_sample_but_counted_as_logged():
    trades = [
        _r("consolidation", "backtest", 1.0),
        _r("consolidation", "backtest", None),   # open — no realized R
        _r("consolidation", "backtest", None),
    ]
    (g,) = compute_groups(trades)
    assert g.logged == 3 and g.n == 1
    assert g.expectancy == 1.0


def test_breakeven_counts_toward_sample_but_not_win_or_loss():
    trades = [
        _r("london", "backtest", 0.0),
        _r("london", "backtest", 0.0),
    ]
    (g,) = compute_groups(trades)
    assert g.n == 2 and g.breakevens == 2 and g.wins == 0 and g.losses == 0
    assert g.win_rate == 0.0
    assert g.avg_win_r is None and g.avg_loss_r is None
    assert g.expectancy == 0.0


def test_break_even_none_without_planned_rr():
    trades = [_r("daily_bias", "backtest", 1.0), _r("daily_bias", "backtest", -1.0)]
    (g,) = compute_groups(trades)
    assert g.avg_rr_planned is None
    assert g.break_even is None
    assert g.above_break_even is None


def test_grouping_splits_model_and_mode_and_is_ordered():
    trades = [
        _r("london", "live", 1.0),
        _r("london", "backtest", 1.0),
        _r("consolidation", "backtest", 1.0),
    ]
    groups = compute_groups(trades)
    keys = [(g.entry_model, g.mode) for g in groups]
    # sorted by (model, mode): consolidation/backtest, london/backtest, london/live
    assert keys == [
        ("consolidation", "backtest"),
        ("london", "backtest"),
        ("london", "live"),
    ]


def test_mode_summaries_always_both_axes_and_pooled():
    trades = [
        _r("london", "backtest", 2.0),
        _r("consolidation", "backtest", -1.0),
        _r("london", "live", 3.0),
    ]
    summaries = {m.mode: m for m in compute_mode_summaries(trades)}
    assert set(summaries) == {"backtest", "live"}
    bt = summaries["backtest"]
    assert bt.n == 2 and bt.total_r == 1.0 and bt.expectancy == 0.5
    lv = summaries["live"]
    assert lv.n == 1 and lv.total_r == 3.0 and lv.expectancy == 3.0


def test_mode_summaries_empty_mode_is_zeroed_not_missing():
    trades = [_r("london", "backtest", 1.0)]
    summaries = {m.mode: m for m in compute_mode_summaries(trades)}
    assert summaries["live"].n == 0
    assert summaries["live"].expectancy is None
    assert summaries["live"].total_r is None


def test_r_distribution_buckets_split_by_mode():
    trades = [
        _r("london", "backtest", -2.5),  # ≤ -2R
        _r("london", "backtest", 0.5),   # 0 to 1R
        _r("london", "live", 2.0),       # 2 to 3R
        _r("london", "live", 5.0),       # ≥ 3R
        _r("london", "live", None),      # open — excluded
    ]
    dist = {b["label"]: b for b in compute_r_distribution(trades)}
    assert dist["≤ -2R"]["backtest"] == 1 and dist["≤ -2R"]["live"] == 0
    assert dist["0 to 1R"]["backtest"] == 1
    assert dist["2 to 3R"]["live"] == 1
    assert dist["≥ 3R"]["live"] == 1
    # total counted = 4 (the open trade is excluded)
    assert sum(b["backtest"] + b["live"] for b in dist.values()) == 4


# ---------------------------------------------------------------------------
# compute_pooled (Phase 6a) — the stage-level view of the same evidence
# ---------------------------------------------------------------------------

def test_pooled_group_spans_models_but_never_modes():
    # backtest: london +2/-1 and daily_bias +2/-1/-1, all planned 2R:R →
    #   5 closed pooled: wins 2 (+2 each), losses 3 (-1 each)
    #   expectancy = 0.4·2 − 0.6·1 = 0.2; win 0.4; break-even 1/3 → above
    trades = [
        _r("london", "backtest", 2.0, 2.0),
        _r("london", "backtest", -1.0, 2.0),
        _r("daily_bias", "backtest", 2.0, 2.0),
        _r("daily_bias", "backtest", -1.0, 2.0),
        _r("daily_bias", "backtest", -1.0, 2.0),
        _r("london", "live", 9.0, 2.0),  # the live axis must NOT leak in
    ]
    g = compute_pooled(trades, "backtest")
    assert g is not None
    assert g.entry_model == POOLED and g.mode == "backtest"
    assert g.n == 5 and (g.wins, g.losses) == (2, 3)
    assert g.expectancy == 0.2 and g.win_rate == 0.4
    assert g.break_even == round(1 / 3, 4) and g.above_break_even is True

    live = compute_pooled(trades, "live")
    assert live is not None and live.n == 1 and live.expectancy == 9.0


def test_pooled_matches_the_per_model_math_when_there_is_one_model():
    """Reuse proof: pooling delegates to compute_groups, so a single-model sample
    yields identical stats under both entry points."""
    trades = [_r("london", "backtest", r, 2.0) for r in (2.0, 2.0, -1.0, -1.0, -1.0)]
    (per_model,) = compute_groups(trades)
    pooled = compute_pooled(trades, "backtest")
    assert pooled is not None
    for f in ("logged", "n", "wins", "losses", "breakevens", "win_rate", "avg_win_r",
              "avg_loss_r", "expectancy", "avg_rr_planned", "break_even",
              "above_break_even", "sample_met"):
        assert getattr(pooled, f) == getattr(per_model, f), f


def test_pooled_is_none_for_a_mode_with_no_entries():
    assert compute_pooled([_r("london", "backtest", 1.0)], "live") is None
    assert compute_pooled([], "backtest") is None


def test_pooled_open_only_sample_is_computable_as_none():
    """Entries logged but none closed: a group exists (logged>0) with no math."""
    g = compute_pooled([_r("london", "backtest", None)], "backtest")
    assert g is not None and g.logged == 1 and g.n == 0
    assert g.expectancy is None and g.sample_met is False
