#!/usr/bin/env python
"""
Aura Sequential-SMT setup engine  —  Phase S1c, hardened in S1d.

Computes Aura setups from REAL exported bars and logs them, with rejections, in an
auditable form: every line carries the rule ID, the computed value, and the bar/time
it came from, so Paul can check it against the Tradezella chart.

    # S1c (as originally run — 22 weekdays, 1 setup / 21 rejections)
    python api/scripts/aura_setup_engine.py \
        --bars api/docs/evidence/s1c/bars/tradezella-831607-export.json \
        --from 2025-05-01 --to 2025-05-30 \
        --out api/docs/evidence/s1c

    # S1d (the declared week, with weekly + 1m added and outcomes simulated)
    python api/scripts/aura_setup_engine.py \
        --bars api/docs/evidence/s1c/bars/tradezella-831607-export.json \
        --bars api/docs/evidence/s1d/bars/tradezella-831607-weekly.json \
        --bars api/docs/evidence/s1d/bars/tradezella-831607-1m-week.json \
        --from 2025-05-26 --to 2025-05-30 \
        --out api/docs/evidence/s1d --shapes

WHAT THIS IS NOT
    - It is not a chart read. Nothing here is perception; it is arithmetic on the
      OHLC the chart itself exported.
    - It is not Paul's practice. Machine-found setups are quarantined (see the
      QUARANTINE banner in the report) and must never touch the evidence layer.
    - It does not resolve judgement rules. R9 / R8 / R31 surface as UNRESOLVED or
      as a reported branch, never as a silent pick.

WHAT S1d ADDED (and why each was a gap worth closing)
    - **Weekly cycle (R18/R27).** Daily was previously the deepest rung, so the
      canonical nesting pair R18 actually names — weekly-with-daily-inside — could
      not be evaluated at all. Exported NATIVELY; nothing is aggregated from daily
      bars, because a synthesised week is not a week the market traded.
    - **NWOG / NDOG (R11).** Implemented against a per-symbol session boundary that
      is MEASURED from each symbol's own timestamps, not assumed. CHFUSD's boundary
      genuinely differs from the futures', which is why S1c refused to guess it.
    - **Outcome simulation.** The engine previously planned a trade and never walked
      price forward, so every `R` was an intention. It now walks 1m (falling back to
      5m) and reports stop-first / target-first with the bar it happened on.
    - **R21 / R22 / R13 / R8**, each either implemented or explicitly left UNRESOLVED.
    - **Bounded markup primitives.** Shapes now carry a computed start AND end time
      (rectangles / rays / bounded segments). An infinite horizontal line asserts
      "this level applies at all times", which contradicts R6 and R7 — see
      neurospect-wiki concepts/mastery/aura/chart-markup.md §0b.

Source of the rules: neurospect-wiki concepts/mastery/aura/rules.md (canonical).
"""

from __future__ import annotations

import argparse
import json
import math
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

ENGINE_VERSION = "S1d.1"   # printed in every report, so an output states its engine

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
#
# ⚠ The weekly entry is 3 bars, and it is a CHOICE with real consequences: a weekly
# forward window of 3 bars means a weekly signal is not knowable for roughly a month.
# That is conservative by construction and it will retire weekly signals a live
# trader might act on sooner. Stated here rather than buried.
FORWARD_BARS = {604800: 3, 86400: 5, 14400: 6, 3600: 8, 900: 8, 300: 8, 60: 10}

# The HTF→LTF cascade actually available in this export (R27).
# S1d added the weekly rung. R18's canonical example is a WEEKLY-cycle SMT with a
# DAILY-cycle SMT nested inside it, and until S1d the engine could not evaluate that
# pair at all — daily was the deepest cycle exported.
CYCLE_WEEKLY = "W"        # R18's canonical outer rung (S1d)
CYCLE_FRAMING = "D"       # range + HTF SMT
CYCLE_CONFIRM = "240"     # 4H — the adjacent cycle R18 nests into
CYCLE_SESSION = "15"      # session-cycle SMT (R30's preference)
CYCLE_ENTRY = "5"         # R30: 5m preferred over 3m
CYCLE_FINE = "1"          # outcome sequencing only — never a signal cycle (R28)

RES_SECONDS = {"W": 604800, "D": 86400, "240": 14400, "60": 3600,
               "15": 900, "5": 300, "1": 60}

# ⚠ WEEKLY IS REPORTED, NOT GATED — and that is a deliberate choice, not an
# oversight. Promoting weekly confirmation to a hard gate would delete setups, and
# the engine has no calibration data saying it should: R18 is satisfied by ANY two
# adjacent cycles, and daily→4H is a legitimate pair. So the weekly rung is emitted
# as evidence STRENGTHENING or WEAKENING a read (R18 canonical nesting present /
# absent), and Paul's review of that column is what should decide whether it ever
# becomes a gate. Hardening it here would be the engine deciding a calibration
# question that only he can answer.
WEEKLY_IS_A_GATE = False

# R28: HTF divergence dominates LTF, and a 1-minute microcycle divergence is
# explicitly low-influence. So 1m bars are admitted for OUTCOME SEQUENCING ONLY and
# are never scanned for signals — using them as a signal cycle would contradict R28.
FINE_RES_IS_SIGNAL_CYCLE = False

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


# ─────────────────────────────────────────────────────────────────────────────
# S1e — THE CONFIGURATION AXES
#
# The S1e audit measured that the 128-entry tally violated every one of Aura's
# stated preferences (R17 100%, R18 91%, R30 90%, R30/R32 56%, R45 38%) — because
# each was REPORTED and none was GATED. Enforcing them collapsed the sample to zero,
# which says the engine's DETECTORS are mis-specified, not that the model fails.
#
# Every field below was previously a hardcoded assumption presented as a fact. They
# are now explicit so the sweep can vary them and show what the result is SENSITIVE
# to. Defaults reproduce the pre-S1e behaviour EXACTLY — the S1c regression is the
# proof of that and must be re-run whenever this block changes.
#
# ⛔ THIS IS A SENSITIVITY INSTRUMENT, NOT A SEARCH FOR THE BEST CELL. With ~32
# independent episodes, sweeping N configurations produces a flattering winner by
# chance. Every cell gets published; no cell is adopted on the strength of its
# expectancy alone.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Config:
    # AXIS 1 — R17, the Aura Asset. Default False encodes "CHFUSD's daily bucketing
    # does not correspond to the futures' session, so it cannot be a daily leg",
    # which refused the 4th leg on 100% of S1e's entries. True admits it at every
    # cycle, reading it on its own calendar as R17 asks ("read it exactly like a
    # normal divergence leg").
    aura_asset_all_cycles: bool = False

    # AXIS 2 — R18's weekly lookback. 12 was invented by S1d; S1d itself flagged
    # that the nearest real weekly SMT fell at ~14 weeks, JUST outside it.
    weekly_lookback_weeks: int = 12

    # AXIS 3 — R30's retest. "report": take the touch found in the entry window and
    # report that an earlier one existed (pre-S1e behaviour). "require_first": only
    # enter if the window's touch IS the first. "session_first": an overnight touch
    # does not consume the entry — the NY session gets its own first touch.
    retest_mode: str = "report"          # report | require_first | session_first

    # AXIS 4 — R30/R32's reference range. Rule 30 says discount (long) / premium
    # (short) "of the LTF range"; the engine measured against the driving HTF range.
    zone_ref: str = "htf"                # htf | ltf

    # AXIS 1b — how the Aura Asset's bars are joined to the primary's. Measured:
    # CHFUSD shares 0 of NQ's 3,794 daily timestamps, so "timestamp" makes the leg
    # permanently NOT-VISIBLE at D/W no matter whether it is admitted.
    aura_asset_join: str = "timestamp"    # timestamp | session_date

    # ── Enforcement of preferences the engine has always merely reported ────────
    enforce_zone: bool = False           # R30/R32 as a gate, not a branch
    min_planned_rr: float = 0.0          # R45 "at least 1:1" as a gate
    weekly_is_a_gate: bool = False       # R18 canonical nesting as a gate

    def label(self) -> str:
        return (f"aa={'all' if self.aura_asset_all_cycles else 'ltf'}"
                f"·wk={self.weekly_lookback_weeks}"
                f"·rt={self.retest_mode}"
                f"·zone={self.zone_ref}·aaj={self.aura_asset_join}"
                f"·gz={int(self.enforce_zone)}"
                f"·rr={self.min_planned_rr:g}"
                f"·wg={int(self.weekly_is_a_gate)}")


CFG = Config()

# ── R11 NWOG / NDOG (S1d) ────────────────────────────────────────────────────
# A New Day / New Week Opening Gap is the gap between one session's CLOSE and the
# next session's OPEN, so it needs a session boundary — and S1c refused to guess
# one because CHFUSD's does not match the futures'. The boundary is now MEASURED
# per symbol (see measure_session_boundary): the recurring intraday break in that
# symbol's own timestamp sequence. Measuring it means the rule cannot be wrong
# because someone mis-remembered a CME session time.
#
# A gap must exceed this many ticks to count. Without a floor, every session break
# emits a "gap" of one tick of float noise and NWOG/NDOG become meaningless.
OPENING_GAP_MIN_TICKS = 2.0

# ── R11 FVG size floor (S1d) ─────────────────────────────────────────────────
# ⚠ S1c had NO size floor on FVG detection, so a ONE-TICK gap (e.g. NQ
# 21,348.75-21,349.00) was admitted as an entry candidate on equal footing with a
# 6-tick one. Two reasons that is wrong, and the second is the serious one:
#   1. Drawing them produced 27 rectangles on a single session — the "wall of lines"
#      Paul rejected, where the ink hides the structure instead of showing it.
#   2. More importantly it is the SAME defect class as the phantom-SMT bug: a
#      measurement at the resolution of the instrument's own granularity, treated as
#      a real feature of the market. The engine already declares a noise floor for
#      SMT (NOISE_FLOOR_TICKS) and for opening gaps, on exactly this reasoning; FVGs
#      were the gap in the argument.
# R11 does not state a minimum size, so this is a DECLARED CHOICE and not a rule.
# Verified not to change the S1c result: the 05-30 entry gap is 6 ticks wide.
FVG_MIN_TICKS = 4.0

# The minimum share of day-boundaries a candidate break must account for before it
# is believed as THE session boundary (same recur-before-you-believe discipline that
# fixed the CHFUSD tick measurement).
SESSION_BREAK_MIN_SUPPORT = 0.5

# ── Outcome simulation (S1d) ─────────────────────────────────────────────────
# Resolutions tried in order for walking price forward. Finer first: if stop and
# target both fall inside one bar the sequence is genuinely unknown at that
# resolution, and the honest move is to try a finer one before giving up — never to
# assume which came first.
OUTCOME_RESOLUTIONS = ["1", "5"]

# ── R8 false-sweep tiebreak (S1d) ────────────────────────────────────────────
# R8: "if a swing looks false across the triad and there's a large gap between
# candidates, prefer the low/high actually swept on all triad assets, even if it
# isn't the most extreme candidate." Both halves are judgement — "looks false" and
# "a large gap". The engine implements the DETECTABLE half (was this extreme swept
# on every triad leg?) and emits UNRESOLVED with both candidates when they disagree
# materially. It never switches to the candidate that happens to yield a trade.
R8_MATERIAL_GAP_FRACTION = 0.10   # candidates differing by more than this are "a large gap"

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
    "R18/R27 WEEKLY confirmation — reported as canonical-nesting evidence, NOT a gate",
    "R21     cross-cycle gap-pairing — reported as supporting confirmation",
    "R22     extreme-of-the-larger-segment — reported ALONGSIDE R35, never swapped in",
    "R8      false-sweep tiebreak — UNRESOLVED with both candidates when they disagree",
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


def load_bars(paths: list[Path]) -> tuple[dict[str, dict[str, Series]], dict]:
    """Load and MERGE one or more export files, keyed resolution -> symbol.

    Multiple files because the exports are immutable per-extraction artifacts: S1c
    pulled D/240/60/15/5, S1d added a native W export and a 1m week. Merging at load
    time keeps each extraction a separate, re-verifiable file rather than rewriting a
    2.3 MB blob every time a resolution is added.

    A later file wins on collision, and the collision is recorded in meta so an
    overwrite can never be silent.
    """
    out: dict[str, dict[str, Series]] = {}
    meta: dict = {"sources": [], "collisions": []}
    for path in paths:
        raw = json.loads(path.read_text())
        for res, syms in raw["resolutions"].items():
            out.setdefault(res, {})
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
                if sym in out[res]:
                    meta["collisions"].append(
                        f"{res}/{sym}: {path.name} replaced an earlier file's series "
                        f"({len(out[res][sym])} -> {len(s)} bars)")
                out[res][sym] = s
        meta["sources"].append({
            "file": path.name,
            **{k: v for k, v in raw.items() if k != "resolutions"},
        })
    # Keep the top-level descriptive keys of the FIRST file for report compatibility.
    if meta["sources"]:
        for k in ("source", "session_url", "extracted_via", "chart_timezone"):
            if k in meta["sources"][0]:
                meta[k] = meta["sources"][0][k]
    return out, meta


def measure_session_boundary(series: dict[str, dict[str, Series]], sym: str) -> dict:
    """MEASURE the symbol's own session boundaries — never assume a CME session time.

    R11's NWOG/NDOG are gaps between one session's CLOSE and the next session's OPEN,
    so they are undefined without a session boundary. S1c declined to implement them
    for exactly this reason: CHFUSD's boundary does not match the futures'. Guessing
    would have produced a confident gap at the wrong place on one of four legs.

    ⚠ THE DAILY AND WEEKLY BREAKS MUST BE SEPARATED BY CALENDAR DAYS SKIPPED, not by
    gap length. A first cut of this function excluded only gaps longer than three days
    and so classified CHFUSD's Fri-16:55 -> Sun-17:00 WEEKEND break as its daily
    boundary (support 0.75 on 3 observations) — a confident-looking answer that would
    have put every CHFUSD NDOG at the wrong place. Forex is near-continuous intraday,
    so for CHFUSD the correct verdict is that a daily boundary is NOT MEASURABLE, and
    that verdict has to be reachable.

    Returns {"daily": {...} | None, "weekly": {...} | None, "res": ...}. A None is a
    real answer: NOT-MEASURABLE, distinct from "no gap found".
    """
    result: dict = {"symbol": sym, "daily": None, "weekly": None, "measured_at_res": None}
    for res in ("5", "15", "60"):
        s = series.get(res, {}).get(sym)
        if s is None or len(s) < 200:
            continue
        step = RES_SECONDS[res]
        # Bucketed by how many CALENDAR DAYS the break crosses: 1 => daily
        # maintenance halt, >1 => a weekend / holiday break.
        daily: dict[tuple, int] = {}
        weekly: dict[tuple, int] = {}
        n_day_bnd = n_week_bnd = 0
        for i in range(1, len(s)):
            if s.times[i] - s.times[i - 1] <= step:
                continue
            close_dt = datetime.fromtimestamp(s.times[i - 1], ET)
            open_dt = datetime.fromtimestamp(s.times[i], ET)
            days_skipped = (open_dt.date() - close_dt.date()).days
            key = ((close_dt.hour, close_dt.minute), (open_dt.hour, open_dt.minute))
            if days_skipped <= 1:
                daily[key] = daily.get(key, 0) + 1
                n_day_bnd += 1
            else:
                weekly[key] = weekly.get(key, 0) + 1
                n_week_bnd += 1
        result["measured_at_res"] = res

        for label, buckets, total in (("daily", daily, n_day_bnd),
                                      ("weekly", weekly, n_week_bnd)):
            if not buckets or total == 0:
                continue
            (c_hm, o_hm), count = max(buckets.items(), key=lambda kv: kv[1])
            support = count / total
            if support < SESSION_BREAK_MIN_SUPPORT:
                continue
            # A "break" that does not actually skip any time is a bar boundary, not a
            # session boundary. Require the halt to exceed one bar of the resolution
            # it was measured at, or it tells us nothing about a session.
            result[label] = {
                "close_et": f"{c_hm[0]:02d}:{c_hm[1]:02d}",
                "open_et": f"{o_hm[0]:02d}:{o_hm[1]:02d}",
                "observations": count, "of_boundaries": total, "support": support,
                "distinct_patterns": len(buckets),
            }
        break
    return result


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


_SESSION_BUCKET_CACHE: dict[tuple[int, str], dict] = {}


def _session_bucket(t: int, res: str):
    """The ET calendar day (D) or ISO week (W) a timestamp belongs to."""
    dt = datetime.fromtimestamp(t, ET)
    if res == "W":
        iso = dt.isocalendar()
        return (iso[0], iso[1])
    return dt.date()


def session_aligned_at(s: Series, res: str, t: int) -> int | None:
    """Index of the bar sharing t's ET session bucket, or None.

    ⭐ WHY THIS EXISTS (S1e, measured 2026-08-14): CHFUSD shares **0 of NQ's 3,794
    daily timestamps**, while ES shares 3,794/3,794 and YM 3,792/3,794. The Aura
    Asset's daily bars are stamped on a different session boundary, so the exact
    timestamp join used for the futures legs can NEVER match — the leg came back
    `NOT-VISIBLE` on 100% of setups even after it was admitted.

    That is why merely admitting the 4th leg changed nothing: admission was
    necessary but not sufficient. R17 says to read the Aura Asset "exactly like a
    normal divergence leg", which requires joining on the SESSION each bar belongs
    to rather than on a timestamp the two exchanges never share.
    """
    cache_key = (id(s), res)
    idx = _SESSION_BUCKET_CACHE.get(cache_key)
    if idx is None:
        idx = {}
        for i, ts in enumerate(s.times):
            idx.setdefault(_session_bucket(ts, res), i)
        _SESSION_BUCKET_CACHE[cache_key] = idx
    return idx.get(_session_bucket(t, res))


def admissible_legs(res: str) -> tuple[list[str], list[str]]:
    """Returns (admitted, refused). Encodes the CHFUSD daily refusal as a rule."""
    rs = RES_SECONDS[res]
    admitted = list(TRIAD_LEGS)
    refused = []
    # AXIS 1 (S1e). With aura_asset_all_cycles the leg is read on its own calendar at
    # every cycle, per R17's "read it exactly like a normal divergence leg". The
    # default keeps the measured daily refusal, which is why R17 fired 128/128.
    if CFG.aura_asset_all_cycles or AURA_ASSET_MIN_RES_SEC <= rs <= AURA_ASSET_MAX_RES_SEC:
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
            # AXIS 1b (S1e): the Aura Asset's bars share NO timestamps with the
            # futures at D/W, so the exact join returns nothing. Joining on the ET
            # session bucket is what lets R17's 4th leg actually vote.
            if (CFG.aura_asset_join == "session_date"
                    and leg_sym == AURA_ASSET and res in ("D", "W")):
                def _lookup(t, _leg=leg, _res=res):
                    return session_aligned_at(_leg, _res, t)
            else:
                _lookup = leg.at
            lvl_idx = [_lookup(t) for t in pivot_ts]
            lvl_idx = [i for i in lvl_idx if i is not None]
            w_idx = [_lookup(t) for t in fwd_ts]
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
    # S1d: a drawn object's TIME EXTENT is a claim (chart-markup §0b), so a gap needs
    # an END as well as a start. `mitigated_time` is when price first traded back into
    # the gap; None means still live, and a live gap is drawn only to the current edge.
    mitigated_time: int | None = None
    liquidity: float | None = None      # R12: the swing level nested INSIDE the gap
    liquidity_time: int | None = None
    liquidity_note: str = ""
    liquidity_source: str = ""          # R13: "inside" | "zoom-in" | "look-left"


def find_fvgs(s: Series, lo: int, hi: int) -> tuple[list[Gap], int]:
    """R11: only FVG / iFVG / NWOG / NDOG. No BPR, no volume-imbalance vocabulary.

    Returns (gaps, n_below_floor) — the count of sub-floor gaps is RETURNED rather than
    discarded, so the report can say what was excluded. A filter whose effect is
    invisible reads as "there was nothing there".
    """
    out: list[Gap] = []
    floor = s.tick * FVG_MIN_TICKS
    below = 0
    for i in range(max(lo, 1), min(hi, len(s) - 1)):
        if s.h[i - 1] < s.l[i + 1]:      # bullish FVG
            if s.l[i + 1] - s.h[i - 1] < floor:
                below += 1
            else:
                out.append(Gap("FVG", "bullish", s.h[i - 1], s.l[i + 1], s.times[i]))
        if s.l[i - 1] > s.h[i + 1]:      # bearish FVG
            if s.l[i - 1] - s.h[i + 1] < floor:
                below += 1
            else:
                out.append(Gap("FVG", "bearish", s.h[i + 1], s.l[i - 1], s.times[i]))
    return out, below


def find_opening_gaps(s: Series, boundary: dict, lo: int, hi: int) -> list[Gap]:
    """R11 NWOG / NDOG — the gap between one session's CLOSE and the next's OPEN.

    S1c declared these and refused to implement them, because the definition needs a
    session boundary and CHFUSD's does not match the futures'. `boundary` here is the
    MEASURED result from measure_session_boundary, so the gap is located by what the
    data does rather than by a remembered CME session time.

    `boundary["daily"]` being None is a real answer — a symbol with no measurable
    daily halt (CHFUSD) gets no NDOGs rather than fabricated ones.
    """
    out: list[Gap] = []
    step = RES_SECONDS[s.res]
    floor = s.tick * OPENING_GAP_MIN_TICKS
    daily = boundary.get("daily")
    weekly = boundary.get("weekly")
    for i in range(max(lo, 1), min(hi, len(s))):
        if s.times[i] - s.times[i - 1] <= step:
            continue
        close_dt = datetime.fromtimestamp(s.times[i - 1], ET)
        open_dt = datetime.fromtimestamp(s.times[i], ET)
        days_skipped = (open_dt.date() - close_dt.date()).days
        hm_close = f"{close_dt.hour:02d}:{close_dt.minute:02d}"
        hm_open = f"{open_dt.hour:02d}:{open_dt.minute:02d}"
        if days_skipped > 1 and weekly and hm_close == weekly["close_et"] \
                and hm_open == weekly["open_et"]:
            kind = "NWOG"
        elif days_skipped <= 1 and daily and hm_close == daily["close_et"] \
                and hm_open == daily["open_et"]:
            kind = "NDOG"
        else:
            continue
        prev_close, new_open = s.c[i - 1], s.o[i]
        if abs(new_open - prev_close) <= floor:
            continue      # a gap smaller than the noise floor is not a gap
        # Geometry, stated plainly: gapped UP leaves the gap BELOW price, where it acts
        # as support when revisited (bullish); gapped DOWN leaves it above (bearish).
        out.append(Gap(
            kind=kind,
            direction=("bullish" if new_open > prev_close else "bearish"),
            low=min(prev_close, new_open), high=max(prev_close, new_open),
            formed_time=s.times[i],
        ))
    return out


def attach_mitigation(g: Gap, s: Series, as_of: int) -> None:
    """When did price first trade back INTO the gap? That is where the drawing ends.

    chart-markup §0b: a PD array is a rectangle bounded formation -> mitigation. Left
    unbounded it keeps asserting the level applies forever, which is the claim Paul
    rejected and which R6/R7 explicitly deny.

    ⚠ THE SEARCH MUST START AFTER INVERSION FOR AN iFVG, not after the original FVG
    formed. Inversion IS price closing through the zone, so a search anchored on
    `formed_time` finds the inverting move itself and reports the gap as mitigated
    BEFORE it inverted. That produced rectangles whose end timestamp preceded their
    start — 15 of them, geometrically impossible and entirely plausible-looking in a
    screenshot. Caught only by reading the emitted coordinates.
    """
    anchor = max(g.formed_time, g.inverted_time or 0)
    start = bisect_right(s.times, anchor)
    end = bisect_right(s.times, as_of)
    for i in range(start, end):
        if s.l[i] <= g.high and s.h[i] >= g.low:
            g.mitigated_time = s.times[i]
            return


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


def attach_liquidity(g: Gap, s: Series, as_of: int, finer: Series | None = None) -> None:
    """R12: the precise target is the swing high/low nested INSIDE the gap, not the
    gap boundary. R13: if none is visible, LOOK LEFT or ZOOM IN.

    S1c implemented only the first test and emitted R13 as advice to Paul. R13 is not
    advice — it names two concrete follow-up searches, and both are computable:

      zoom-in    a lower-timeframe swing usually appears inside the same gap, so
                 re-run the pivot search on the finer series (1m) within the gap.
      look-left  a resting UNTAKEN level at a similar price, found to the left of the
                 gap. "Untaken" is the load-bearing word: a level price has already
                 traded through is not resting liquidity, so each candidate is checked
                 for having survived up to `as_of` before it is offered.

    Which route supplied the answer is recorded in `liquidity_source`, because a
    zoom-in level and a look-left level are different claims about where the target is.
    """
    hi = bisect_right(s.times, as_of)
    inside = [p for p in find_pivots(s, 0, hi)
              if g.low <= p.price <= g.high and p.known_at <= as_of]
    if inside:
        p = max(inside, key=lambda x: x.time)
        g.liquidity, g.liquidity_time, g.liquidity_source = p.price, p.time, "inside"
        return

    # R13a — ZOOM IN.
    if finer is not None:
        fhi = bisect_right(finer.times, as_of)
        flo = max(0, bisect_left(finer.times, g.formed_time) - 1)
        fin = [p for p in find_pivots(finer, flo, fhi)
               if g.low <= p.price <= g.high and p.known_at <= as_of]
        if fin:
            p = max(fin, key=lambda x: x.time)
            g.liquidity, g.liquidity_time = p.price, p.time
            g.liquidity_source = f"zoom-in ({finer.res}m)"
            g.liquidity_note = (f"R13 - no swing inside the gap at {s.res}m; found by "
                                f"zooming in to {finer.res}m, as R13 prescribes")
            return

    # R13b — LOOK LEFT for a resting UNTAKEN level at a similar price.
    band = (g.high - g.low)
    lo_b, hi_b = g.low - band, g.high + band
    g_idx = bisect_left(s.times, g.formed_time)
    left = [p for p in find_pivots(s, 0, g_idx) if lo_b <= p.price <= hi_b
            and p.known_at <= as_of]
    for p in sorted(left, key=lambda x: -x.time):
        # Untaken means price has not traded through it since it formed.
        after = range(bisect_right(s.times, p.time), hi)
        taken = any((s.h[i] > p.price) if p.side == "high" else (s.l[i] < p.price)
                    for i in after)
        if not taken:
            g.liquidity, g.liquidity_time = p.price, p.time
            g.liquidity_source = "look-left"
            g.liquidity_note = (f"R13 - no swing inside the gap; nearest RESTING UNTAKEN "
                                f"level to the left is the {p.side} {p.price:,.2f} @ "
                                f"{fmt_et(p.time)}")
            return

    g.liquidity_note = ("R13 - no internal liquidity at this resolution, none on a "
                        "zoom-in, and no resting untaken level to the left within one "
                        "gap-width. The precise target is genuinely NOT-VISIBLE here")


# ─────────────────────────────────────────────────────────────────────────────
# S1d — outcome simulation. The difference between a trade and an intention.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Outcome:
    verdict: str          # TARGET | STOP | UNRESOLVED-AT-RESOLUTION | UNRESOLVED-AT-DATA-EDGE
    res: str              # the resolution the walk was decided on
    at_time: int | None = None
    realised_r: float | None = None
    mfe_r: float = 0.0    # maximum favourable excursion, in R
    mae_r: float = 0.0    # maximum adverse excursion, in R
    bars_walked: int = 0
    last_bar: int | None = None
    note: str = ""


def simulate_outcome(series, bias: str, entry_t: int, entry_px: float,
                     stop_px: float, target_px: float) -> Outcome:
    """Walk price forward from the entry bar and report what ACTUALLY happened.

    Why this exists: without it every `R` the engine prints is *planned*. Paul asked to
    learn from "the trades you take", and a trade with no outcome is an intention.

    Three things this refuses to do:

    1. **Guess the sequence inside a bar.** If one bar's range spans BOTH the stop and
       the target, which came first is unknowable at that resolution. The walk retries
       on a finer resolution; if the finer one is also ambiguous the verdict is
       UNRESOLVED-AT-RESOLUTION. Assuming "stop first" (conservative) or "target first"
       (flattering) would both be inventions, and the flattering one is exactly how a
       backtest lies.
    2. **Treat running out of data as a result.** If neither level is touched before the
       last available bar, that is UNRESOLVED-AT-DATA-EDGE — a measurement gap, not a
       breakeven and not a loss. This matters concretely here: the replay is parked at
       2025-05-30 16:59 ET, so a trade entered on 05-30 has only that session to
       resolve in.
    3. **Round a touch into a fill.** A level is hit when the bar's range reaches it;
       slippage and queue position are not modelled, and are not claimed to be.
    """
    risk = abs(entry_px - stop_px)
    best: Outcome | None = None
    for res in OUTCOME_RESOLUTIONS:
        s = series.get(res, {}).get(PRIMARY)
        if s is None:
            continue
        i0 = bisect_right(s.times, entry_t)      # strictly AFTER the entry bar
        if i0 >= len(s):
            continue
        mfe = mae = 0.0
        ambiguous_at = None
        for i in range(i0, len(s)):
            if bias == "LONG":
                fav, adv = s.h[i] - entry_px, entry_px - s.l[i]
                hit_t, hit_s = s.h[i] >= target_px, s.l[i] <= stop_px
            else:
                fav, adv = entry_px - s.l[i], s.h[i] - entry_px
                hit_t, hit_s = s.l[i] <= target_px, s.h[i] >= stop_px
            mfe, mae = max(mfe, fav), max(mae, adv)
            if hit_t and hit_s:
                ambiguous_at = s.times[i]
                break
            if hit_s:
                return Outcome("STOP", res, s.times[i], -1.0, mfe / risk, mae / risk,
                               i - i0 + 1, s.times[-1])
            if hit_t:
                return Outcome("TARGET", res, s.times[i],
                               abs(target_px - entry_px) / risk,
                               mfe / risk, mae / risk, i - i0 + 1, s.times[-1])
        if ambiguous_at is not None:
            # Try the next (coarser) resolution only to report; do NOT resolve it.
            best = Outcome(
                "UNRESOLVED-AT-RESOLUTION", res, ambiguous_at, None,
                mfe / risk, mae / risk, 0, s.times[-1],
                note=("one bar's range spans BOTH the stop and the target, so which "
                      "was reached first is unknowable at this resolution. Not "
                      "guessed — a guess here is how a backtest flatters itself"))
            continue
        # Ran out of bars without touching either level.
        cand = Outcome(
            "UNRESOLVED-AT-DATA-EDGE", res, None, None, mfe / risk, mae / risk,
            len(s) - i0, s.times[-1],
            note=("neither stop nor target was reached before the last available bar. "
                  "The replay is parked at the data edge and advancing it would consume "
                  "days Paul intends to replay himself, so this outcome is NOT-VISIBLE "
                  "rather than breakeven"))
        # ⚠ KEEP THE FINEST resolution's verdict. OUTCOME_RESOLUTIONS is ordered finest
        # first, so the first unresolved result is the most granular one. An earlier
        # version overwrote it with each coarser attempt, and the record then claimed the
        # walk was decided at 5m when 1m data was loaded and had already been walked —
        # misreporting which instrument produced the measurement.
        if best is None:
            best = cand
    return best or Outcome("UNRESOLVED-AT-DATA-EDGE", "-", note="no series to walk")


# ─────────────────────────────────────────────────────────────────────────────
# S1d — R21 cross-cycle gap-pairing, R22 larger-segment extreme, R8 sweep check
# ─────────────────────────────────────────────────────────────────────────────

# R21: "weekly-cycle -> check daily gaps; daily/session -> 4H gaps; micro -> 15m-1H."
R21_PAIRING = {"W": "D", "D": "240", "240": "15", "15": "5"}


def r21_gap_pairing(series, driving_cycle: str, direction: str,
                    t_from: int, as_of: int) -> str | None:
    """R21 — confirmation by a gap on the cycle PAIRED with the driving SMT's cycle.

    Reported as supporting confirmation, never as a gate: R20 lists gap/SMT-fill as
    ONE OF several ways to confirm, so its absence does not invalidate a nesting that
    already qualified under R18.
    """
    paired = R21_PAIRING.get(driving_cycle)
    if paired is None:
        return None
    s = series.get(paired, {}).get(PRIMARY)
    if s is None:
        return f"R21 - paired cycle {paired} not available in this export (NOT-VISIBLE)"
    lo = max(0, bisect_left(s.times, t_from) - 1)
    hi = bisect_right(s.times, as_of)
    gaps = [g for g in find_fvgs(s, lo, hi)[0] if g.direction == direction]
    if not gaps:
        return (f"R21 - no {direction} gap on the paired {paired} cycle since "
                f"{fmt_et(t_from)}; this confirmation route is absent (R20 lists "
                "others, so it is not disqualifying)")
    g = gaps[-1]
    return (f"R21 - paired {paired}-cycle {direction} gap {g.low:,.2f}-{g.high:,.2f} "
            f"formed {fmt_et(g.formed_time)} supports the {driving_cycle} SMT")


def prim_tick_of(series, res: str) -> float:
    s = series.get(res, {}).get(PRIMARY)
    return s.tick if s is not None and s.tick else 0.01


def r22_larger_segment_extreme(series, outer_cycle: str, side: str,
                               smt_time: int, as_of: int) -> tuple[float, int, str] | None:
    """R22 — "if SMT occurred BETWEEN two segments of a larger cycle, expect the extreme
    of that larger segment to eventually be taken. This goes for all cycles."

    Implemented as: locate the bar of the LARGER cycle that contains the SMT, and take
    that bar's extreme in the direction of the bias. Reported ALONGSIDE R35's range
    extreme — never substituted for it, because choosing between two valid targets is
    a judgement R22 does not make for you.

    ⚠ WHAT THIS DOES NOT CHECK. R22's condition is that the SMT occurred *between two
    segments* of the larger cycle. This function only locates the larger-cycle bar
    CONTAINING the SMT; it does not verify the between-two-segments geometry, because
    "segment" is not defined precisely enough in the rulebook to test. So the level it
    returns is R22-shaped rather than R22-proven, and the report says so rather than
    presenting it as a satisfied rule.
    """
    s = series.get(outer_cycle, {}).get(PRIMARY)
    if s is None:
        return None
    i = bisect_right(s.times, smt_time) - 1
    if i < 0 or s.times[i] > as_of:
        return None
    px = s.l[i] if side == "high" else s.h[i]   # SHORT targets the low, LONG the high
    return px, s.times[i], outer_cycle


def _swept_on_all_legs(series, res: str, pivot_time: int,
                       side: str) -> tuple[bool | None, list[str]]:
    """Was the level at `pivot_time` swept on EVERY triad leg? None = NOT-VISIBLE."""
    prim = series[res][PRIMARY]
    fwd = FORWARD_BARS[RES_SECONDS[res]]
    pi = prim.at(pivot_time)
    if pi is None:
        return None, ["pivot bar not locatable by timestamp"]
    w_ts = prim.times[pi + 1: pi + 1 + fwd]
    notes, verdicts = [], []
    for sym in [PRIMARY] + TRIAD_LEGS:
        leg = series[res].get(sym)
        li = leg.at(pivot_time) if leg is not None else None
        idx = [leg.at(t) for t in w_ts] if leg is not None else []
        idx = [i for i in idx if i is not None]
        if leg is None or li is None or not idx:
            notes.append(f"{sym}:NOT-VISIBLE")
            continue
        lvl = leg.h[li] if side == "high" else leg.l[li]
        ext = max(leg.h[i] for i in idx) if side == "high" else min(leg.l[i] for i in idx)
        took = (ext > lvl) if side == "high" else (ext < lvl)
        verdicts.append(took)
        notes.append(f"{sym}:{'swept' if took else 'held'}")
    if len(verdicts) < 2:
        return None, notes
    return all(verdicts), notes


def r8_anchor_check(series, res: str, rng: "Range", as_of: int) -> list[str]:
    """R8 — the false-sweep tiebreak, applied to what R8 actually governs: which swing
    the RANGE EXTREME is anchored on.

    ⚠ A first cut of this ran the sweep test on the *driving SMT pivot* and therefore
    fired on every single setup — an SMT is BY CONSTRUCTION a level the other legs did
    not take, so "not swept on all legs" is the definition of the signal, not a warning
    about it. A check that cannot ever pass is not a check; it is noise that trains the
    reader to skip the UNRESOLVED lines.

    ⚠ There is also a genuine tension in the rulebook that this must not paper over.
    Rule 8's first sentence says anchor extremes only on SMT-QUALIFIED swings (which
    diverge); its second says prefer the extreme swept on ALL triad assets (which does
    not diverge). Both cannot be satisfied by the same swing. So the engine reports the
    measurement for both anchors and NEVER re-anchors — R8's tiebreak stays a judgement
    call, exactly as the boot prompt permits.

    Emits a line only when there is a materially different alternative candidate that
    WAS swept on all legs; silence means R8 has nothing to say here.
    """
    out: list[str] = []
    prim = series[res][PRIMARY]
    for anchor_t, anchor_px, side in ((rng.high_time, rng.high, "high"),
                                      (rng.low_time, rng.low, "low")):
        ok, notes = _swept_on_all_legs(series, res, anchor_t, side)
        if ok is not False:
            continue          # swept on all legs, or not visible — R8 has no tiebreak
        lo = max(0, bisect_left(prim.times, anchor_t) - FRAMING_LOOKBACK_BARS)
        hi = bisect_right(prim.times, as_of)
        alts = []
        for p in find_pivots(prim, lo, hi):
            if p.side != side or p.known_at > as_of or p.time == anchor_t:
                continue
            if abs(p.price - anchor_px) <= rng.size * R8_MATERIAL_GAP_FRACTION:
                continue      # not "a large gap between candidates"
            alt_ok, _ = _swept_on_all_legs(series, res, p.time, side)
            if alt_ok:
                alts.append(p)
        if alts:
            best = min(alts, key=lambda p: abs(p.price - anchor_px))
            out.append(
                f"R8 - the range {side} is anchored on {anchor_px:,.2f} "
                f"({' '.join(notes)}), which was NOT swept on every triad leg. A "
                f"materially different candidate that WAS swept on all legs exists: "
                f"{best.price:,.2f} @ {fmt_et(best.time)}. R8 prefers the all-legs-swept "
                "extreme even when it is less extreme - but 'looks false' is judgement, "
                "so the engine reports both and does NOT re-anchor. Decide by hand")
    return out


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
    # S1d
    outcome: Outcome | None = None
    shapes: list[dict] = field(default_factory=list)   # bounded markup spec
    stand_aside: str | None = None                     # R51, in plain words


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


def shape(tool: str, rule: str, label: str, pts: list[tuple[int, float]],
          colour: str = "#ffffff", extra: dict | None = None) -> dict:
    """One entry in the bounded-markup spec consumed by the drawing pass.

    Every shape carries BOTH ends of its time extent, because that extent is a claim
    (chart-markup §0b). `horizontal_line` is deliberately not among the tools emitted:
    an infinite line asserts the level applies at all times, which is what R6 and R7
    deny and what Paul rejected in S1c's markup.
    """
    assert tool in ("rectangle", "trend_line", "ray"), f"unbounded tool: {tool}"
    # A drawn object's time extent must run FORWARD. This guard exists because a
    # mitigation search anchored on the wrong bar produced 15 rectangles whose end
    # preceded their start, and nothing downstream would have complained — the chart
    # would simply have drawn something wrong. Raising here makes that class of bug
    # impossible to ship rather than merely unlikely.
    if len(pts) == 2 and pts[1][0] <= pts[0][0]:
        raise ValueError(
            f"non-increasing time extent for {rule} {label!r}: "
            f"{pts[0][0]} -> {pts[1][0]}. A bounded shape must end after it starts; "
            "check the mitigation/inversion anchor that produced these times.")
    return {
        "tool": tool, "rule": rule,
        # The [S1d] marker must survive onto the chart: a computed level must never be
        # mistakable for one of Paul's hand reads.
        "label": f"[S1d] {rule} {label}",
        "points": [{"time": int(t), "price": float(p)} for t, p in pts],
        "colour": colour, **(extra or {}),
    }


# chart-markup §Colour convention — fixed so two sessions are comparable at a glance.
C_RANGE = "#ffffff"      # range boundary: structural, neutral
C_ZONE = "#9e9e9e"       # discount / EQ / premium: zones should recede
C_SMT = "#ffeb3b"        # SMT-qualified swing: the load-bearing filter
C_SWING = "#757575"      # unqualified swing: provisional by definition
C_GAP = "#2196f3"        # gap (FVG/iFVG/NWOG/NDOG): what price is drawn to
C_LIQ = "#64b5f6"        # liquidity inside a gap: the precise target
C_ENTRY = "#4caf50"
C_STOP = "#f44336"
C_TARGET = "#4caf50"


def analyse_day(series, day: datetime, boundaries: dict | None = None) -> Record:
    day_str = day.strftime("%Y-%m-%d")
    t0, t1 = et_day_bounds(day)
    rec = Record(day=day_str, kind="REJECTION")
    boundaries = boundaries or {}

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
        rec.stand_aside = (
            "STAND ASIDE (R51) - no daily-cycle Sequential SMT was knowable before this "
            "session opened, so there is no confirmed level to trade from. R3 is the "
            "filter everything downstream leans on: an unqualified swing is provisional "
            "by definition, and taking one is trading a guess.")
        return rec

    # R7/R23: read the CURRENT state. The most recently knowable same-cycle SMT
    # retires every earlier one — a stale signal is not a signal.
    htf_events.sort(key=lambda e: (e.known_at, e.pivot_time))
    htf = htf_events[-1]
    rec.bias = htf.bias
    superseded = len([e for e in htf_events if e.known_at < htf.known_at])
    age_days = (t0 - htf.known_at) / 86400.0

    # ── R18/R27 (S1d): the WEEKLY rung. R18's canonical example is a weekly-cycle SMT
    # with a daily-cycle SMT nested inside it, and until the native W export existed
    # this pair could not be evaluated at all. Reported, not gated (WEEKLY_IS_A_GATE):
    # R18 is satisfied by any two adjacent cycles, so daily->4H remains legitimate, and
    # promoting weekly to a gate is a calibration decision only Paul can make.
    wk = series.get(CYCLE_WEEKLY, {}).get(PRIMARY)
    if wk is None:
        rec.branches.append(
            "R18/R27 - no weekly series in this export, so R18's CANONICAL nesting pair "
            "(weekly with daily inside) is NOT-VISIBLE rather than absent")
    else:
        wk_ev, _ = find_smt(series, CYCLE_WEEKLY, htf.side,
                            t0 - 604800 * CFG.weekly_lookback_weeks, t0, as_of=t0)
        if wk_ev:
            w = wk_ev[-1]
            rec.lines.append(Line("R18", f"WEEKLY-cycle SMT {w.side} {w.level:,.2f} @ "
                                         f"{fmt_et(w.pivot_time)}, diverging on "
                                         f"{', '.join(w.diverging)} (knowable "
                                         f"{fmt_et(w.known_at)}) - the daily SMT nests "
                                         "inside it, which is R18's CANONICAL pair"))
        else:
            rec.branches.append(
                f"R18 - no weekly-cycle SMT on this side in the "
                f"{CFG.weekly_lookback_weeks}-week lookback. The "
                "daily->4H nesting still satisfies R18, but this read does NOT have "
                "the canonical weekly-with-daily-inside structure, so treat it as the "
                "weaker of the two forms")
        if not wk_ev and CFG.weekly_is_a_gate:
            # AXIS: R18 canonical nesting promoted to a GATE (a calibration choice).
            rec.kind = "REJECTION"
            rec.failing_rule = "R18"
            rec.stand_aside = (f"R18 gated: no weekly-cycle SMT on this side within "
                               f"{CFG.weekly_lookback_weeks} weeks, so the canonical "
                               "weekly-with-daily-inside nesting is absent")
            return rec

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

    # ── MARKUP (S1d), bounded. Emitted here so a day that stands aside is still fully
    # marked up: "a real session is mostly markup and sitting on your hands", and an
    # artifact showing only the trade would teach the opposite.
    r_start = min(rng.move_from, rng.low_time, rng.high_time)
    r_end = rng.broken_by[2] if rng.broken_by else t1      # R6: terminate at the close
    r_tool = "trend_line" if rng.broken_by else "ray"      # §0b: bounded once it died
    for lvl, nm in ((rng.high, "range high"), (rng.low, "range low")):
        rec.shapes.append(shape(r_tool, "R4", f"{nm} {lvl:,.2f}",
                                [(r_start, lvl), (r_end, lvl)], C_RANGE))
    # M5 / R5: discount / EQ / premium as a box bounded to the RANGE'S SPAN, not the
    # whole chart. Fib 0 / 0.5 / 1 only — this model uses no quadrants.
    eq = (rng.high + rng.low) / 2.0
    rec.shapes.append(shape("rectangle", "R5", f"premium {eq:,.2f}-{rng.high:,.2f}",
                            [(r_start, eq), (r_end, rng.high)], C_ZONE))
    rec.shapes.append(shape("rectangle", "R5", f"discount {rng.low:,.2f}-{eq:,.2f}",
                            [(r_start, rng.low), (r_end, eq)], C_ZONE))
    rec.shapes.append(shape("trend_line", "R5", f"equilibrium {eq:,.2f}",
                            [(r_start, eq), (r_end, eq)], C_ZONE))
    # M2 / R3: the SMT-qualified swing, yellow, stopping where it was swept.
    rec.shapes.append(shape("trend_line", "R3",
                            f"SMT-qualified {htf.side} {htf.level:,.2f}",
                            [(htf.pivot_time, htf.level), (htf.taken_time, htf.level)],
                            C_SMT))

    # ── R8 (S1d): the false-sweep tiebreak, on the RANGE ANCHORS (not the SMT pivot —
    # see r8_anchor_check for why that first attempt was wrong). Silence here means R8
    # has nothing to say, which is the common case.
    for line in r8_anchor_check(series, CYCLE_FRAMING, rng, t0):
        rec.unresolved.append(line)

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
        # Draw WHERE it died — the whole point of bounding a range at its invalidating
        # close is that the chart then shows the kill, not a level floating onwards.
        rec.shapes.append(shape("trend_line", "R6", f"invalidating close {px:,.2f}",
                                [(when, px), (min(when + 86400 * 2, t1), px)], C_STOP))
        rec.stand_aside = (
            f"STAND ASIDE (R51) - the framed range died on {fmt_et(when)} when a candle "
            f"closed {how.split()[1]} the boundary at {px:,.2f}. R7 says wait for the next "
            "Sequential SMT to anchor a new range; there is nothing to trade against a "
            "dead range, and trading one is how the 1.22-of-range entries in S1c happened.")
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
        rec.stand_aside = (
            "STAND ASIDE (R51) - there is a daily SMT but it is not SEQUENTIAL: no 4H "
            "confirmation and no 15m Sequential Skip. Ordinary SMT is not the signal; "
            "R18's edge is cross-cycle alignment, and a single-cycle divergence is the "
            "thing that looks like the setup without being it.")
        return rec

    # ── R21 (S1d): confirmation by a gap on the cycle PAIRED with the driving SMT's.
    pairing = r21_gap_pairing(series, CYCLE_FRAMING,
                             "bullish" if htf.bias == "LONG" else "bearish",
                             htf.pivot_time, t0)
    if pairing and pairing.startswith("R21 - paired"):
        rec.lines.append(Line("R21", pairing.removeprefix("R21 - ")))
    elif pairing:
        rec.branches.append(pairing)     # absence is reportable, not disqualifying

    # ── R30: the 5m iFVG entry, scanned forward through the declared entry window.
    (wh0, wm0), (wh1, wm1) = ENTRY_WINDOW_ET
    win_lo = int(datetime(day.year, day.month, day.day, wh0, wm0, tzinfo=ET).timestamp())
    win_hi = int(datetime(day.year, day.month, day.day, wh1, wm1, tzinfo=ET).timestamp())
    fvgs, fvg_below_floor = find_fvgs(entry_s, max(e_lo - 60, 0), e_hi)
    if fvg_below_floor:
        rec.branches.append(
            f"R11 - {fvg_below_floor} candidate FVG(s) were EXCLUDED for being under the "
            f"declared {FVG_MIN_TICKS:g}-tick size floor. Stated rather than silently "
            "dropped: a one-tick gap is the instrument's granularity, not a PD array, "
            "but the floor is a declared choice and R11 does not name a minimum")
    want = "bullish" if htf.bias == "LONG" else "bearish"

    # ── R11 (S1d): NWOG / NDOG, on the MEASURED per-symbol session boundary. Declared
    # in S1c and left unimplemented because the boundary was unknown; it is now
    # measured rather than assumed, and for a symbol with no measurable daily halt the
    # engine emits none rather than inventing them.
    bnd = boundaries.get(PRIMARY, {})
    opening = find_opening_gaps(entry_s, bnd, max(e_lo - 300, 0), e_hi)
    zone_wanted = "DISCOUNT" if htf.bias == "LONG" else "PREMIUM"
    for g in opening:
        attach_mitigation(g, entry_s, t1 - 1)
        in_zone = rng.zone((g.low + g.high) / 2.0)
        rec.lines.append(Line("R11", f"{g.kind} {g.low:,.2f}-{g.high:,.2f} formed "
                                     f"{fmt_hm(g.formed_time, day_str)} ({g.direction}, in "
                                     f"{in_zone}"
                                     + (f", mitigated {fmt_hm(g.mitigated_time, day_str)}"
                                        if g.mitigated_time else ", still unmitigated")
                                     + ")"))
        # M6 boxes PD arrays in the range's discount (long) / premium (short). Every
        # opening gap is drawn regardless, because a marked-up session shows the
        # structure that was REJECTED too — but the zone is on the label, so a gap on
        # the wrong side of equilibrium cannot be mistaken for a candidate.
        rec.shapes.append(shape(
            "rectangle", "R11", f"{g.kind} {g.low:,.2f}-{g.high:,.2f} [{in_zone}]",
            [(g.formed_time, g.low),
             (g.mitigated_time or min(t1, entry_s.times[-1]), g.high)], C_GAP))
    if not opening:
        if bnd.get("daily") is None:
            rec.branches.append(
                f"R11 - no NDOG computable for {PRIMARY}: no daily session boundary is "
                "MEASURABLE in this data (a symbol that trades near-continuously has no "
                "daily opening gap). NOT-MEASURABLE, not zero")
        else:
            rec.branches.append(
                f"R11 - no NWOG/NDOG cleared the {OPENING_GAP_MIN_TICKS:g}-tick floor at "
                f"the measured {bnd['daily']['close_et']}->{bnd['daily']['open_et']} ET "
                "session boundary")

    ifvgs = [g for g in invert_gaps(entry_s, fvgs, t1 - 1)
             if g.direction == want and g.inverted_time is not None]
    if not ifvgs:
        rec.failing_rule = "R30"
        rec.lines.append(Line("R30", f"no {want} 5m iFVG formed in the session - "
                                     "the preferred entry never presented"))
        rec.stand_aside = (
            f"STAND ASIDE (R51) - the framing and confirmation held ({htf.bias} bias), but "
            f"the preferred entry never presented: no {want} 5m iFVG formed all session. "
            "R30 names the iFVG as the entry; without one there is no trade to take, and "
            "manufacturing one from a plain FVG in a hurry is the failure R51 exists for.")
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
        rec.stand_aside = (
            f"STAND ASIDE (R51) - {len(ifvgs)} {want} 5m iFVG(s) did form, but none was "
            f"retested inside the {wh0:02d}:{wm0:02d}-{wh1:02d}:{wm1:02d} ET window, so "
            "there was never an entry trigger. The setup existed and the entry did not; "
            "chasing a gap that never came back is the pre-9:30 failure R31 warns about.")
        return rec

    gap, ei = entry
    # R13 (S1d): the zoom-in route needs a finer series, which is what the 1m export is
    # for. R28 keeps 1m out of signal detection, but using it to LOCATE a level R12
    # already says is the target is exactly R13's "zoom in until a lower-TF swing
    # appears inside the same gap".
    attach_liquidity(gap, entry_s, entry_s.times[ei],
                     finer=series.get(CYCLE_FINE, {}).get(PRIMARY))
    entry_px = gap.high if htf.bias == "LONG" else gap.low
    entry_t = entry_s.times[ei]

    # ── M6 MARKUP of the PD arrays, split by WHAT WAS KNOWABLE AT THE ENTRY DECISION.
    # This is a correctness split, not a tidying one. An iFVG that inverted at 14:00
    # cannot have informed an 08:05 entry, so drawing it in the same colour as the
    # decision context puts hindsight on the chart that justifies the trade — which is
    # the visual form of the lookahead bug that contaminated 75% of S1c's output.
    # Zone filter per M6: box gaps in the range's discount (long) / premium (short).
    n_post = 0
    for g in ifvgs:
        attach_mitigation(g, entry_s, t1 - 1)
        if rng.zone((g.low + g.high) / 2.0) != zone_wanted:
            continue
        inv_t = g.inverted_time or g.formed_time
        is_the_one = (g.low == gap.low and g.high == gap.high
                      and g.inverted_time == gap.inverted_time)
        if inv_t > entry_t and not is_the_one:
            n_post += 1
            continue      # counted and reported below, never drawn as decision context
        rec.shapes.append(shape(
            "rectangle", "R11",
            (f"** TRADED iFVG ** {g.low:,.2f}-{g.high:,.2f} [{zone_wanted}]" if is_the_one
             else f"iFVG {g.low:,.2f}-{g.high:,.2f} [{zone_wanted}]"),
            [(inv_t, g.low),
             (g.mitigated_time or min(t1, entry_s.times[-1]), g.high)],
            C_GAP, {"traded": is_the_one}))
    if n_post:
        rec.branches.append(
            f"R11 - {n_post} further {want} iFVG(s) in {zone_wanted} inverted AFTER the "
            f"{fmt_hm(entry_t, day_str)} entry and are deliberately NOT drawn: they could "
            "not have informed the decision, and drawing them would put hindsight on the "
            "chart that justifies the trade. Counted here rather than dropped silently")

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
        rec.stand_aside = (
            f"STAND ASIDE (R51) - the invalidation level sits on the WRONG SIDE of the "
            f"entry for a {htf.bias}, so no stop can be placed. R29 requires knowing what "
            "would prove the idea wrong before taking it; a trade with no definable "
            "invalidation is a position, not a trade.")
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
        rec.stand_aside = (
            f"STAND ASIDE (R51) - the range extreme this {htf.bias} would target has already "
            "been taken, so there is no draw on liquidity left in the bias direction. "
            "Entering anyway means holding a position with nothing to aim at - and note "
            "an abs() bug once rendered exactly this case as a plausible 0.7R.")
        return rec
    rr = reward / risk if risk else 0.0

    # AXIS 4 (S1e). R30 says discount (long) / premium (short) "of the LTF range";
    # the engine has always measured against the driving HTF range. Which one the
    # rule means changes 56% of S1e's entries, so it is a configured axis, not a
    # silent choice.
    zone_rng = rng
    zone_basis = "HTF"
    if CFG.zone_ref == "ltf":
        ltf_rng = frame_range(entry_s, as_of=entry_t)
        if ltf_rng is not None:
            zone_rng, zone_basis = ltf_rng, "LTF"
        else:
            rec.branches.append(
                "R30/R32 - LTF range requested for the discount/premium read but no "
                "LTF range could be framed at the entry; fell back to the HTF range")
    pos = zone_rng.position(entry_px)
    zone = zone_rng.zone(entry_px)

    # ── Enforcement axes: preferences the engine has always merely reported.
    want_zone_gate = "DISCOUNT" if htf.bias == "LONG" else "PREMIUM"
    if CFG.enforce_zone and zone != want_zone_gate:
        rec.kind = "REJECTION"
        rec.failing_rule = "R32"
        rec.stand_aside = (
            f"R30/R32 gated: entry is in {zone} ({pos:.2f} of the {zone_basis} range) "
            f"but a {htf.bias} requires {want_zone_gate}")
        return rec
    if CFG.min_planned_rr > 0.0 and rr < CFG.min_planned_rr:
        rec.kind = "REJECTION"
        rec.failing_rule = "R45"
        rec.stand_aside = (
            f"R45 gated: planned reward:risk is {rr:.2f}:1, below the required "
            f"{CFG.min_planned_rr:g}:1 - risking a full R to make a fraction of one")
        return rec

    rec.kind = "SETUP"

    # ── Is this the FIRST retest of the inverted zone, or a later one? The entry scan is
    # confined to the 08:00-16:00 ET window, so a touch that happened overnight is
    # invisible to it — and the engine would present a second or third touch as though it
    # were the trigger. R30 says the entry is "the" retest without saying which, so this
    # is reported as a branch rather than resolved: whether a re-tested zone is still
    # valid is a judgement, and silently taking the later touch makes the entry look
    # cleaner than it was.
    first_touch = gap.mitigated_time
    # AXIS 3 (S1e). 90% of S1e's entries were NOT the first retest, because the
    # 08:00-16:00 scan cannot see an overnight touch. The three readings of R30:
    #   report        - take it, say an earlier touch existed (pre-S1e behaviour)
    #   require_first - an earlier touch consumes the entry; stand aside
    #   session_first - an OVERNIGHT touch does not consume it; the NY session gets
    #                   its own first touch (a touch inside the window still does)
    if first_touch is not None and first_touch < entry_t:
        if CFG.retest_mode == "require_first":
            rec.kind = "REJECTION"
            rec.failing_rule = "R30"
            rec.stand_aside = (
                f"R30 gated: price first returned to the inverted zone at "
                f"{fmt_hm(first_touch, day_str)}, so the {fmt_hm(entry_t, day_str)} "
                "touch taken here would be a LATER retest, not the retest")
            return rec
        if CFG.retest_mode == "session_first" and first_touch < win_lo:
            first_touch = None           # overnight touch; the session's is the first
    if first_touch is not None and first_touch < entry_t:
        rec.branches.append(
            f"R30 - this is NOT the first retest of the inverted zone. Price first "
            f"returned to it at {fmt_hm(first_touch, day_str)}, OUTSIDE the "
            f"{ENTRY_WINDOW_ET[0][0]:02d}:{ENTRY_WINDOW_ET[0][1]:02d}-"
            f"{ENTRY_WINDOW_ET[1][0]:02d}:{ENTRY_WINDOW_ET[1][1]:02d} ET entry window, so "
            f"the {fmt_hm(entry_t, day_str)} touch taken here is a LATER one. R30 does not "
            "say whether a re-tested iFVG is still a valid entry - decide by hand, and note "
            "the window is what made the earlier touch invisible to the scan")

    rec.lines.append(Line("R5", f"entry in {zone} ({pos:.2f} of {zone_basis} range)"))
    rec.lines.append(Line("R30", f"5m iFVG {gap.low:,.2f}-{gap.high:,.2f} "
                                 f"(formed {fmt_hm(gap.formed_time, day_str)}, inverted "
                                 f"{fmt_hm(gap.inverted_time, day_str)}), retested {fmt_hm(entry_t, day_str)}"))
    if gap.liquidity is not None:
        rec.lines.append(Line("R12", f"liquidity inside the gap {gap.liquidity:,.2f} "
                                     f"@ {fmt_hm(gap.liquidity_time, day_str)} - this is the precise "
                                     f"target, not the gap boundary  [found: {gap.liquidity_source}]"))
        if gap.liquidity_note:
            rec.branches.append(gap.liquidity_note)
        # R12's target is a REGION's internal level: a short bounded segment inside the
        # box, never a line across the chart.
        rec.shapes.append(shape("trend_line", "R12", f"liquidity {gap.liquidity:,.2f}",
                                [(gap.formed_time, gap.liquidity),
                                 (gap.mitigated_time or entry_t, gap.liquidity)], C_LIQ))
    else:
        rec.unresolved.append(gap.liquidity_note)
    rec.lines.append(Line("R33", f"stop {stop_px:,.2f}  ·  risk {risk:,.2f} pts "
                                 f"(invalidation = the swept {htf.side} extreme of the "
                                 f"qualifying {qual.cycle} SMT @ {fmt_et(qual.pivot_time)})"))
    rec.lines.append(Line("R35", f"target {target_px:,.2f} (range extreme)  ·  {rr:.1f}R "
                                 "PLANNED"))
    rec.lines.append(Line("R43", f"risk expressed in R: 1R = {risk:,.2f} pts; "
                                 f"expectancy needs win% AND R:R together (R44)"))

    # ── R22 (S1d): the extreme of the LARGER cycle segment containing the SMT. Reported
    # beside R35's range extreme, never swapped in — two valid targets is a judgement
    # R22 does not settle, and silently taking the nearer one would flatter the R:R.
    alt = r22_larger_segment_extreme(series, CYCLE_WEEKLY, htf.side, htf.pivot_time, t0)
    if alt:
        alt_px, alt_t, alt_cyc = alt
        alt_reward = (alt_px - entry_px) if htf.bias == "LONG" else (entry_px - alt_px)
        if abs(alt_px - target_px) < prim_tick_of(series, CYCLE_ENTRY):
            # Honest bookkeeping: when the larger segment's extreme IS the range extreme,
            # R22 has added nothing. Printing "an alternative target" that is the same
            # price would manufacture a second, independent-looking confirmation.
            rec.lines.append(Line("R22", f"larger-segment ({alt_cyc}) extreme is the SAME "
                                         f"level as R35's target ({alt_px:,.2f}) - the "
                                         "range low was made inside that weekly segment, "
                                         "so R22 adds NO independent target here"))
        elif alt_reward > 0:
            rec.lines.append(Line("R22", f"larger-segment ({alt_cyc}) extreme {alt_px:,.2f} "
                                         f"@ {fmt_et(alt_t)} -> {alt_reward / risk:.1f}R. "
                                         "R22 expects this to be taken eventually; it is "
                                         "an ALTERNATIVE target to R35's range extreme, "
                                         "not a replacement"))
        else:
            rec.branches.append(
                f"R22 - the {alt_cyc} segment extreme {alt_px:,.2f} lies BEHIND entry, so "
                "R22 offers no additional target here")

    # ── OUTCOME (S1d). Everything above is a plan; this is what price did.
    oc = simulate_outcome(series, htf.bias, entry_t, entry_px, stop_px, target_px)
    rec.outcome = oc
    verdict_txt = {
        "TARGET": f"TARGET first at {fmt_et(oc.at_time)} -> realised "
                  f"{oc.realised_r:+.2f}R" if oc.at_time else "TARGET",
        "STOP": f"STOP first at {fmt_et(oc.at_time)} -> realised "
                f"{oc.realised_r:+.2f}R" if oc.at_time else "STOP",
    }.get(oc.verdict, f"{oc.verdict} - {oc.note}")
    # MFE/MAE are magnitudes of excursion FOR and AGAINST the position, both reported
    # unsigned in R — a trade that ran 1.2R in favour before resolving is a different
    # lesson from one that never moved, and the plan alone cannot show that.
    rec.lines.append(Line("OUT", f"{verdict_txt}  (walked {oc.res}m, {oc.bars_walked} bars; "
                                 f"MFE {oc.mfe_r:.2f}R in favour · MAE {oc.mae_r:.2f}R against)"))
    if oc.realised_r is None:
        rec.unresolved.append(
            f"OUTCOME {oc.verdict} - there is NO realised R for this trade. "
            "MFE/MAE are reported so the excursion is visible, but they are NOT a result: "
            "an unresolved trade must never be counted as a win, a loss or a breakeven.")

    # Execution objects, bounded to the TRADE'S lifetime (§0b) — not the whole session.
    t_end = oc.at_time or oc.last_bar or min(t1, entry_s.times[-1])
    for px, rule, nm, col in ((entry_px, "R30", "entry", C_ENTRY),
                              (stop_px, "R33", "stop", C_STOP),
                              (target_px, "R35", "target", C_TARGET)):
        rec.shapes.append(shape("trend_line", rule, f"{nm} {px:,.2f}",
                                [(entry_t, px), (t_end, px)], col))
    # M12 / R29: the invalidation written ON the chart, not only in your head.
    rec.shapes.append(shape("trend_line", "R29",
                            f"invalidation: close beyond {stop_px:,.2f} kills this "
                            f"{htf.bias}",
                            [(entry_t, stop_px), (t_end, stop_px)], C_STOP,
                            {"is_text_note": True}))

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

def render(records: list[Record], series, meta, span, argv_note: str,
           selection_basis: str | None = None) -> str:
    t_from, t_to = span
    out: list[str] = []
    w = out.append

    w(f"# Aura Sequential-SMT — computed setups (engine {ENGINE_VERSION})")
    w("")
    w("> ## ⚠️ MACHINE-GENERATED — NOT A TRAINING RECORD")
    w("> These setups were computed by a script from exported bars. They are **not**")
    w("> Paul's reps. They must never touch the evidence layer: no `evidence_assets`,")
    w("> no rep credit, nothing feeding the streak, the calibration score or the")
    w("> Readiness Gate. A tutorial artifact is not a training record.")
    w("")

    # ── THE SELECTION BASIS, FIRST AND LOUD. A span chosen BECAUSE it contains a setup
    #    carries no information about how often setups occur, and a reader who infers a
    #    frequency from it has been misled by the artifact rather than by their own
    #    carelessness. So it is printed before any number.
    w("> ## ⛔ HOW THIS SPAN WAS CHOSEN — read before reading any number")
    if selection_basis:
        for ln in selection_basis.split("\n"):
            w(f"> {ln}")
    else:
        w("> **⚠️ SELECTION BASIS NOT DECLARED.** This run was produced without stating")
        w("> how its span was chosen, so nothing in it supports any claim about")
        w("> frequency, hit rate or expectancy. Re-run with `--selection-basis`.")
    w("")
    w(f"Generated by `api/scripts/aura_setup_engine.py` — {argv_note}")
    w("")

    w("## The sample this ran on")
    w("")
    w(f"- **Source:** {meta.get('source')}")
    w(f"- **Session URL:** {meta.get('session_url')}")
    w(f"- **Extracted via:** `{meta.get('extracted_via')}`")
    w(f"- **Declared span:** {t_from.strftime('%Y-%m-%d')} → {t_to.strftime('%Y-%m-%d')} (ET)")
    if meta.get("sources"):
        w(f"- **Export files merged:** "
          + ", ".join(f"`{s['file']}`" for s in meta["sources"]))
    if meta.get("collisions"):
        w("- **⚠️ Series overwritten during merge:** " + "; ".join(meta["collisions"]))
    w("")
    w("| Resolution | Symbol | Bars | First bar (UTC) | Last bar (UTC) | Measured tick |")
    w("|---|---|---:|---|---|---:|")
    for res in ["W", "D", "240", "60", "15", "5", "1"]:
        for sym, s in series.get(res, {}).items():
            w(f"| {res} | {sym} | {len(s)} | "
              f"{datetime.fromtimestamp(s.times[0], timezone.utc):%Y-%m-%d %H:%M} | "
              f"{datetime.fromtimestamp(s.times[-1], timezone.utc):%Y-%m-%d %H:%M} | "
              f"{s.tick:g} |")
    w("")

    # ── The measured session boundaries R11 needs. Printed because "measured" is only
    #    a meaningful claim if the measurement is visible and checkable.
    bnds = meta.get("session_boundaries") or {}
    if bnds:
        w("### Session boundaries — MEASURED per symbol, never assumed (R11)")
        w("")
        w("| Symbol | Measured at | Daily close→open (ET) | Support | Weekly close→open (ET) |")
        w("|---|---|---|---:|---|")
        for sym, b in bnds.items():
            d, k = b.get("daily"), b.get("weekly")
            w(f"| {sym} | {b.get('measured_at_res') or '—'}m | "
              + (f"{d['close_et']}→{d['open_et']}" if d else "**NOT-MEASURABLE**") + " | "
              + (f"{d['support']:.0%}" if d else "—") + " | "
              + (f"{k['close_et']}→{k['open_et']}" if k else "**NOT-MEASURABLE**") + " |")
        w("")
        w("**`NOT-MEASURABLE` is a result, not a gap in the table.** A symbol that trades")
        w("near-continuously has no daily opening gap, so it gets no NDOGs rather than")
        w("invented ones — which is exactly why S1c declined to implement R11's NWOG/NDOG")
        w("at all. An earlier version of this measurement mis-classified CHFUSD's")
        w("Friday→Sunday **weekend** break as its daily boundary, at 75% support; daily and")
        w("weekly breaks are now separated by calendar days skipped, not by gap length.")
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
    w(f"- **Weekly rung (R18/R27):** present, and **reported not gated** "
      f"(`WEEKLY_IS_A_GATE = {WEEKLY_IS_A_GATE}`). R18 is satisfied by any two adjacent "
      "cycles, so daily→4H stays legitimate; whether weekly confirmation should become a "
      "gate is a calibration question only Paul's review can answer, and the engine "
      "declines to answer it for him.")
    w(f"- **NWOG/NDOG floor (R11):** {OPENING_GAP_MIN_TICKS:g} ticks, against a "
      "**measured** per-symbol session boundary (table above)")
    w(f"- **FVG size floor (R11):** {FVG_MIN_TICKS:g} ticks. S1c had **none**, so a "
      "one-tick gap was an entry candidate on equal footing with a six-tick one — the "
      "same defect class as phantom SMT, and the reason a single session drew 27 "
      "rectangles. R11 names no minimum, so this is a declared choice; the count "
      "excluded is reported per day rather than dropped silently, and the S1c result is "
      "**unchanged** by it (that entry gap is 6 ticks wide).")
    w(f"- **Outcome walk:** resolutions tried in order {OUTCOME_RESOLUTIONS} — finest "
      "first, so an in-bar ambiguity is retried at higher resolution before it is "
      "declared unresolvable. The sequence inside a bar is never guessed.")
    w(f"- **1m bars are for OUTCOME SEQUENCING ONLY** "
      f"(`FINE_RES_IS_SIGNAL_CYCLE = {FINE_RES_IS_SIGNAL_CYCLE}`) — R28 makes a "
      "1-minute microcycle divergence explicitly low-influence, so scanning 1m for "
      "signals would contradict the rulebook.")
    w(f"- **R8 material gap:** {R8_MATERIAL_GAP_FRACTION:.0%} — the sweep-consistency "
      "check is measured and reported; the re-anchoring decision is left to Paul")
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

    # ── Outcomes. Kept separate from the plan, and never collapsed into a rate.
    with_oc = [r for r in setups if r.outcome]
    if with_oc:
        w("### Outcomes — what price actually did")
        w("")
        w("| Day | Bias | Verdict | Realised R | MFE (R) | MAE (R) | Walked |")
        w("|---|---|---|---:|---:|---:|---|")
        for r in with_oc:
            o = r.outcome
            w(f"| {r.day} | {r.bias} | {o.verdict} | "
              + (f"{o.realised_r:+.2f}" if o.realised_r is not None else "**none**")
              + f" | {o.mfe_r:.2f} | {o.mae_r:.2f} | {o.res}m × {o.bars_walked} |")
        w("")
        unres = [r for r in with_oc if r.outcome.realised_r is None]
        if unres:
            w(f"**⚠️ {len(unres)} of {len(with_oc)} entr"
              + ("y has" if len(with_oc) == 1 else "ies have")
              + " NO realised R.** An unresolved trade is not a breakeven and not a")
            w("loss. It must not be counted in any win rate, and MFE/MAE are excursion")
            w("measurements rather than results.")
            w("")
        w("**No hit rate, win rate or expectancy is computed here, and none may be")
        w("quoted from this run.** Expectancy needs `(win% × avg win R) − (loss% × avg")
        w("loss R)` (R44) over a sample that was not chosen for its contents — this one")
        w("was. See the selection basis at the top.")
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
            w(f"  MARKUP: {len(r.shapes)} bounded shapes emitted")
            w("```")
            w("")

    w("## Rejections and stand-asides")
    w("")
    w("> R51: **missing a trade is discipline, not a loss.** Each day below carries the")
    w("> reason in plain words, because \"REJECTED at R6\" teaches nothing on its own —")
    w("> the point of a stand-aside record is that Paul can check whether he agrees.")
    w("")
    for r in rejects:
        w("```")
        w(f"{r.day} · REJECTED at {r.failing_rule}")
        for ln in r.lines:
            w(f"  {ln.rule:<4} {ln.text}")
        for u in r.unresolved:
            w(f"  UNRESOLVED: {u}")
        for b in r.branches:
            w(f"  BRANCH: {b}")
        if r.shapes:
            w(f"  MARKUP: {len(r.shapes)} bounded shapes emitted")
        w("```")
        if r.stand_aside:
            w("")
            w(f"> {r.stand_aside}")
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
    ap.add_argument("--bars", required=True, type=Path, action="append",
                    help="export file; repeat to merge several (S1c D/240/60/15/5 + "
                         "S1d weekly + S1d 1m)")
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--shapes", action="store_true",
                    help="also emit the bounded-markup shape spec for the drawing pass")
    ap.add_argument("--selection-basis", default=None,
                    help="HOW this span was chosen. Omitting it prints a visible warning "
                         "in the report, because a span chosen because it contains a setup "
                         "carries no information about frequency and the reader must be "
                         "told which kind of span this is.")
    # ── S1e configuration axes (see the Config dataclass). Defaults reproduce the
    # pre-S1e behaviour exactly; the S1c regression is the proof.
    ap.add_argument("--aura-asset-all-cycles", action="store_true",
                    help="R17 AXIS: read the Aura Asset at every cycle on its own "
                         "calendar, instead of refusing it at daily/weekly")
    ap.add_argument("--weekly-lookback-weeks", type=int, default=12,
                    help="R18 AXIS: weeks of lookback for the weekly-cycle SMT")
    ap.add_argument("--retest-mode", default="report",
                    choices=["report", "require_first", "session_first"],
                    help="R30 AXIS: how an earlier retest of the inverted zone is treated")
    ap.add_argument("--aura-asset-join", default="timestamp",
                    choices=["timestamp", "session_date"],
                    help="R17 AXIS: join the Aura Asset on exact timestamps (which "
                         "never match at D/W) or on the ET session bucket")
    ap.add_argument("--zone-ref", default="htf", choices=["htf", "ltf"],
                    help="R30/R32 AXIS: which range discount/premium is measured against")
    ap.add_argument("--enforce-zone", action="store_true",
                    help="gate on R30/R32 instead of reporting it")
    ap.add_argument("--min-planned-rr", type=float, default=0.0,
                    help="R45 gate: minimum planned reward:risk (0 disables)")
    ap.add_argument("--weekly-is-a-gate", action="store_true",
                    help="R18 gate: require the canonical weekly-with-daily nesting")
    a = ap.parse_args()

    global CFG
    CFG = Config(
        aura_asset_all_cycles=a.aura_asset_all_cycles,
        weekly_lookback_weeks=a.weekly_lookback_weeks,
        retest_mode=a.retest_mode,
        zone_ref=a.zone_ref,
        aura_asset_join=a.aura_asset_join,
        enforce_zone=a.enforce_zone,
        min_planned_rr=a.min_planned_rr,
        weekly_is_a_gate=a.weekly_is_a_gate,
    )

    series, meta = load_bars(a.bars)
    meta["s1e_config"] = asdict(CFG)
    meta["s1e_config_label"] = CFG.label()
    d0 = datetime.strptime(a.t_from, "%Y-%m-%d")
    d1 = datetime.strptime(a.t_to, "%Y-%m-%d")

    # Session boundaries are MEASURED once, per symbol, before any rule runs — R11's
    # NWOG/NDOG are undefined without them and S1c refused to guess.
    boundaries = {sym: measure_session_boundary(series, sym)
                  for sym in [PRIMARY] + TRIAD_LEGS + [AURA_ASSET]}
    meta["session_boundaries"] = boundaries

    records: list[Record] = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:      # Mon-Fri; weekend days are not sessions
            records.append(analyse_day(series, d, boundaries))
        d += timedelta(days=1)

    argv_note = (f"--bars {' --bars '.join(p.name for p in a.bars)} "
                 f"--from {a.t_from} --to {a.t_to}  (engine {ENGINE_VERSION})")
    md = render(records, series, meta, (d0, d1), argv_note, a.selection_basis)

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "computed-setups.md").write_text(md, encoding="utf-8")
    (a.out / "computed-setups.json").write_text(json.dumps({
        "engine_version": ENGINE_VERSION,
        "declared_span": {"from": a.t_from, "to": a.t_to},
        "session_boundaries": boundaries,
        "records": [
            {
                "day": r.day, "kind": r.kind, "bias": r.bias,
                "failing_rule": r.failing_rule, "stand_aside": r.stand_aside,
                "lines": [{"rule": ln.rule, "text": ln.text} for ln in r.lines],
                "unresolved": r.unresolved, "branches": r.branches,
                "outcome": (None if r.outcome is None else {
                    "verdict": r.outcome.verdict, "res": r.outcome.res,
                    "at_time": r.outcome.at_time, "realised_r": r.outcome.realised_r,
                    "mfe_r": r.outcome.mfe_r, "mae_r": r.outcome.mae_r,
                    "bars_walked": r.outcome.bars_walked, "note": r.outcome.note,
                }),
                "shapes": r.shapes,
            } for r in records
        ],
    }, indent=2), encoding="utf-8")

    if a.shapes:
        spec = {
            "engine_version": ENGINE_VERSION,
            "marker": "[S1d]",
            "quarantine": ("MACHINE-GENERATED tutorial markup. Every shape carries the "
                           "[S1d] marker. Must be REMOVED before Paul marks this week by "
                           "hand — pre-drawn levels turn a markup rep into tracing."),
            "primitives_note": ("Bounded shapes only: rectangles / rays / bounded "
                                "segments with computed start AND end. No horizontal_line "
                                "— an infinite line asserts the level applies at all "
                                "times, which R6 and R7 deny (chart-markup §0b)."),
            "days": [{"day": r.day, "kind": r.kind, "shapes": r.shapes}
                     for r in records if r.shapes],
        }
        # DEDUPE for the drawing pass. Four consecutive stand-aside days framed the same
        # dead range, so drawing each day's set would stack four pixel-identical copies
        # — indistinguishable on the chart, and four times the cleanup risk. Deduping by
        # (tool, label, points) keeps one of each and records which days shared it, so
        # nothing is lost from the per-day record.
        seen: dict[str, dict] = {}
        for r in records:
            for sh in r.shapes:
                key = json.dumps([sh["tool"], sh["label"], sh["points"]], sort_keys=True)
                if key in seen:
                    seen[key]["days"].append(r.day)
                else:
                    seen[key] = {**sh, "days": [r.day]}
        spec["draw"] = list(seen.values())
        spec["draw_note"] = (
            f"{len(seen)} DISTINCT shapes de-duplicated from "
            f"{sum(len(r.shapes) for r in records)} per-day shapes. Each carries the days "
            "it applies to. Draw this list, not the per-day lists.")
        (a.out / "chart-shapes-spec.json").write_text(json.dumps(spec, indent=1),
                                                      encoding="utf-8")
        n_sh = sum(len(r.shapes) for r in records)
        print(f"shape spec: {n_sh} bounded shapes -> {a.out / 'chart-shapes-spec.json'}")

    n_set = sum(1 for r in records if r.kind == "SETUP")
    print(f"{len(records)} days · {n_set} setups · {len(records) - n_set} rejections")
    print(f"-> {a.out / 'computed-setups.md'}")


if __name__ == "__main__":
    main()
