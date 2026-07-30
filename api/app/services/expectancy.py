"""Pure, DB-agnostic expectancy math for the analytics API (Phase 5f).

This is the evidence-gated core of the proof-of-edge loop, kept pure (no DB, no
I/O) so it can be unit-tested against hand-built fixtures with known answers —
mirroring services/scheduler.py's no-DB tests. The router loads journal rows,
maps them to `TradeR`, and calls these functions.

Formula (canonical in concepts/mastery/README §Readiness-to-Live Gate +
concepts/aura/risk-management — REUSED, not reinvented):

    expectancy = (win% × avg win R) − (loss% × avg loss R)
    break-even win rate = 1 / (1 + R:R)

Win / loss / breakeven are classified by the SIGN of the realized `r_multiple`
(r>0 win, r<0 loss, r==0 breakeven), NOT by the `outcome` enum — this keeps the
math self-consistent (a positive R can never be miscounted as a loss) and makes
the expectancy identity exact:

    expectancy == mean(r_multiple)   over the closed sample

which the unit tests assert both ways. Only CLOSED trades (a non-null
`r_multiple`) enter the sample.
"""

from dataclasses import dataclass, replace

# The `entry_model` label of the POOLED group (Phase 6a). A stage exit bar is not
# per-model (unlike the gate), so `compute_pooled` reports one group across all
# models; the sentinel is not an `entry_model` enum label and never collides.
POOLED = "__all__"

# Reference sample size — the design Readiness Gate wants ≥50 backtested setups
# per model (concepts/mastery/README §Gate). Surfaced so an under-evidenced model
# reads as such (north star), but it is NOT the gate verdict (that is Phase 5g).
SAMPLE_TARGET = 50

# Fixed R histogram buckets, half-open [lo, hi). None lo/hi = open-ended tail.
_BUCKETS: list[tuple[str, float | None, float | None]] = [
    ("≤ -2R", None, -2.0),
    ("-2 to -1R", -2.0, -1.0),
    ("-1 to 0R", -1.0, 0.0),
    ("0 to 1R", 0.0, 1.0),
    ("1 to 2R", 1.0, 2.0),
    ("2 to 3R", 2.0, 3.0),
    ("≥ 3R", 3.0, None),
]


@dataclass(frozen=True)
class TradeR:
    """The only inputs expectancy needs from a journal row."""

    entry_model: str
    mode: str
    r_multiple: float | None
    rr_planned: float | None = None


@dataclass(frozen=True)
class Group:
    entry_model: str
    mode: str
    logged: int
    n: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float | None
    avg_win_r: float | None
    avg_loss_r: float | None
    expectancy: float | None
    avg_rr_planned: float | None
    break_even: float | None
    above_break_even: bool | None
    sample_target: int
    sample_met: bool


@dataclass(frozen=True)
class ModeStats:
    mode: str
    logged: int
    n: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float | None
    expectancy: float | None
    total_r: float | None


def _stats(closed: list[float]):
    """Core stats over a list of realized R (already filtered to closed trades).
    Returns (wins, losses, bes, win_rate, avg_win_r, avg_loss_r, expectancy)."""
    n = len(closed)
    if n == 0:
        return 0, 0, 0, None, None, None, None
    wins = [r for r in closed if r > 0]
    losses = [r for r in closed if r < 0]
    bes = [r for r in closed if r == 0]
    win_rate = len(wins) / n
    loss_rate = len(losses) / n
    avg_win_r = sum(wins) / len(wins) if wins else None
    avg_loss_r = abs(sum(losses) / len(losses)) if losses else None  # positive magnitude
    # Expectancy via the canonical formula (avg legs treated as 0 when the leg is
    # empty). This is algebraically identical to mean(closed); tests assert both.
    expectancy = win_rate * (avg_win_r or 0.0) - loss_rate * (avg_loss_r or 0.0)
    return (
        len(wins), len(losses), len(bes), win_rate, avg_win_r, avg_loss_r, expectancy,
    )


def _round(x: float | None, places: int) -> float | None:
    return None if x is None else round(x, places)


def compute_groups(trades: list[TradeR], sample_target: int = SAMPLE_TARGET) -> list[Group]:
    """Group by (entry_model, mode) and compute per-group expectancy. A group is
    emitted for any (model, mode) with ≥1 non-deleted entry; its stats cover the
    CLOSED subset only. Ordered by entry_model then mode (deterministic)."""
    buckets: dict[tuple[str, str], list[TradeR]] = {}
    for t in trades:
        buckets.setdefault((t.entry_model, t.mode), []).append(t)

    out: list[Group] = []
    for (model, mode), rows in sorted(buckets.items()):
        logged = len(rows)
        closed = [float(r.r_multiple) for r in rows if r.r_multiple is not None]
        wins, losses, bes, win_rate, avg_win_r, avg_loss_r, expectancy = _stats(closed)

        rrs = [float(r.rr_planned) for r in rows if r.rr_planned is not None and r.rr_planned > 0]
        avg_rr = sum(rrs) / len(rrs) if rrs else None
        break_even = 1.0 / (1.0 + avg_rr) if avg_rr else None
        above_be = (win_rate >= break_even) if (win_rate is not None and break_even is not None) else None

        out.append(Group(
            entry_model=model, mode=mode, logged=logged, n=len(closed),
            wins=wins, losses=losses, breakevens=bes,
            win_rate=_round(win_rate, 4),
            avg_win_r=_round(avg_win_r, 3),
            avg_loss_r=_round(avg_loss_r, 3),
            expectancy=_round(expectancy, 3),
            avg_rr_planned=_round(avg_rr, 3),
            break_even=_round(break_even, 4),
            above_break_even=above_be,
            sample_target=sample_target,
            sample_met=len(closed) >= sample_target,
        ))
    return out


def compute_pooled(
    trades: list[TradeR], mode: str, sample_target: int = SAMPLE_TARGET
) -> Group | None:
    """One POOLED `Group` across every model for `mode` — the stage-level view of
    the same evidence (Phase 6a: services/stages.py grades A4/M7/U4 on it).

    Deliberately implemented by DELEGATING to `compute_groups` over a re-labelled
    copy, so the sample / win-rate / expectancy / break-even math is literally the
    same code path (no second implementation to drift). Returns None when the mode
    has no entries at all. Backtest and live are never conflated: one mode per call.
    """
    relabelled = [replace(t, entry_model=POOLED) for t in trades if t.mode == mode]
    groups = compute_groups(relabelled, sample_target)
    return groups[0] if groups else None


def compute_mode_summaries(trades: list[TradeR]) -> list[ModeStats]:
    """Top-line per axis (backtest / live), all models pooled. Always returns a
    row for both modes (n=0 when empty) so the UI shows both axes side by side."""
    out: list[ModeStats] = []
    for mode in ("backtest", "live"):
        rows = [t for t in trades if t.mode == mode]
        closed = [float(t.r_multiple) for t in rows if t.r_multiple is not None]
        wins, losses, bes, win_rate, _awr, _alr, expectancy = _stats(closed)
        out.append(ModeStats(
            mode=mode, logged=len(rows), n=len(closed),
            wins=wins, losses=losses, breakevens=bes,
            win_rate=_round(win_rate, 4),
            expectancy=_round(expectancy, 3),
            total_r=_round(sum(closed), 2) if closed else None,
        ))
    return out


def compute_r_distribution(trades: list[TradeR]) -> list[dict]:
    """R histogram over closed trades, split backtest vs live per bucket."""
    counts = {label: {"backtest": 0, "live": 0} for label, _, _ in _BUCKETS}
    for t in trades:
        if t.r_multiple is None or t.mode not in ("backtest", "live"):
            continue
        r = float(t.r_multiple)
        for label, lo, hi in _BUCKETS:
            if (lo is None or r >= lo) and (hi is None or r < hi):
                counts[label][t.mode] += 1
                break
    return [
        {"label": label, "lo": lo, "hi": hi,
         "backtest": counts[label]["backtest"], "live": counts[label]["live"]}
        for label, lo, hi in _BUCKETS
    ]
