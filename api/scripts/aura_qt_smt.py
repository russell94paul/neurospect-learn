#!/usr/bin/env python
"""
Sequential SMT, rebuilt on the QUARTERLY-THEORY SEGMENT model (S1e-b, 2026-08-15).

    python api/scripts/aura_qt_smt.py --bars api/docs/evidence/s1e/bars/packed \
        --from 2025-05-01 --to 2025-05-30 --out api/docs/evidence/s1e/qt

⭐ WHY THIS EXISTS — two corrections from Paul's QT[✦] Pine indicators
   (see api/docs/evidence/s1e/reference/README.md for the verbatim excerpts).

1. THE CYCLES ARE SEGMENTS, NOT TIMEFRAMES.
   `aura_setup_engine.py` mapped Aura's cycles onto chart timeframes (W/D/240/60/15/5).
   The indicator does not. A cycle's NAME is the CONTAINER and the comparison runs
   between its four (or seven) SEGMENTS:

       Daily   -> the four 6-hour quarters of the day (day starts 18:00 NY)
       Weekly  -> the days within the week
       Monthly -> the weeks within the month
       90m     -> the four 90-minute quarters inside a 6-hour session
       Micro   -> the four 22.5-minute quarters inside a 90m

   This is rule 22 read literally: "if SMT occurred BETWEEN TWO SEGMENTS of a larger
   cycle, expect the extreme of that larger segment to be taken."

   ⭐ It is almost certainly why S1e reported "no weekly-cycle SMT" on 91% of entries:
   we hunted 3-candle pivots on WEEKLY BARS over a 12-week lookback. Under the segment
   model a weekly-cycle SMT is available every week — it is the days inside it.

2. SMT IS SEGMENT-EXTREME DIVERGENCE, NOT PIVOT SWEEPING.
   Verbatim from the indicator:

       _bear0 = ((ah1 >= ah0 and bh1 <= bh0) or (ah1 <= ah0 and bh1 >= bh0)) and not(...)
       _bull0 = ((al1 <= al0 and bl1 >= bl0) or (al1 >= al0 and bl1 <= bl0)) and not(...)

   ah1/ah0 = the primary's highest high in the PREVIOUS vs CURRENT segment;
   bh1/bh0 = the same on the comparison asset. So: one asset made a higher high while
   the other made a lower high, segment over segment. No pivot. No forward window.
   No sweep. The old engine required all three.

⭐ A FREE CONSEQUENCE: bucketing by session segment needs no timestamp join, so the Aura
Asset participates naturally. CHFUSD shares 0 of NQ's 3,794 daily timestamps, which made
it permanently NOT-VISIBLE under the old exact-timestamp join (100% of S1e's setups).

⛔ WHAT THIS SCRIPT IS NOT
- Not a claim that the indicator IS Aura. It is Enigma's Quarterly-Theory tooling. It
  settles MECHANICS; only Paul and the videos settle what a rule MEANS.
- Not a replacement for `aura_setup_engine.py` yet. It is a second, independent detector
  whose output is meant to be COMPARED with the old one and with the chart.
- Not gated on outcomes. Paul's priority (2026-08-15) is that the LEVELS are right —
  entries, SSMTs, range/premium/discount, FVG/iFVG — not the P&L.
"""

from __future__ import annotations

import argparse
import json
from bisect import bisect_left
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

PRIMARY = "NQ"
TRIAD_LEGS = ["ES", "YM"]
AURA_ASSET = "CHFUSD"          # 6S proxy; the indicator's default quad is CME:6S1!

# ⚠ The indicator's SSMT block uses a FIXED 'UTC-4' offset by default, while its
# QT-cycles block uses DST-aware 'America/New_York'. In winter those differ by an hour,
# which SHIFTS THE 18:00 DAY START and therefore every segment boundary. We default to
# DST-aware NY because the futures session itself follows NY DST — but this is a real,
# declared divergence from the indicator's default, not an oversight.
DAY_START_HOUR = 18

# The bar resolution segments are built from. 90m = 18x5m and 6h = 72x5m divide exactly.
# ⚠ MICRO (22.5m) IS NOT BUILDABLE FROM 5m (22.5 / 5 = 4.5) and is therefore NOT emitted.
# R28 calls a 1-minute microcycle divergence explicitly low-influence, so this is a
# declared omission rather than a silent gap.
BUILD_RES = "5"

CYCLES = ["90m", "Daily", "Weekly", "Monthly", "Quarterly", "Yearly"]


@dataclass
class Segment:
    key: tuple
    start: int
    end: int
    high: float = float("-inf")
    low: float = float("inf")
    high_t: int = 0
    low_t: int = 0
    bars: int = 0


@dataclass
class SmtEvent:
    cycle: str
    side: str                 # "high" (bearish) | "low" (bullish)
    bias: str                 # SHORT | LONG
    leg: str                  # the asset that diverged
    seg_prev: str
    seg_curr: str
    known_at: int             # the segment CLOSE — an SMT is not knowable mid-segment
    primary_prev: float
    primary_curr: float
    leg_prev: float
    leg_curr: float
    level: float              # the primary's extreme that defines the signal
    active_from: int = 0      # set by lifecycle()
    active_until: int | None = None
    taken_at: int | None = None


def segment_keys(ts: int) -> dict:
    """Every Quarterly-Theory segment key a timestamp belongs to.

    Mirrors the indicator's math: the day starts at 18:00 and each container is cut into
    four (or seven) segments.
    """
    dt = datetime.fromtimestamp(ts, NY)
    day_anchor = dt.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if dt < day_anchor:
        day_anchor -= timedelta(days=1)

    mins = int((dt - day_anchor).total_seconds() // 60)
    q_day = min(mins // 360, 3) + 1                 # 1..4  six-hour quarters
    q_90 = min((mins % 360) // 90, 3) + 1           # 1..4  ninety-minute quarters

    a = day_anchor
    iso = a.isocalendar()
    # qWeek: the indicator numbers Sunday=1 .. Saturday=7 from the DAY-ANCHOR's weekday.
    q_week = (a.weekday() + 1) % 7 + 1              # Mon=0 -> 2, ... Sun=6 -> 1
    week_of_month = ((iso[1] - 1) % 4) + 1
    q_month = ((a.month - 1) % 3) + 1
    q_year = (a.month - 1) // 3 + 1

    return {
        # container identity            segment index within it
        "90m":       ((a.date(), q_day), q_90),
        "Daily":     ((a.date(),), q_day),
        "Weekly":    ((iso[0], iso[1]), q_week),
        "Monthly":   ((a.year, a.month), week_of_month),
        "Quarterly": ((a.year, q_year), q_month),
        "Yearly":    ((a.year,), q_year),
    }


def build_segments(rows: list[list]) -> dict[str, list[Segment]]:
    """Bucket bars into ordered segments per cycle. No timestamp join anywhere."""
    out: dict[str, "OrderedDict[tuple, Segment]"] = {c: OrderedDict() for c in CYCLES}
    for r in rows:
        ts = int(r[0])
        keys = segment_keys(ts)
        for cycle, key in keys.items():
            seg = out[cycle].get(key)
            if seg is None:
                seg = Segment(key=key, start=ts, end=ts)
                out[cycle][key] = seg
            seg.end = ts
            seg.bars += 1
            if r[2] > seg.high:
                seg.high, seg.high_t = float(r[2]), ts
            if r[3] < seg.low:
                seg.low, seg.low_t = float(r[3]), ts
    return {c: list(v.values()) for c, v in out.items()}


def detect(segs: dict[str, dict[str, list[Segment]]], legs: list[str]) -> list[SmtEvent]:
    """Segment-extreme divergence, exactly as the indicator states it."""
    events: list[SmtEvent] = []
    for cycle in CYCLES:
        prim = segs[PRIMARY][cycle]
        # index each leg's segments by key so containers line up without a timestamp join
        leg_idx = {lg: {s.key: s for s in segs[lg][cycle]} for lg in legs if lg in segs}
        for i in range(1, len(prim)):
            p0, p1 = prim[i], prim[i - 1]          # current, previous
            for lg, idx in leg_idx.items():
                b0, b1 = idx.get(p0.key), idx.get(p1.key)
                if b0 is None or b1 is None:
                    continue                        # NOT-VISIBLE, never DID-NOT-DIVERGE
                # bearish: highs disagree in direction
                if not (p1.high == p0.high and b1.high == b0.high):
                    if (p1.high >= p0.high) != (b1.high >= b0.high):
                        events.append(SmtEvent(
                            cycle=cycle, side="high", bias="SHORT", leg=lg,
                            seg_prev=str(p1.key), seg_curr=str(p0.key),
                            known_at=p0.end,
                            primary_prev=p1.high, primary_curr=p0.high,
                            leg_prev=b1.high, leg_curr=b0.high,
                            level=max(p1.high, p0.high)))
                # bullish: lows disagree in direction
                if not (p1.low == p0.low and b1.low == b0.low):
                    if (p1.low <= p0.low) != (b1.low <= b0.low):
                        events.append(SmtEvent(
                            cycle=cycle, side="low", bias="LONG", leg=lg,
                            seg_prev=str(p1.key), seg_curr=str(p0.key),
                            known_at=p0.end,
                            primary_prev=p1.low, primary_curr=p0.low,
                            leg_prev=b1.low, leg_curr=b0.low,
                            level=min(p1.low, p0.low)))
    return events


def lifecycle(events: list[SmtEvent], prim_rows: list[list]) -> None:
    """Set each event's ACTIVE window, per the indicator's own deletion rule.

    Verbatim (bearish):   if time > tme and high >= top -> delete the line
    where `top` = line.get_y2 = the CURRENT segment's high, and `tme` = the time of
    that extreme. Mirror for bullish with `low <= bot`.

    So an SSMT is not a point event: it stays valid until price TAKES the diverged
    extreme. That is R23 — "the indicator displays only currently-valid Sequential
    SMTs; always read the current state, never a stale signal".

    ⚠ FRESHNESS: the indicator passes `dayStart` as `_time_limit` for 90m and Micro,
    and `0` for Daily and above. So intraday SSMTs stop counting as active at the next
    18:00 open; higher cycles persist until invalidated.

    ⚠ DIVERGENCE FROM THE INDICATOR, DELIBERATE: it evaluates `ah0` as the RUNNING max
    of the still-open segment, so its SSMT appears live and its endpoint moves. We date
    every event at its segment CLOSE instead. Reading a running extreme would be
    lookahead in a backtest — the exact defect S1c found contaminating 75% of output.
    """
    times = [int(r[0]) for r in prim_rows]
    highs = [float(r[2]) for r in prim_rows]
    lows = [float(r[3]) for r in prim_rows]

    for e in events:
        i = bisect_left(times, e.known_at)
        taken_at = None
        if e.side == "high":
            level = e.primary_curr
            for j in range(i, len(times)):
                if highs[j] >= level:
                    taken_at = times[j]
                    break
        else:
            level = e.primary_curr
            for j in range(i, len(times)):
                if lows[j] <= level:
                    taken_at = times[j]
                    break
        e.active_from = e.known_at
        e.taken_at = taken_at
        expiry = taken_at
        if e.cycle in ("90m", "Micro"):
            # expires at the next 18:00 NY open regardless of invalidation
            dt = datetime.fromtimestamp(e.known_at, NY)
            nxt = dt.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
            if dt >= nxt:
                nxt += timedelta(days=1)
            day_expiry = int(nxt.timestamp())
            expiry = day_expiry if taken_at is None else min(taken_at, day_expiry)
        e.active_until = expiry


def sequential(events: list[SmtEvent], span_end: int) -> list[dict]:
    """Sequential SMT = >=2 cycles' SSMTs ACTIVE AT THE SAME MOMENT, same direction.

    This is `f_alert`: it fires when the two chosen cycles both report an active SSMT
    (defaults pair Weekly+90m, and Daily+Micro). Nesting is ACTIVITY OVERLAP, not
    co-formation — which is what `aura_setup_engine.py` required and is a further
    reason its R18 read was wrong.
    """
    out = []
    for bias in ("SHORT", "LONG"):
        sel = [e for e in events if e.bias == bias]
        edges = sorted({e.active_from for e in sel} |
                       {e.active_until for e in sel if e.active_until})
        for t in edges:
            live = [e for e in sel
                    if e.active_from <= t and (e.active_until is None or t < e.active_until)]
            cycles = sorted({e.cycle for e in live}, key=CYCLES.index)
            if len(cycles) >= 2:
                out.append({
                    "at": t,
                    "at_ny": datetime.fromtimestamp(t, NY).isoformat(),
                    "bias": bias,
                    "cycles_active": cycles,
                    "depth": len(cycles),
                    "legs": sorted({e.leg for e in live}),
                })
    out.sort(key=lambda r: r["at"])
    # collapse consecutive identical states so the output is transitions, not a stream
    collapsed = []
    for r in out:
        if collapsed and collapsed[-1]["bias"] == r["bias"] \
                and collapsed[-1]["cycles_active"] == r["cycles_active"]:
            continue
        collapsed.append(r)
    return collapsed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    raw = json.loads((a.bars / f"s1e-bars-{BUILD_RES}.json").read_text())["resolutions"][BUILD_RES]
    symbols = [PRIMARY] + TRIAD_LEGS + [AURA_ASSET]

    t0 = int(datetime.strptime(a.t_from, "%Y-%m-%d").replace(tzinfo=NY).timestamp())
    t1 = int((datetime.strptime(a.t_to, "%Y-%m-%d").replace(tzinfo=NY)
              + timedelta(days=1)).timestamp())

    segs: dict[str, dict[str, list[Segment]]] = {}
    coverage = {}
    for sym in symbols:
        if sym not in raw:
            coverage[sym] = "ABSENT"
            continue
        rows = [r for r in raw[sym]["rows"] if t0 <= int(r[0]) <= t1]
        segs[sym] = build_segments(rows)
        coverage[sym] = {"bars": len(rows),
                         **{c: len(segs[sym][c]) for c in CYCLES}}

    events = detect(segs, TRIAD_LEGS + [AURA_ASSET])
    prim_rows = [r for r in raw[PRIMARY]["rows"] if t0 <= int(r[0]) <= t1]
    lifecycle(events, prim_rows)
    seq = sequential(events, t1)

    by_cycle: dict[str, dict] = {}
    for c in CYCLES:
        sel = [e for e in events if e.cycle == c]
        by_cycle[c] = {
            "events": len(sel),
            "short": sum(1 for e in sel if e.bias == "SHORT"),
            "long": sum(1 for e in sel if e.bias == "LONG"),
            "by_leg": {lg: sum(1 for e in sel if e.leg == lg)
                       for lg in TRIAD_LEGS + [AURA_ASSET]},
        }

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "qt-smt.json").write_text(json.dumps({
        "detector": "QT segment-extreme divergence (S1e-b)",
        "source": "api/docs/evidence/s1e/reference/README.md",
        "span": {"from": a.t_from, "to": a.t_to},
        "day_start_hour_ny": DAY_START_HOUR,
        "built_from_resolution": BUILD_RES,
        "micro_cycle": "NOT EMITTED — 22.5m does not divide 5m; R28 calls it low-influence",
        "timezone_note": ("DST-aware America/New_York used; the indicator's SSMT block "
                          "defaults to a FIXED UTC-4, which shifts every segment boundary "
                          "by an hour in winter. Declared divergence."),
        "coverage": coverage,
        "summary": by_cycle,
        "sequential_note": ("Sequential SMT = >=2 cycles ACTIVE simultaneously, same "
                            "direction (the indicator's f_alert). Activity overlap, not "
                            "co-formation."),
        "sequential": seq,
        "events": [
            {**e.__dict__, "known_at_utc": datetime.fromtimestamp(e.known_at, timezone.utc)
             .isoformat(), "known_at_ny": datetime.fromtimestamp(e.known_at, NY).isoformat()}
            for e in events
        ],
    }, indent=1), encoding="utf-8")

    print(f"[qt-smt] {a.t_from} -> {a.t_to}   {len(events)} SMT events")
    for c in CYCLES:
        s = by_cycle[c]
        print(f"  {c:<10} {s['events']:>5}  (SHORT {s['short']:>4} / LONG {s['long']:>4})"
              f"   by leg: {s['by_leg']}")
    still_live = sum(1 for e in events if e.taken_at is None)
    print(f"  {'-'*58}")
    print(f"  invalidated by price taking the extreme : {len(events) - still_live}")
    print(f"  never taken inside the span             : {still_live}")
    depths = {}
    for r in seq:
        depths[r['depth']] = depths.get(r['depth'], 0) + 1
    print(f"  SEQUENTIAL states (>=2 cycles active)   : {len(seq)}   by depth: {dict(sorted(depths.items()))}")
    print(f"[qt-smt] -> {a.out / 'qt-smt.json'}")


if __name__ == "__main__":
    main()
