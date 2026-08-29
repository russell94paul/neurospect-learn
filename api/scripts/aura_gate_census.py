#!/usr/bin/env python
"""
Aura HTF gate census — how many days can EVER reach the entry stage?

WHY THIS EXISTS. S1e wants "a number of valid entries and then wins and losses". The
naive plan is to export ~10 months of 5m bars and run the engine. But the entry count
may be capped by the RULES, not by the data: S1c stood aside on 21 of 22 days and R6
alone took 13. If almost no day clears the higher-timeframe gates, a deeper 5m export
buys almost nothing, and that should be known BEFORE paying for the export.

The engine's HTF gates (R3 SMT-qualified swing -> R7 currency -> R4 range -> R6 range
still live -> R18 nesting) all run on DAILY and 4H bars, which reach back to 2024-12-18
in the existing export. Only the last step (R30's 5m iFVG) needs the deep 5m history.
So the census below is computable today, with no new export.

    python api/scripts/aura_gate_census.py \
        --bars api/docs/evidence/s1c/bars/tradezella-831607-export.json \
        --bars api/docs/evidence/s1d/bars/tradezella-831607-weekly.json \
        --from 2025-01-02 --to 2025-05-30

⛔ COUNTING BASIS, DECLARED BEFORE ANY NUMBER IS PRODUCED
    - One unit = **one ET weekday** in the declared span. Not one setup, not one trade.
    - The population is **enumerated, never sampled**: every weekday in the span is
      evaluated and appears in exactly one bucket.
    - A day's verdict is **the FIRST gate that rejects it**, matching the engine's own
      evaluation order, so the buckets are mutually exclusive and sum to the population.
    - `REACHED-ENTRY-STAGE` means every HTF gate passed and the day would go on to look
      for a 5m iFVG. It is **NOT** a setup and **NOT** a trade — the 5m step rejects a
      further share of these (in S1c's window, R30 rejected some days outright).
    - This measures an **upper bound** on entries per unit of history. The true entry
      count is lower. An upper bound is the useful quantity here: if it is small, S1e's
      tally cannot be large no matter how much 5m data is exported.

⚠️ This is not a backtest and produces no outcomes, no win rate and no expectancy.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import aura_setup_engine as E


def htf_verdict(series, day: datetime) -> tuple[str, str]:
    """Re-run only the HTF gates, in the engine's order. Returns (bucket, detail).

    Deliberately imports the engine's own functions rather than reimplementing them: a
    census that used a second implementation of R6 would be measuring a different rule
    than the one S1e will run.
    """
    t0, _ = E.et_day_bounds(day)
    frame = series.get(E.CYCLE_FRAMING, {}).get(E.PRIMARY)
    if frame is None:
        return "DATA", "no daily series"
    # Is the framing cycle even loaded this far back?
    lo, hi = frame.slice_idx(t0 - 86400 * E.FRAMING_LOOKBACK_BARS, t0)
    if hi - lo < 20:
        return "DATA", "daily lookback not loaded this far back"

    events = []
    for side in ("high", "low"):
        ev, _ = E.find_smt(series, E.CYCLE_FRAMING, side,
                           t0 - 86400 * E.FRAMING_LOOKBACK_BARS, t0, as_of=t0)
        events += ev
    if not events:
        return "R3", "no SMT-qualified daily swing in the lookback"

    events.sort(key=lambda e: (e.known_at, e.pivot_time))
    htf = events[-1]

    rng = E.frame_range(frame, t0, anchor_time=htf.pivot_time)
    if rng is None:
        return "R4", "no framable expansive move"
    if rng.broken_by:
        how, px, when = rng.broken_by
        return "R6", f"range dead — {how} {px:,.2f} on {E.fmt_et(when)}"

    conf, _ = E.find_smt(series, E.CYCLE_CONFIRM, htf.side, htf.pivot_time, t0, as_of=t0)
    if conf:
        return "REACHED-ENTRY-STAGE", f"{htf.bias} — nested {E.CYCLE_CONFIRM}m"
    skip, _ = E.find_smt(series, E.CYCLE_SESSION, htf.side, htf.pivot_time, t0, as_of=t0)
    if skip:
        return "REACHED-ENTRY-STAGE", f"{htf.bias} — R24 Sequential Skip"
    return "R18", "daily SMT present but not sequential"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", required=True, type=Path, action="append")
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    a = ap.parse_args()

    series, _ = E.load_bars(a.bars)
    d0 = datetime.strptime(a.t_from, "%Y-%m-%d")
    d1 = datetime.strptime(a.t_to, "%Y-%m-%d")

    buckets: Counter[str] = Counter()
    reached: list[tuple[str, str]] = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            b, detail = htf_verdict(series, d)
            buckets[b] += 1
            if b == "REACHED-ENTRY-STAGE":
                reached.append((d.strftime("%Y-%m-%d"), detail))
        d += timedelta(days=1)

    total = sum(buckets.values())
    print(f"\nDeclared span {a.t_from} -> {a.t_to} ET · {total} weekdays enumerated")
    print("Counting basis: one unit = one ET weekday; verdict = FIRST gate to reject; "
          "buckets are mutually exclusive and sum to the population.\n")
    print(f"{'bucket':<22} {'days':>5}  {'share':>7}")
    print("-" * 40)
    for k, v in buckets.most_common():
        print(f"{k:<22} {v:>5}  {v / total:>6.1%}")
    print("-" * 40)
    print(f"{'TOTAL':<22} {total:>5}  {sum(buckets.values()) / total:>6.1%}")

    n = buckets.get("REACHED-ENTRY-STAGE", 0)
    print(f"\nREACHED-ENTRY-STAGE = {n} of {total} weekdays "
          f"({n / total:.1%}) — an UPPER BOUND on entries, not an entry count.")
    print("The 5m iFVG step (R30) rejects a further share of these, so the true entry "
          "count is lower.\n")
    if n:
        print("Days that cleared every HTF gate:")
        for day, detail in reached:
            print(f"  {day}  {detail}")
    if total:
        print(f"\nImplied history needed for ~10 entries at THIS upper bound: "
              f"{10 / (n / total) if n else float('inf'):.0f} weekdays "
              f"(~{(10 / (n / total)) / 21 if n else float('inf'):.1f} months) — and more, "
              "because R30 rejects some of them.")


if __name__ == "__main__":
    main()
