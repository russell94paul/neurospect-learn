#!/usr/bin/env python
"""
Aura Sequential-SMT setup engine  —  Phase S1c.

Computes Aura setups from REAL exported bars and logs them, with rejections, in an
auditable form: every line carries the rule ID, the computed value, and the bar/time
it came from, so Paul can check it against the Tradezella chart.

    python api/scripts/aura_setup_engine.py \
        --bars api/docs/evidence/s1c/bars/tradezella-831607-export.json \
        --from 2025-05-01 --to 2025-05-30 \
        --out api/docs/evidence/s1c

WHAT THIS IS NOT
    - It is not a chart read. Nothing here is perception; it is arithmetic on the
      OHLC the chart itself exported.
    - It is not Paul's practice. Machine-found setups are quarantined (see the
      QUARANTINE banner in the report) and must never touch the evidence layer.
    - It does not resolve judgement rules. R9 / R8 / R31 surface as UNRESOLVED or
      as a reported branch, never as a silent pick.

Source of the rules: neurospect-wiki concepts/mastery/aura/rules.md (canonical).
"""

from __future__ import annotations

import argparse
import json
import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────────────────────
# DECLARED CONSTANTS — every threshold here is printed in the run header.
# An unstated threshold is an invented rule wearing a fact's clothes (E6).
# ─────────────────────────────────────────────────────────────────────────────

PRIMARY = "NQ"

# R15/R17. NQ/ES/YM are the working triad. CHFUSD stands in for the Aura Asset
# (6S) and is admissible INTRADAY ONLY — its daily bars bucket on a different
# exchange day (Etc/UTC vs America/Chicago), so it reproduces the exact defect
# R17 rejected DXY for. The engine refuses it at daily rather than silently
# producing a signal.
TRIAD_LEGS = ["ES", "YM"]
AURA_ASSET = "CHFUSD"
AURA_ASSET_MIN_RES_SEC = 60      # admissible at any intraday resolution …
AURA_ASSET_MAX_RES_SEC = 4 * 3600  # … up to and including 4H. Never daily/weekly.

# SMT noise floor, in TICKS of each instrument's own measured tick size.
# Why this exists: on 2026-08-13 a naive "did it exceed the level?" test was found
# to manufacture phantom SMT out of zero-margin near-misses — the level matched
# exactly and not exceeded by a single tick — on the REAL triad, not just on MNQ.
# Both sides must clear the floor: the taking leg must EXCEED by more than the
# floor, and the diverging leg must MISS by more than the floor.
NOISE_FLOOR_TICKS = 2.0

# R1/R2 pivots are 3-candle. Forward window for "was the level taken?", in bars,
# per cycle. A too-coarse window hides divergence (measured: 20 bars showed 0/53
# NQ-vs-MNQ where 3 bars showed 1/56).
FORWARD_BARS = {86400: 5, 14400: 6, 3600: 8, 900: 8, 300: 8}

# The HTF→LTF cascade actually available in this export (R27).
CYCLE_FRAMING = "D"       # range + HTF SMT
CYCLE_CONFIRM = "240"     # 4H — the adjacent cycle R18 nests into
CYCLE_SESSION = "15"      # session-cycle SMT (R30's preference)
CYCLE_ENTRY = "5"         # R30: 5m preferred over 3m

RES_SECONDS = {"D": 86400, "240": 14400, "60": 3600, "15": 900, "5": 300, "1": 60}

# R4/R7 range framing. R7 anchors a new range at a HTF Sequential SMT plus an
# expansive move away, and says to keep following THAT range until an opposing or
# same-cycle SMT forms. So the expansive move is searched in a window anchored on
# the driving SMT, not over an arbitrary trailing window — framing over 60 trailing
# daily bars produced a 3,584-point "range" from five weeks earlier that price had
# long since closed through (found and fixed 2026-08-13).
FRAMING_LOOKBACK_BARS = 60
RANGE_ANCHOR_PRE_BARS = 10    # framing bars to look back BEFORE the driving SMT pivot

# R33/R34: a stop this large relative to the range means the entry timeframe and the
# invalidation level are mismatched. R34's answer is a correlated leg with a tighter
# equivalent gap. Reported as a branch, never auto-substituted.
STOP_OVERSIZE_FRACTION = 0.25

# Entry scan window, ET. The model is NY-session shaped and R31 anchors on the 9:30
# open, but R31 also explicitly discusses PRE-9:30 setups — so the window opens at
# 08:00 to keep that branch live and reportable rather than defining it away.
ENTRY_WINDOW_ET = ((8, 0), (16, 0))

# R9 is explicitly judgement ("if the range isn't obvious, zoom out"; "overlapping
# ranges are acceptable — do not force one"). When the top-2 candidate expansive
# moves are within this fraction of each other, the engine refuses to pick and
# emits UNRESOLVED with both candidates.
R9_AMBIGUITY_TOLERANCE = 0.15

# R31 is soft ("prefer waiting for the 9:30 NY open" — stated for struggling
# traders in particular). The engine reports the branch; it never rejects on it.
RTH_OPEN_ET = (9, 30)

# HARD GATES — declared, not inferred. A candidate failing any of these is logged
# as a REJECTION naming the failing rule, and is still a record worth keeping (R51).
HARD_GATES = [
    "R3   swing must be SMT-qualified across the triad",
    "R18  SMT must nest across >=2 adjacent cycles (or R24 Sequential Skip)",
    "R6   the framed range must still be LIVE - a candle CLOSE beyond a boundary kills it",
    "R7   the driving SMT must still be current - a later same-cycle or opposing SMT retires it",
    "R30  a 5m iFVG must exist in the bias direction",
    "R35  the target must lie BEYOND entry in the bias direction",
    "R29  invalidation must be definable (a stop level must exist)",
]

# SOFT / REPORTED — branches, never gates.
SOFT_BRANCHES = [
    "R5/R32  entry in discount (long) / premium (short) — reported, not enforced",
    "R31     pre-09:30 ET entry — reported as a branch (soft rule)",
    "R9      ambiguous range — emitted as UNRESOLVED, never silently picked",
]


# ─────────────────────────────────────────────────────────────────────────────
# Bars
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Series:
    symbol: str
    res: str
    times: list[int]
    o: list[float]
    h: list[float]
    l: list[float]
    c: list[float]
    tick: float = 0.0
    _index: dict[int, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.times)

    def at(self, t: int) -> int | None:
        """Index of the bar stamped exactly t, or None. Timestamp join (never index)."""
        return self._index.get(t)

    def slice_idx(self, t_from: int, t_to: int) -> tuple[int, int]:
        """Indices [lo, hi) of bars with t_from <= time <= t_to."""
        return bisect_left(self.times, t_from), bisect_right(self.times, t_to)


def load_bars(path: Path) -> tuple[dict[str, dict[str, Series]], dict]:
    raw = json.loads(path.read_text())
    out: dict[str, dict[str, Series]] = {}
    for res, syms in raw["resolutions"].items():
        out[res] = {}
        for sym, payload in syms.items():
            rows = payload["rows"]
            rows.sort(key=lambda r: r[0])
            s = Series(
                symbol=sym,
                res=res,
                times=[int(r[0]) for r in rows],
                o=[float(r[1]) for r in rows],
                h=[float(r[2]) for r in rows],
                l=[float(r[3]) for r in rows],
                c=[float(r[4]) for r in rows],
            )
            s._index = {t: i for i, t in enumerate(s.times)}
            s.tick = measure_tick(s)
            out[res][sym] = s
    meta = {k: v for k, v in raw.items() if k != "resolutions"}
    return out, meta


def measure_tick(s: Series, sample: int = 4000) -> float:
    """MEASURED, not assumed: the smallest non-zero price increment observed.

    Tick sizes differ across the legs (NQ/ES 0.25, YM 1.0, CHFUSD ~0.00001), so a
    raw price comparison is not apples-to-apples. Deriving it from the data means
    the noise floor cannot be wrong because someone mis-remembered a contract spec.

    ⚠ Taking the plain MINIMUM non-zero difference does not work and is not a safe
    default: on CHFUSD it returned 5.98e-09 — IEEE-754 representation noise between
    two prices that are equal in intent — which drove that leg's noise floor to
    effectively zero and reintroduced the phantom-SMT bug the floor exists to
    prevent, on the one leg whose ticks are too small to eyeball. So a candidate
    increment must RECUR before it is believed.
    """
    vals: list[float] = []
    n = min(len(s), sample)
    for i in range(n):
        vals.extend((s.o[i], s.h[i], s.l[i], s.c[i]))
    uniq = sorted(set(vals))
    if len(uniq) < 3:
        return 0.0

    counts: dict[str, int] = {}
    for a, b in zip(uniq, uniq[1:]):
        d = b - a
        if d > 1e-12:
            key = f"{d:.6g}"          # collapse float dust onto a canonical value
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return 0.0

    total = sum(counts.values())
    min_support = max(3, int(total * 0.005))
    recurring = [float(k) for k, v in counts.items() if v >= min_support]
    if not recurring:
        recurring = [float(max(counts.items(), key=lambda kv: kv[1])[0])]
    return min(recurring)


def floor_for(s: Series) -> float:
    return s.tick * NOISE_FLOOR_TICKS


# ─────────────────────────────────────────────────────────────────────────────
# R1 / R2 — swing points (3-candle pivots, fractal across all timeframes)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Pivot:
    idx: int
    time: int
    price: float
    side: str        # "high" | "low"
    known_at: int    # a pivot needs bar i+1, so it is only knowable at i+1's close


def find_pivots(s: Series, lo: int = 0, hi: int | None = None) -> list[Pivot]:
    hi = len(s) if hi is None else hi
    out: list[Pivot] = []
    for i in range(max(lo, 1), min(hi, len(s) - 1)):
        if s.h[i] > s.h[i - 1] and s.h[i] > s.h[i + 1]:
            out.append(Pivot(i, s.times[i], s.h[i], "high", s.times[i + 1]))
        if s.l[i] < s.l[i - 1] and s.l[i] < s.l[i + 1]:
            out.append(Pivot(i, s.times[i], s.l[i], "low", s.times[i + 1]))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# R3 / R18 / R20 — Sequential SMT across the triad, with a noise floor and a margin
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LegRead:
    symbol: str
    verdict: str          # TOOK | DID-NOT-TAKE | NOT-VISIBLE | REFUSED
    level: float | None = None
    extreme: float | None = None
    margin: float | None = None    # + = exceeded (TOOK) / missed by (DID-NOT-TAKE)
    margin_ticks: float | None = None
    note: str = ""


@dataclass
class SmtEvent:
    cycle: str
    side: str             # "high" (bearish SMT) | "low" (bullish SMT)
    bias: str             # SHORT | LONG
    pivot_time: int
    level: float
    taken_time: int
    primary_margin: float
    primary_margin_ticks: float
    legs: list[LegRead]
    diverging: list[str]
    known_at: int         # the full forward window must elapse to know a leg did NOT take


def admissible_legs(res: str) -> tuple[list[str], list[str]]:
    """Returns (admitted, refused). Encodes the CHFUSD daily refusal as a rule."""
    rs = RES_SECONDS[res]
    admitted = list(TRIAD_LEGS)
    refused = []
    if AURA_ASSET_MIN_RES_SEC <= rs <= AURA_ASSET_MAX_RES_SEC:
        admitted.append(AURA_ASSET)
    else:
        refused.append(AURA_ASSET)
    return admitted, refused


def find_smt(
    series: dict[str, Series],
    res: str,
    side: str,
    t_from: int,
    t_to: int,
    as_of: int,
) -> tuple[list[SmtEvent], list[str]]:
    """Find SMT-qualified pivots (R3) on the primary leg between t_from and t_to.

    Only events fully knowable by `as_of` are returned — no lookahead.
    """
    prim = series[res][PRIMARY]
    rs = RES_SECONDS[res]
    fwd = FORWARD_BARS[rs]
    admitted, refused = admissible_legs(res)
    notes = [
        f"R17  {AURA_ASSET} REFUSED at {res} — cycles do not correspond "
        f"(different exchange day bucketing); not treated as a leg"
        for _ in refused
    ]

    lo, hi = prim.slice_idx(t_from, t_to)
    events: list[SmtEvent] = []

    for p in find_pivots(prim, max(lo - 1, 0), min(hi + 1, len(prim))):
        if p.side != side:
            continue

        # Forward window on the primary leg.
        w_lo = p.idx + 1
        w_hi = min(p.idx + 1 + fwd, len(prim))
        if w_hi <= w_lo:
            continue

        # ⚠ known_at MUST come from real bar timestamps, never calendar arithmetic.
        # `p.time + fwd * rs` silently ignores weekends and holidays: for the pivot
        # of 2025-05-20 it returned 05-25, while the 5th forward DAILY BAR is
        # 05-28 09:30 — so the engine treated a signal as pre-session knowledge on
        # the very session that produced it. The last bar of the window must also
        # CLOSE before the window's verdict is final, hence the trailing + rs.
        known_at = prim.times[w_hi - 1] + rs
        if known_at > as_of:
            continue  # not yet knowable — would be lookahead

        pf = floor_for(prim)
        if side == "high":
            extreme = max(prim.h[w_lo:w_hi])
            took = extreme > p.price + pf
            margin = extreme - p.price
        else:
            extreme = min(prim.l[w_lo:w_hi])
            took = extreme < p.price - pf
            margin = p.price - extreme
        if not took:
            continue  # the primary never took its own level — no SMT to read

        taken_time = prim.times[w_lo + (
            (prim.h[w_lo:w_hi].index(extreme)) if side == "high"
            else (prim.l[w_lo:w_hi].index(extreme))
        )]

        # The three pivot bars define the level window each leg is measured on.
        pivot_ts = [prim.times[j] for j in (p.idx - 1, p.idx, p.idx + 1)
                    if 0 <= j < len(prim)]
        fwd_ts = prim.times[w_lo:w_hi]

        legs: list[LegRead] = []
        for leg_sym in admitted:
            leg = series[res].get(leg_sym)
            if leg is None:
                legs.append(LegRead(leg_sym, "NOT-VISIBLE", note="symbol absent at this resolution"))
                continue
            lvl_idx = [leg.at(t) for t in pivot_ts]
            lvl_idx = [i for i in lvl_idx if i is not None]
            w_idx = [leg.at(t) for t in fwd_ts]
            w_idx = [i for i in w_idx if i is not None]
            # NOT-VISIBLE is a distinct verdict from DID-NOT-TAKE. Collapsing them
            # would turn a measurement gap into a claim about the market.
            if not lvl_idx or not w_idx:
                legs.append(LegRead(
                    leg_sym, "NOT-VISIBLE",
                    note=f"no timestamp-matched bars ({len(lvl_idx)} level / {len(w_idx)} window)",
                ))
                continue
            lf = floor_for(leg)
            if side == "high":
                lvl = max(leg.h[i] for i in lvl_idx)
                ext = max(leg.h[i] for i in w_idx)
                if ext > lvl + lf:
                    v, m = "TOOK", ext - lvl
                elif ext < lvl - lf:
                    v, m = "DID-NOT-TAKE", lvl - ext
                else:
                    v, m = "WITHIN-NOISE", abs(lvl - ext)
            else:
                lvl = min(leg.l[i] for i in lvl_idx)
                ext = min(leg.l[i] for i in w_idx)
                if ext < lvl - lf:
                    v, m = "TOOK", lvl - ext
                elif ext > lvl + lf:
                    v, m = "DID-NOT-TAKE", ext - lvl
                else:
                    v, m = "WITHIN-NOISE", abs(lvl - ext)
            legs.append(LegRead(
                leg_sym, v, level=lvl, extreme=ext, margin=m,
                margin_ticks=(m / leg.tick if leg.tick else None),
            ))

        diverging = [x.symbol for x in legs if x.verdict == "DID-NOT-TAKE"]
        if not diverging:
            continue  # correlation held — no divergence, no signal

        events.append(SmtEvent(
            cycle=res, side=side,
            bias=("SHORT" if side == "high" else "LONG"),
            pivot_time=p.time, level=p.price, taken_time=taken_time,
            primary_margin=margin,
            primary_margin_ticks=(margin / prim.tick if prim.tick else 0.0),
            legs=legs, diverging=diverging, known_at=known_at,
        ))
    return events, list(dict.fromkeys(notes))


# ─────────────────────────────────────────────────────────────────────────────
# R4 / R9 — the range, by the expansive-move method (never time-based)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Range:
    low: float
    high: float
    low_time: int
    high_time: int
    move_from: int
    move_to: int
    size: float
    unresolved: str | None = None
    runner_up: str | None = None
    broken_by: tuple[str, float, int] | None = None   # R6: close beyond a boundary
    alive_alternative: str | None = None              # R9: a smaller candidate still live

    def position(self, price: float) -> float:
        if self.high == self.low:
            return 0.5
        return (price - self.low) / (self.high - self.low)

    def zone(self, price: float) -> str:
        p = self.position(price)
        if abs(p - 0.5) < 1e-9:
            return "EQUILIBRIUM"
        return "DISCOUNT" if p < 0.5 else "PREMIUM"


def frame_range(s: Series, as_of: int, anchor_time: int | None = None) -> Range | None:
    """R4: the LARGEST expansive move between two swing points IS the range.

    R7: when an anchor (the driving Sequential SMT) is given, the move is searched
    from RANGE_ANCHOR_PRE_BARS before that pivot — a range is anchored at the SMT,
    not at an arbitrary trailing window.

    R9 is judgement and is not resolved here: if the top two candidates are within
    R9_AMBIGUITY_TOLERANCE of each other the range is emitted UNRESOLVED.
    """
    hi = bisect_right(s.times, as_of)
    if anchor_time is not None:
        a_idx = bisect_left(s.times, anchor_time)
        lo = max(0, a_idx - RANGE_ANCHOR_PRE_BARS)
    else:
        lo = max(0, hi - FRAMING_LOOKBACK_BARS)
    pivots = [p for p in find_pivots(s, lo, hi) if p.known_at <= as_of]
    if len(pivots) < 2:
        return None
    pivots.sort(key=lambda p: p.time)

    cands: list[tuple[float, Pivot, Pivot]] = []
    for a, b in zip(pivots, pivots[1:]):
        if a.side == b.side:
            continue
        cands.append((abs(b.price - a.price), a, b))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])

    size, a, b = cands[0]
    unresolved = runner_up = None
    alive_alt = None
    if len(cands) > 1 and cands[1][0] >= size * (1 - R9_AMBIGUITY_TOLERANCE):
        s2, a2, b2 = cands[1]
        unresolved = (
            "R9 - two candidate ranges within "
            f"{R9_AMBIGUITY_TOLERANCE:.0%} ({size:.2f} vs {s2:.2f}); "
            "R9 says overlapping/ambiguous ranges are acceptable - do not force one"
        )
        runner_up = (
            f"{min(a2.price, b2.price):.2f}-{max(a2.price, b2.price):.2f} "
            f"(move {fmt_et(a2.time)}->{fmt_et(b2.time)})"
        )

    low_p, high_p = (a, b) if a.price < b.price else (b, a)
    rng = Range(
        low=low_p.price, high=high_p.price,
        low_time=low_p.time, high_time=high_p.time,
        move_from=a.time, move_to=b.time, size=size,
        unresolved=unresolved, runner_up=runner_up,
    )
    check_range_alive(rng, s, as_of)

    # R9 again: if the chosen (largest) range is dead but a smaller candidate is
    # still live, that is a judgement call between overlapping ranges — surface it,
    # never silently switch to the one that yields a trade.
    if rng.broken_by:
        for s2, a2, b2 in cands[1:]:
            alt = Range(
                low=min(a2.price, b2.price), high=max(a2.price, b2.price),
                low_time=a2.time, high_time=b2.time,
                move_from=a2.time, move_to=b2.time, size=s2,
            )
            check_range_alive(alt, s, as_of)
            if not alt.broken_by:
                alive_alt = (f"{alt.low:,.2f}-{alt.high:,.2f} ({s2:,.2f} pts, move "
                             f"{fmt_et(a2.time)} -> {fmt_et(b2.time)})")
                break
        rng.alive_alternative = alive_alt
    return rng


def check_range_alive(rng: Range, s: Series, as_of: int) -> None:
    """R6: a range is invalidated ONLY by a candle CLOSE beyond its boundary — a wick
    through is not a break.

    Without this the engine happily measures entries at 1.22 of a range that price
    closed through five weeks earlier, and R5/R32/R35 all become fiction.
    """
    start = bisect_right(s.times, max(rng.move_to, rng.high_time, rng.low_time))
    end = bisect_right(s.times, as_of)
    for i in range(start, end):
        if s.c[i] > rng.high:
            rng.broken_by = ("close above", s.c[i], s.times[i])
            return
        if s.c[i] < rng.low:
            rng.broken_by = ("close below", s.c[i], s.times[i])
            return


# ─────────────────────────────────────────────────────────────────────────────
# R11 / R12 / R13 — gaps and the liquidity nested inside them
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Gap:
    kind: str            # FVG | iFVG | NDOG | NWOG
    direction: str       # bullish | bearish (the direction it supports AFTER inversion)
    low: float
    high: float
    formed_time: int
    inverted_time: int | None = None
    liquidity: float | None = None      # R12: the swing level nested INSIDE the gap
    liquidity_time: int | None = None
    liquidity_note: str = ""


def find_fvgs(s: Series, lo: int, hi: int) -> list[Gap]:
    """R11: only FVG / iFVG / NWOG / NDOG. No BPR, no volume-imbalance vocabulary."""
    out: list[Gap] = []
    for i in range(max(lo, 1), min(hi, len(s) - 1)):
        if s.h[i - 1] < s.l[i + 1]:      # bullish FVG
            out.append(Gap("FVG", "bullish", s.h[i - 1], s.l[i + 1], s.times[i]))
        if s.l[i - 1] > s.h[i + 1]:      # bearish FVG
            out.append(Gap("FVG", "bearish", s.h[i + 1], s.l[i - 1], s.times[i]))
    return out


def invert_gaps(s: Series, gaps: list[Gap], as_of: int) -> list[Gap]:
    """An FVG becomes an iFVG when a later bar CLOSES beyond it (R6's close rule).

    A bearish FVG closed ABOVE becomes bullish support; a bullish FVG closed BELOW
    becomes bearish resistance. R30's preferred entry is the resulting iFVG.
    """
    out: list[Gap] = []
    for g in gaps:
        start = bisect_right(s.times, g.formed_time)
        end = bisect_right(s.times, as_of)
        inv_t = None
        for i in range(start, end):
            if g.direction == "bearish" and s.c[i] > g.high:
                inv_t = s.times[i]
                break
            if g.direction == "bullish" and s.c[i] < g.low:
                inv_t = s.times[i]
                break
        if inv_t is not None:
            out.append(Gap(
                "iFVG",
                "bullish" if g.direction == "bearish" else "bearish",
                g.low, g.high, g.formed_time, inverted_time=inv_t,
            ))
    return out


def attach_liquidity(g: Gap, s: Series, as_of: int) -> None:
    """R12: the precise target is the swing high/low nested INSIDE the gap, not the
    gap boundary. R13: if none is visible, look left / zoom in — surfaced, not faked.
    """
    hi = bisect_right(s.times, as_of)
    inside = [p for p in find_pivots(s, 0, hi)
              if g.low <= p.price <= g.high and p.known_at <= as_of]
    if inside:
        p = max(inside, key=lambda x: x.time)
        g.liquidity, g.liquidity_time = p.price, p.time
    else:
        g.liquidity_note = ("R13 - no internal liquidity visible at this resolution; "
                            "look left for a resting untaken level, or zoom in")


# ─────────────────────────────────────────────────────────────────────────────
# Setup assembly
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Line:
    rule: str
    text: str


@dataclass
class Record:
    day: str
    kind: str                      # SETUP | REJECTION
    bias: str | None = None
    lines: list[Line] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    branches: list[str] = field(default_factory=list)
    failing_rule: str | None = None


def fmt_et(ts: int) -> str:
    return datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d %H:%M ET")


def fmt_hm(ts: int, day: str | None = None) -> str:
    """Bare HH:MM only when the stamp falls on the record's own ET date.

    Otherwise the date is carried. A gap reported as "formed 19:30 ... retested
    09:50" reads as though the retest preceded the formation; it did not — the gap
    formed the previous evening. An ambiguous timestamp is an uncheckable record.
    """
    d = datetime.fromtimestamp(ts, ET)
    if day is not None and d.strftime("%Y-%m-%d") == day:
        return d.strftime("%H:%M")
    return d.strftime("%m-%d %H:%M")


def et_day_bounds(day: datetime) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, 0, 0, tzinfo=ET)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def analyse_day(series, day: datetime) -> Record:
    day_str = day.strftime("%Y-%m-%d")
    t0, t1 = et_day_bounds(day)
    rec = Record(day=day_str, kind="REJECTION")

    entry_s = series[CYCLE_ENTRY].get(PRIMARY)
    if entry_s is None:
        rec.failing_rule = "DATA"
        rec.lines.append(Line("DATA", f"no {PRIMARY} series at {CYCLE_ENTRY}m"))
        return rec

    e_lo, e_hi = entry_s.slice_idx(t0, t1 - 1)
    if e_hi - e_lo < 12:
        rec.failing_rule = "DATA"
        rec.lines.append(Line(
            "DATA", f"only {e_hi - e_lo} bars of {CYCLE_ENTRY}m data in this ET day "
                    "- not a tradeable session in this export (holiday, weekend, or "
                    "outside the loaded window)"))
        return rec

    # ── Framing, established PRE-SESSION (R26): everything below uses only data
    #    stamped before the session day opens. No lookahead.
    frame = series[CYCLE_FRAMING].get(PRIMARY)
    if frame is None:
        rec.failing_rule = "DATA"
        rec.lines.append(Line("DATA", "no daily series for the framing cycle"))
        return rec

    # ── R3: SMT on the framing cycle FIRST — it is what anchors the range (R7).
    htf_events, notes = [], []
    for side in ("high", "low"):
        ev, nt = find_smt(series, CYCLE_FRAMING, side,
                          t0 - 86400 * FRAMING_LOOKBACK_BARS, t0, as_of=t0)
        htf_events += ev
        notes += nt
    for n in dict.fromkeys(notes):
        rec.branches.append(n)

    if not htf_events:
        rec.failing_rule = "R3"
        rec.lines.append(Line("R3", "no SMT-qualified swing on the daily cycle in the "
                                    f"{FRAMING_LOOKBACK_BARS}-bar lookback - unqualified "
                                    "swings are provisional and not tradeable"))
        return rec

    # R7/R23: read the CURRENT state. The most recently knowable same-cycle SMT
    # retires every earlier one — a stale signal is not a signal.
    htf_events.sort(key=lambda e: (e.known_at, e.pivot_time))
    htf = htf_events[-1]
    rec.bias = htf.bias
    superseded = len([e for e in htf_events if e.known_at < htf.known_at])
    age_days = (t0 - htf.known_at) / 86400.0

    # ── R4/R7: frame the range ANCHORED on that SMT, then R6-validate it.
    rng = frame_range(frame, t0, anchor_time=htf.pivot_time)
    if rng is None:
        rec.failing_rule = "R4"
        rec.lines.append(Line("R4", "no expansive move framable from the daily cycle"))
        return rec

    rec.lines.append(Line("R4", f"range {rng.low:,.2f}-{rng.high:,.2f}  "
                                f"(expansive move {fmt_et(rng.move_from)} -> {fmt_et(rng.move_to)}, "
                                f"{rng.size:,.2f} pts)"))
    if rng.unresolved:
        rec.unresolved.append(rng.unresolved + f"  [runner-up: {rng.runner_up}]")

    if rng.broken_by:
        how, px, when = rng.broken_by
        rec.failing_rule = "R6"
        rec.lines.append(Line("R6", f"range INVALIDATED - candle {how} the boundary at "
                                    f"{px:,.2f} on {fmt_et(when)}. R6: only a close beyond "
                                    "a boundary breaks a range, and this one closed. R7: "
                                    "wait for the next Sequential SMT to anchor a new range"))
        if rng.alive_alternative:
            rec.unresolved.append(
                "R9 - the largest expansive move is dead but a smaller candidate is still "
                f"live: {rng.alive_alternative}. R9 says overlapping ranges are acceptable "
                "and must not be forced; the engine will NOT switch to the one that "
                "happens to yield a trade. Zoom out and decide by hand")
        return rec
    legtxt = "  ".join(
        f"{x.symbol}:{x.verdict}"
        + (f"({x.margin_ticks:+.1f}t)" if x.margin_ticks is not None else "")
        for x in htf.legs
    )
    rec.lines.append(Line("R3", f"SMT-qualified {htf.side} {htf.level:,.2f} @ "
                                f"{fmt_et(htf.pivot_time)} - {PRIMARY} took it "
                                f"{fmt_hm(htf.taken_time, day_str)} by "
                                f"{htf.primary_margin_ticks:.1f} ticks; {legtxt}"))
    rec.lines.append(Line("R18", f"daily-cycle SMT diverging on {', '.join(htf.diverging)} "
                                 f"-> bias {htf.bias}  (knowable {fmt_et(htf.known_at)}, "
                                 f"age {age_days:.1f}d, {superseded} earlier same-cycle "
                                 "SMT(s) retired per R7)"))

    # Nesting into the adjacent (4H) cycle — this is what makes it SEQUENTIAL.
    conf, _ = find_smt(series, CYCLE_CONFIRM, htf.side,
                       htf.pivot_time, t0, as_of=t0)
    seq_kind = None
    conf_ev = None
    if conf:
        c = conf_ev = conf[-1]
        seq_kind = "NESTED"
        rec.lines.append(Line("R18", f"nested {CYCLE_CONFIRM}m SMT @ {fmt_et(c.pivot_time)} "
                                     f"level {c.level:,.2f}, diverging on "
                                     f"{', '.join(c.diverging)} - adjacent cycles agree"))
    else:
        skip, _ = find_smt(series, CYCLE_SESSION, htf.side, htf.pivot_time, t0, as_of=t0)
        if skip:
            seq_kind = "SKIP"
            c = conf_ev = skip[-1]
            rec.lines.append(Line("R24", f"Sequential SKIP - {CYCLE_CONFIRM}m did NOT confirm, "
                                         f"{CYCLE_SESSION}m did @ {fmt_et(c.pivot_time)} "
                                         f"(diverging on {', '.join(c.diverging)})"))
    if seq_kind is None:
        rec.failing_rule = "R18"
        rec.lines.append(Line("R18", f"daily SMT present but NOT sequential - no {CYCLE_CONFIRM}m "
                                     f"confirmation and no {CYCLE_SESSION}m skip. R18 requires "
                                     "nesting across >=2 adjacent cycles"))
        return rec

    # ── R30: the 5m iFVG entry, scanned forward through the declared entry window.
    (wh0, wm0), (wh1, wm1) = ENTRY_WINDOW_ET
    win_lo = int(datetime(day.year, day.month, day.day, wh0, wm0, tzinfo=ET).timestamp())
    win_hi = int(datetime(day.year, day.month, day.day, wh1, wm1, tzinfo=ET).timestamp())
    fvgs = find_fvgs(entry_s, max(e_lo - 60, 0), e_hi)
    want = "bullish" if htf.bias == "LONG" else "bearish"
    ifvgs = [g for g in invert_gaps(entry_s, fvgs, t1 - 1)
             if g.direction == want and g.inverted_time is not None]
    if not ifvgs:
        rec.failing_rule = "R30"
        rec.lines.append(Line("R30", f"no {want} 5m iFVG formed in the session - "
                                     "the preferred entry never presented"))
        return rec

    # First retest of an inverted zone after inversion = the entry trigger.
    entry = None
    for g in sorted(ifvgs, key=lambda x: x.inverted_time or 0):
        start = bisect_right(entry_s.times, g.inverted_time)
        for i in range(start, e_hi):
            if not (win_lo <= entry_s.times[i] <= win_hi):
                continue
            touched = (g.low <= entry_s.l[i] <= g.high) or (g.low <= entry_s.h[i] <= g.high) \
                      or (entry_s.l[i] < g.low and entry_s.h[i] > g.high)
            if touched:
                entry = (g, i)
                break
        if entry:
            break
    if entry is None:
        rec.failing_rule = "R30"
        rec.lines.append(Line("R30", f"{len(ifvgs)} {want} 5m iFVG(s) formed but none was "
                                     f"retested inside the {wh0:02d}:{wm0:02d}-{wh1:02d}:{wm1:02d} ET "
                                     "entry window - no entry trigger"))
        return rec

    gap, ei = entry
    attach_liquidity(gap, entry_s, entry_s.times[ei])
    entry_px = gap.high if htf.bias == "LONG" else gap.low
    entry_t = entry_s.times[ei]

    # ── R33: stop at the level whose respect would invalidate the trade — "the
    # high/low of the qualifying daily-cycle / 4H SMT". Prefer the 4H qualifier when
    # the nesting supplied one: a daily sweep extreme is the correct level for a
    # daily-cycle entry and a wildly wrong one for a 5m entry.
    qual = conf[-1] if conf else htf
    sweep_ext = (qual.level - qual.primary_margin) if htf.bias == "LONG" \
        else (qual.level + qual.primary_margin)
    stop_px = sweep_ext
    risk = (entry_px - stop_px) if htf.bias == "LONG" else (stop_px - entry_px)
    if risk <= 0:
        rec.failing_rule = "R29"
        rec.lines.append(Line("R29", f"invalidation level {stop_px:,.2f} is on the wrong side "
                                     f"of entry {entry_px:,.2f} for a {htf.bias} - no definable "
                                     "stop, so there is no trade (R29 requires knowing what "
                                     "invalidates the idea)"))
        return rec

    # ── R35: target = the extreme of the timeframe being played. It must lie BEYOND
    # entry in the bias direction; an abs() here previously rendered a target the
    # trade had already passed as a plausible-looking 0.7R.
    target_px = rng.high if htf.bias == "LONG" else rng.low
    reward = (target_px - entry_px) if htf.bias == "LONG" else (entry_px - target_px)
    if reward <= 0:
        rec.failing_rule = "R35"
        rec.lines.append(Line("R35", f"target {target_px:,.2f} is already taken - it lies "
                                     f"behind entry {entry_px:,.2f} for a {htf.bias}. There is "
                                     "no draw on liquidity left in this direction"))
        return rec
    rr = reward / risk if risk else 0.0

    pos = rng.position(entry_px)
    zone = rng.zone(entry_px)

    rec.kind = "SETUP"
    rec.lines.append(Line("R5", f"entry in {zone} ({pos:.2f} of range)"))
    rec.lines.append(Line("R30", f"5m iFVG {gap.low:,.2f}-{gap.high:,.2f} "
                                 f"(formed {fmt_hm(gap.formed_time, day_str)}, inverted "
                                 f"{fmt_hm(gap.inverted_time, day_str)}), retested {fmt_hm(entry_t, day_str)}"))
    if gap.liquidity is not None:
        rec.lines.append(Line("R12", f"liquidity inside the gap {gap.liquidity:,.2f} "
                                     f"@ {fmt_hm(gap.liquidity_time, day_str)} - this is the precise "
                                     "target, not the gap boundary"))
    else:
        rec.unresolved.append(gap.liquidity_note)
    rec.lines.append(Line("R33", f"stop {stop_px:,.2f}  ·  risk {risk:,.2f} pts "
                                 f"(invalidation = the swept {htf.side} extreme of the "
                                 f"qualifying {qual.cycle} SMT @ {fmt_et(qual.pivot_time)})"))
    rec.lines.append(Line("R35", f"target {target_px:,.2f} (range extreme)  ·  {rr:.1f}R"))
    rec.lines.append(Line("R43", f"risk expressed in R: 1R = {risk:,.2f} pts; "
                                 f"expectancy needs win% AND R:R together (R44)"))

    # ── Soft branches — reported, never gates.
    et_dt = datetime.fromtimestamp(entry_t, ET)
    if (et_dt.hour, et_dt.minute) < RTH_OPEN_ET:
        rec.branches.append(
            f"R31 (soft) - entry {fmt_hm(entry_t, day_str)} is BEFORE 09:30 ET. dOoMeR prefers "
            "waiting for the 9:30 open on these; the engine reports the branch and "
            "does not resolve it")
    want_zone = "DISCOUNT" if htf.bias == "LONG" else "PREMIUM"
    if zone != want_zone:
        rec.branches.append(
            f"R5/R32 - entry is in {zone} but a {htf.bias} prefers {want_zone}. R32: "
            "entering from the wrong side of equilibrium lowers the R:R ceiling")
    if seq_kind == "SKIP":
        rec.branches.append("R24 - this is a Sequential SKIP, not a clean nesting")
    # The Aura Asset is a FLAGGED leg (R17: dOoMeR's own origin story is admitted
    # speculation) AND its tick size is the least reliably measurable of the four.
    # A confirmation resting on it ALONE is the weakest link in the chain and must
    # say so on the face of the record.
    if conf_ev is not None and conf_ev.diverging == [AURA_ASSET]:
        rec.branches.append(
            f"R17 (flagged) - the {conf_ev.cycle}m confirmation diverges on {AURA_ASSET} "
            "ALONE, with no index leg agreeing. R17 is a flagged rule and this leg's "
            "tick size is the least reliably measured of the four, so its noise floor "
            "is the softest. Treat this confirmation as the weakest link in the chain "
            "and verify it by hand")
    if risk > rng.size * STOP_OVERSIZE_FRACTION:
        rec.branches.append(
            f"R34 - stop is {risk:,.2f} pts, over {STOP_OVERSIZE_FRACTION:.0%} of the "
            f"{rng.size:,.2f}-pt range. R34's answer is the same idea on a correlated "
            "leg with a tighter equivalent gap (e.g. YM instead of ES) - not taken "
            "automatically, because which leg is a judgement call")
    if age_days > 5:
        rec.branches.append(
            f"R23 - the driving daily SMT is {age_days:.1f} days old. R23 says read the "
            "CURRENT state; the range is still live per R6, but check by hand that no "
            "opposing signal has formed")
    rec.branches.append("R19 - probabilistic, not guaranteed. Never treat as certain")
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def render(records: list[Record], series, meta, span, argv_note: str) -> str:
    t_from, t_to = span
    out: list[str] = []
    w = out.append

    w("# Aura Sequential-SMT — computed setups (Phase S1c)")
    w("")
    w("> ## ⚠️ MACHINE-GENERATED — NOT A TRAINING RECORD")
    w("> These setups were computed by a script from exported bars. They are **not**")
    w("> Paul's reps. They must never touch the evidence layer: no `evidence_assets`,")
    w("> no rep credit, nothing feeding the streak, the calibration score or the")
    w("> Readiness Gate. A tutorial artifact is not a training record.")
    w("")
    w(f"Generated by `api/scripts/aura_setup_engine.py` — {argv_note}")
    w("")

    w("## The sample this ran on")
    w("")
    w(f"- **Source:** {meta.get('source')}")
    w(f"- **Session URL:** {meta.get('session_url')}")
    w(f"- **Extracted via:** `{meta.get('extracted_via')}`")
    w(f"- **Declared span:** {t_from.strftime('%Y-%m-%d')} → {t_to.strftime('%Y-%m-%d')} (ET)")
    w("")
    w("| Resolution | Symbol | Bars | First bar (UTC) | Last bar (UTC) | Measured tick |")
    w("|---|---|---:|---|---|---:|")
    for res in ["D", "240", "60", "15", "5"]:
        for sym, s in series.get(res, {}).items():
            w(f"| {res} | {sym} | {len(s)} | "
              f"{datetime.fromtimestamp(s.times[0], timezone.utc):%Y-%m-%d %H:%M} | "
              f"{datetime.fromtimestamp(s.times[-1], timezone.utc):%Y-%m-%d %H:%M} | "
              f"{s.tick:g} |")
    w("")

    w("## Declared thresholds — every one of these is a choice, not a fact")
    w("")
    w(f"- **Noise floor:** {NOISE_FLOOR_TICKS:g} ticks of each instrument's own "
      "**measured** tick size, applied to BOTH sides of a divergence. Without it, "
      "zero-margin near-misses manufacture phantom SMT (measured 2026-08-13).")
    w(f"- **Forward window** (was the level taken?): "
      + ", ".join(f"{k // 60}m→{v} bars" if k < 86400 else f"D→{v} bars"
                  for k, v in sorted(FORWARD_BARS.items())))
    w(f"- **Cascade (R27):** framing `{CYCLE_FRAMING}` → confirm `{CYCLE_CONFIRM}m` → "
      f"session `{CYCLE_SESSION}m` → entry `{CYCLE_ENTRY}m`")
    w(f"- **Range framing (R4/R7):** anchored on the driving SMT, searched from "
      f"{RANGE_ANCHOR_PRE_BARS} framing bars before its pivot; SMT itself found over a "
      f"{FRAMING_LOOKBACK_BARS}-bar lookback")
    w(f"- **Entry window:** {ENTRY_WINDOW_ET[0][0]:02d}:{ENTRY_WINDOW_ET[0][1]:02d}–"
      f"{ENTRY_WINDOW_ET[1][0]:02d}:{ENTRY_WINDOW_ET[1][1]:02d} ET — opens before 09:30 "
      "deliberately, so R31's pre-open branch stays reportable instead of being defined away")
    w(f"- **R34 oversize-stop flag:** risk > {STOP_OVERSIZE_FRACTION:.0%} of the range")
    w(f"- **R9 ambiguity tolerance:** {R9_AMBIGUITY_TOLERANCE:.0%} — inside this, the "
      "engine refuses to pick a range")
    w(f"- **{AURA_ASSET} admissibility (R17):** intraday only "
      f"({AURA_ASSET_MIN_RES_SEC // 60}m–{AURA_ASSET_MAX_RES_SEC // 60}m). "
      "**Refused at daily/weekly** — its bars bucket on a different exchange day, "
      "which is the exact defect R17 rejected DXY for.")
    w("")
    w("**Hard gates** (a failure here is logged as a rejection naming the rule):")
    for g in HARD_GATES:
        w(f"- `{g}`")
    w("")
    w("**Soft / reported branches** (never gates):")
    for g in SOFT_BRANCHES:
        w(f"- `{g}`")
    w("")

    setups = [r for r in records if r.kind == "SETUP"]
    rejects = [r for r in records if r.kind == "REJECTION"]
    w("## Result")
    w("")
    w(f"- **{len(records)}** ET days evaluated")
    w(f"- **{len(setups)}** setups")
    w(f"- **{len(rejects)}** rejections / stand-asides")
    w("")
    w("> A day correctly stood aside is a record, not a blank (R51). The rejections "
      "below are the more valuable half of this log — no instrument Paul currently "
      "has keeps them.")
    w("")

    if setups:
        w("## Setups")
        w("")
        for r in setups:
            w("```")
            w(f"{r.day} · {PRIMARY} · bias {r.bias}")
            for ln in r.lines:
                w(f"  {ln.rule:<4} {ln.text}")
            for u in r.unresolved:
                w(f"  UNRESOLVED: {u}")
            for b in r.branches:
                w(f"  BRANCH: {b}")
            w("```")
            w("")

    w("## Rejections and stand-asides")
    w("")
    for r in rejects:
        w("```")
        w(f"{r.day} · REJECTED at {r.failing_rule}")
        for ln in r.lines:
            w(f"  {ln.rule:<4} {ln.text}")
        for u in r.unresolved:
            w(f"  UNRESOLVED: {u}")
        w("```")
        w("")

    by_rule: dict[str, int] = {}
    for r in rejects:
        by_rule[r.failing_rule or "?"] = by_rule.get(r.failing_rule or "?", 0) + 1
    w("### Rejections by failing rule")
    w("")
    w("| Failing rule | Days |")
    w("|---|---:|")
    for k, v in sorted(by_rule.items(), key=lambda x: -x[1]):
        w(f"| {k} | {v} |")
    w("")
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    series, meta = load_bars(a.bars)
    d0 = datetime.strptime(a.t_from, "%Y-%m-%d")
    d1 = datetime.strptime(a.t_to, "%Y-%m-%d")

    records: list[Record] = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:      # Mon-Fri; weekend days are not sessions
            records.append(analyse_day(series, d))
        d += timedelta(days=1)

    argv_note = (f"--bars {a.bars.name} --from {a.t_from} --to {a.t_to}")
    md = render(records, series, meta, (d0, d1), argv_note)

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "computed-setups.md").write_text(md, encoding="utf-8")
    (a.out / "computed-setups.json").write_text(json.dumps([
        {
            "day": r.day, "kind": r.kind, "bias": r.bias,
            "failing_rule": r.failing_rule,
            "lines": [{"rule": ln.rule, "text": ln.text} for ln in r.lines],
            "unresolved": r.unresolved, "branches": r.branches,
        } for r in records
    ], indent=2), encoding="utf-8")

    n_set = sum(1 for r in records if r.kind == "SETUP")
    print(f"{len(records)} days · {n_set} setups · {len(records) - n_set} rejections")
    print(f"-> {a.out / 'computed-setups.md'}")


if __name__ == "__main__":
    main()
