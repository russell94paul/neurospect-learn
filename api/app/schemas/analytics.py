"""Pydantic schemas for the expectancy / analytics API (Phase 5f).

The empirical proof-of-edge view: journal entries grouped by `entry_model` ×
`mode`, with per-group expectancy computed in R. The formula is canonical in
concepts/mastery/README §Readiness-to-Live Gate + concepts/aura/risk-management
and REUSED here (not reinvented):

    expectancy = (win% × avg win R) − (loss% × avg loss R)
    break-even win rate = 1 / (1 + R:R)

Computed ONLY over CLOSED trades (a non-null `r_multiple`). This is the VIEW the
5g Readiness Gate will read; 5f surfaces the numbers + their true sample size and
does NOT emit any "cleared to live" verdict (that is 5g's job). The pure math
lives in app/services/expectancy.py.
"""

from pydantic import BaseModel


class ExpectancyGroup(BaseModel):
    """One `entry_model` × `mode` cell. `logged` counts every non-deleted entry;
    `n` counts the CLOSED subset (with `r_multiple`) that expectancy is computed
    over — a small `n` is a visibly under-evidenced model (north star)."""

    entry_model: str
    mode: str
    logged: int          # total non-deleted entries in the group
    n: int               # closed trades (non-null r_multiple) — the sample size
    wins: int            # r_multiple > 0
    losses: int          # r_multiple < 0
    breakevens: int      # r_multiple == 0
    win_rate: float | None       # wins / n, a FRACTION 0–1 (UI formats as %)
    avg_win_r: float | None      # mean R of winners (positive)
    avg_loss_r: float | None     # mean |R| of losers (positive magnitude)
    expectancy: float | None     # R per trade — the proof-of-edge number
    avg_rr_planned: float | None # mean planned R:R (over entries carrying one)
    break_even: float | None     # required win rate = 1/(1+avg R:R), fraction 0–1
    above_break_even: bool | None  # win_rate ≥ break_even (None if either unknown)
    sample_target: int   # REFERENCE sample (design gate ≥50 setups) — NOT the 5g verdict
    sample_met: bool     # n ≥ sample_target (reference only; the gate is 5g)


class ExpectancyOut(BaseModel):
    """All non-empty model×mode groups, plus the reference sample target used."""

    sample_target: int
    groups: list[ExpectancyGroup]


class ModeSummary(BaseModel):
    """Top-line for one axis (backtest / live). `expectancy` here is the overall
    mean R across all that mode's closed trades (all models pooled)."""

    mode: str
    logged: int
    n: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float | None
    expectancy: float | None
    total_r: float | None  # sum of r_multiple across the mode's closed trades


class SummaryOut(BaseModel):
    modes: list[ModeSummary]


class RDistributionBucket(BaseModel):
    """One R histogram bucket, split by mode so backtest vs live never conflate."""

    label: str
    lo: float | None  # half-open [lo, hi); null lo/hi = open-ended
    hi: float | None
    backtest: int
    live: int


class RDistributionOut(BaseModel):
    buckets: list[RDistributionBucket]
