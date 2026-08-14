#!/usr/bin/env python
"""
Independent audit of one computed record — Phase S1c.

Re-derives the numbers in a single logged setup straight from the exported JSON,
WITHOUT importing anything from `aura_setup_engine.py`. The point is that a bug in
the engine cannot hide in the check: if the two disagree, the engine is wrong.

Predictions are asserted, not printed-and-eyeballed. The exit code is the verdict.

    python api/scripts/aura_verify_record.py \
        --bars api/docs/evidence/s1c/bars/tradezella-831607-export.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# The record under audit: 2025-05-30 SHORT (see computed-setups.md).
# Each expectation is what the ENGINE claimed. The audit recomputes it by hand.
CLAIMS = {
    "pivot_et": "2025-05-20 09:30",
    "level": 21562.25,
    "nq_margin_ticks": 21.0,
    "es_verdict": "DID-NOT-TAKE",
    "es_margin_ticks": 141.0,
    "ym_verdict": "DID-NOT-TAKE",
    "ym_margin_ticks": 234.0,
    "stop": 21567.50,
    "target": 20727.00,
    "entry": 21341.75,
    "rr": 2.7,
    # The session the engine traded this on, and the ET day it claims the signal
    # became knowable. This pair is the lookahead check.
    "traded_on_et_date": "2025-05-30",
    "known_at_et": "2025-05-29 09:30",
}
TICK = {"NQ": 0.25, "ES": 0.25, "YM": 1.0}
FORWARD_DAILY_BARS = 5
FLOOR_TICKS = 2.0


def et(ts: int) -> str:
    return datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d %H:%M")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    a = ap.parse_args()
    raw = json.loads(a.bars.read_text())
    daily = raw["resolutions"]["D"]

    nq = sorted(daily["NQ"]["rows"], key=lambda r: r[0])
    es = sorted(daily["ES"]["rows"], key=lambda r: r[0])
    ym = sorted(daily["YM"]["rows"], key=lambda r: r[0])

    fails: list[str] = []

    def check(name: str, got, want, tol=1e-6) -> None:
        ok = (abs(got - want) <= tol) if isinstance(want, (int, float)) else (got == want)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got!r}, engine claimed {want!r}")
        if not ok:
            fails.append(name)

    # Locate the pivot bar by ET timestamp, not by index.
    pi = next(i for i, r in enumerate(nq) if et(int(r[0])) == CLAIMS["pivot_et"])
    print(f"\nPivot bar located at index {pi} — {et(int(nq[pi][0]))}")

    # R1/R2: it must actually be a 3-candle swing high.
    is_pivot = nq[pi][2] > nq[pi - 1][2] and nq[pi][2] > nq[pi + 1][2]
    print(f"  {'PASS' if is_pivot else 'FAIL'}  R1/R2 3-candle swing high "
          f"({nq[pi-1][2]} < {nq[pi][2]} > {nq[pi+1][2]})")
    if not is_pivot:
        fails.append("R1/R2 pivot")

    check("R1 level", nq[pi][2], CLAIMS["level"])

    # Forward window, by timestamp.
    fwd_ts = [int(r[0]) for r in nq[pi + 1: pi + 1 + FORWARD_DAILY_BARS]]
    print(f"  forward window: {et(fwd_ts[0])} .. {et(fwd_ts[-1])} ({len(fwd_ts)} bars)")

    nq_ext = max(float(r[2]) for r in nq if int(r[0]) in fwd_ts)
    check("NQ exceeded level by (ticks)", round((nq_ext - CLAIMS["level"]) / TICK["NQ"], 2),
          CLAIMS["nq_margin_ticks"])

    # Legs: level = max high over the three pivot bars, joined BY TIMESTAMP.
    pivot_ts = {int(nq[j][0]) for j in (pi - 1, pi, pi + 1)}
    for sym, rows, vkey, mkey in (
        ("ES", es, "es_verdict", "es_margin_ticks"),
        ("YM", ym, "ym_verdict", "ym_margin_ticks"),
    ):
        lvl_bars = [r for r in rows if int(r[0]) in pivot_ts]
        win_bars = [r for r in rows if int(r[0]) in set(fwd_ts)]
        if not lvl_bars or not win_bars:
            print(f"  FAIL  {sym}: NOT-VISIBLE — no timestamp-matched bars")
            fails.append(f"{sym} visibility")
            continue
        lvl = max(float(r[2]) for r in lvl_bars)
        ext = max(float(r[2]) for r in win_bars)
        floor = TICK[sym] * FLOOR_TICKS
        verdict = ("TOOK" if ext > lvl + floor
                   else "DID-NOT-TAKE" if ext < lvl - floor else "WITHIN-NOISE")
        check(f"{sym} verdict", verdict, CLAIMS[vkey])
        check(f"{sym} missed by (ticks)", round((lvl - ext) / TICK[sym], 2), CLAIMS[mkey])

    # ── THE LOOKAHEAD CHECK ────────────────────────────────────────────────────
    # The signal is not knowable until the last bar of the forward window has
    # CLOSED. Derived from real bar timestamps: calendar arithmetic (pivot + N days)
    # ignores weekends and holidays and previously dated this signal 05-25, three
    # sessions early — which let the engine trade it on the session that produced it.
    last_fwd = fwd_ts[-1]
    known_at = last_fwd + 86400          # the window's last daily bar must close
    check("known_at (bar-derived, not calendar)", et(known_at), CLAIMS["known_at_et"])
    traded_at = datetime.strptime(CLAIMS["traded_on_et_date"], "%Y-%m-%d") \
        .replace(tzinfo=ET).timestamp()
    no_lookahead = known_at <= traded_at
    print(f"  {'PASS' if no_lookahead else 'FAIL'}  no lookahead: signal knowable "
          f"{et(known_at)} <= session open {CLAIMS['traded_on_et_date']} 00:00")
    if not no_lookahead:
        fails.append("lookahead")
    naive = int(nq[pi][0]) + 5 * 86400
    print(f"  (for contrast, naive calendar arithmetic would have dated it "
          f"{et(naive)} — {(known_at - naive) // 86400} days early)")

    # R33/R35: the arithmetic of the trade itself.
    stop = CLAIMS["level"] + (nq_ext - CLAIMS["level"])
    check("R33 stop = level + sweep margin", stop, CLAIMS["stop"])
    risk = CLAIMS["stop"] - CLAIMS["entry"]
    reward = CLAIMS["entry"] - CLAIMS["target"]
    check("R35 R:R", round(reward / risk, 1), CLAIMS["rr"])
    print(f"  (risk {risk:,.2f} pts · reward {reward:,.2f} pts — both positive in the "
          f"SHORT direction, which is the sign check the engine previously failed)")

    print("\n" + ("AUDIT PASSED — the engine's numbers reproduce independently"
                  if not fails else f"AUDIT FAILED on: {', '.join(fails)}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
