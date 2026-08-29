#!/usr/bin/env python
"""
Swing-point SMT — the SECOND SMT object, the one that qualifies RANGE ANCHORS.

    python api/scripts/aura_swing_smt.py --bars api/docs/evidence/s1e/bars/packed \
        --res 60 --from 2025-05-26 --to 2025-05-30 --out api/docs/evidence/s1e/swing

⭐ WHY THIS EXISTS — `object-inventory.md` §"there are TWO SMT objects"
The corpus describes two different SMT objects doing two different jobs, and S1e conflated
them:

    swing-point SMT   a 3-candle PIVOT the triad disagrees about  ->  qualifies which swing
                      points are valid RANGE ANCHORS            (aura-06, aura-11, R3, R8)

    cycle SMT         a cycle SEGMENT's extreme vs the previous  ->  sets BIAS
                      segment's                                  (aura-07/12, R18)

`aura_qt_smt.py` builds the cycle object. THIS builds the swing-point object.
`aura_setup_engine.py` built only this one and then used it for the cycle object's job.

The load-bearing rule (aura-11, R3): *"Swing points that have sequential or SMT within them
have a higher chance of holding compared to [swing points] that don't."* And aura-11 on
anchoring: *"I want to position the extremes of my ranges on swing points, higher time frame
swing points that have SMT within them."*

⭐ WHY THIS IS SAFE TO BUILD NOW: range ANCHORING uses this object, which Paul's pending
TradingView check does not touch. Only the new-range TRIGGER (R7: HTF Sequential SMT +
expansive move) depends on the cycle detector under validation.

⚠ DECLARED INTERPRETATION — the forward window.
aura-06's language points at the IMMEDIATELY ADJACENT candle: *"candle 2 failed to take out
or candle 3 failed to take out the high … however, on YM, it took it out."* The old engine
used a wider N-bar window instead. Both are defensible, so the window is a DECLARED,
configurable constant (`--forward-bars`, default 3) and its value is written into the output
— never an unstated choice buried in code.

⚠ NO LOOKAHEAD. A leg "did not take" a level only once the forward window has CLOSED. Every
event is dated at that close, never at the pivot. S1c found a lookahead bug of exactly this
shape contaminating 75% of its output.

⚠ THE AURA ASSET IS JOINED ON SESSION DATE, not exact timestamps — CHFUSD shares **0** of
NQ's 3,794 daily timestamps, which made it permanently NOT-VISIBLE in the old engine (100%
of S1e's setups). See `s1e/execution-audit.md`.

⛔ R8 IS A RULEBOOK CONTRADICTION AND IS NOT RESOLVED HERE.
Rule 8 sentence 1: anchor extremes only on **SMT-qualified** swings (which diverge).
Rule 8 sentence 2: prefer the extreme **swept on all triad assets** (which does not diverge).
No single swing satisfies both. Both facts are MEASURED and emitted per pivot
(`smt_qualified`, `swept_on_all`); the choice is left to Paul.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

PRIMARY = "NQ"
TRIAD_LEGS = ["ES", "YM"]
AURA_ASSET = "CHFUSD"

# Coarse resolutions where the Aura Asset's bars do not share timestamps with the futures.
SESSION_JOIN_RES = {"D", "W"}
DAY_START_HOUR = 18


@dataclass
class LegRead:
    symbol: str
    verdict: str              # TOOK | DID-NOT-TAKE | WITHIN-NOISE | NOT-VISIBLE
    margin_ticks: float | None = None
    note: str = ""


@dataclass
class SwingSMT:
    side: str                 # high | low
    level: float
    pivot_t: int
    known_at: int             # forward window CLOSE — never the pivot
    res: str
    primary_verdict: str
    legs: list = field(default_factory=list)
    diverging: list = field(default_factory=list)
    smt_qualified: bool = False
    swept_on_all: bool = False


def measure_tick(rows: list[list]) -> float:
    seen = set()
    for r in rows[:4000]:
        for v in (r[1], r[2], r[3], r[4]):
            seen.add(round(float(v), 6))
    vals = sorted(seen)
    diffs = [round(b - a, 6) for a, b in zip(vals, vals[1:]) if b - a > 1e-9]
    return min(diffs) if diffs else 0.25


def session_key(ts: int):
    dt = datetime.fromtimestamp(ts, NY)
    a = dt.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if dt < a:
        a -= timedelta(days=1)
    return a.date()


def build_lookup(rows: list[list], res: str, session_join: bool):
    """Index a leg's bars for lookup — by timestamp, or by ET session date."""
    idx = {}
    for i, r in enumerate(rows):
        k = session_key(int(r[0])) if session_join else int(r[0])
        idx.setdefault(k, i)
    return idx


def detect(series: dict[str, list[list]], res: str, forward_bars: int,
           noise_ticks: float) -> list[SwingSMT]:
    prim = series[PRIMARY]
    tick = measure_tick(prim)
    floor = noise_ticks * tick
    out: list[SwingSMT] = []

    lookups = {}
    for sym, rows in series.items():
        if sym == PRIMARY:
            continue
        lookups[sym] = (rows, build_lookup(rows, res,
                                          sym == AURA_ASSET and res in SESSION_JOIN_RES))

    for i in range(1, len(prim) - 1 - forward_bars):
        a, b, c = prim[i - 1], prim[i], prim[i + 1]
        for side in ("high", "low"):
            if side == "high":
                if not (b[2] > a[2] and b[2] > c[2]):
                    continue
                level = float(b[2])
            else:
                if not (b[3] < a[3] and b[3] < c[3]):
                    continue
                level = float(b[3])

            window = prim[i + 1: i + 1 + forward_bars]
            if not window:
                continue
            known_at = int(window[-1][0])          # the window's CLOSE — no lookahead

            def verdict_for(rows, idx, sess):
                """Did this leg take its corresponding level over the same window?"""
                key = session_key(int(b[0])) if sess else int(b[0])
                j = idx.get(key)
                if j is None:
                    return LegRead("", "NOT-VISIBLE", note="no bar matched for the pivot")
                lvl = float(rows[j][2]) if side == "high" else float(rows[j][3])
                seg = rows[j + 1: j + 1 + forward_bars]
                if not seg:
                    return LegRead("", "NOT-VISIBLE", note="forward window absent")
                ext = (max(float(x[2]) for x in seg) if side == "high"
                       else min(float(x[3]) for x in seg))
                lt = measure_tick(rows)
                if side == "high":
                    d = ext - lvl
                else:
                    d = lvl - ext
                if d > lt * noise_ticks:
                    return LegRead("", "TOOK", round(d / lt, 2))
                if d < -lt * noise_ticks:
                    return LegRead("", "DID-NOT-TAKE", round(-d / lt, 2))
                return LegRead("", "WITHIN-NOISE", round(abs(d) / lt, 2))

            # the primary's own verdict over the same window
            pext = (max(float(x[2]) for x in window) if side == "high"
                    else min(float(x[3]) for x in window))
            pd_ = (pext - level) if side == "high" else (level - pext)
            p_verdict = ("TOOK" if pd_ > floor else
                         "DID-NOT-TAKE" if pd_ < -floor else "WITHIN-NOISE")

            legs = []
            for sym, (rows, idx) in lookups.items():
                lr = verdict_for(rows, idx, sym == AURA_ASSET and res in SESSION_JOIN_RES)
                lr.symbol = sym
                legs.append(lr)

            # SMT = the triad DISAGREES about whether the level was taken.
            decided = [l for l in legs if l.verdict in ("TOOK", "DID-NOT-TAKE")]
            diverging = [l.symbol for l in decided if l.verdict != p_verdict]
            qualified = bool(diverging) and p_verdict in ("TOOK", "DID-NOT-TAKE")
            # rule 8 sentence 2: the extreme swept on ALL triad assets (the opposite test)
            swept_all = (p_verdict == "TOOK"
                         and bool(decided)
                         and all(l.verdict == "TOOK" for l in decided))

            out.append(SwingSMT(
                side=side, level=level, pivot_t=int(b[0]), known_at=known_at, res=res,
                primary_verdict=p_verdict, legs=[asdict(l) for l in legs],
                diverging=diverging, smt_qualified=qualified, swept_on_all=swept_all))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--res", default="60")
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--forward-bars", type=int, default=3,
                    help="DECLARED forward window in bars. aura-06's wording points at the "
                         "immediately adjacent candle; the old engine used a wider window.")
    ap.add_argument("--noise-ticks", type=float, default=1.0,
                    help="ticks a leg must exceed the level by to count as TOOK. Guards "
                         "against a phantom SMT from a sub-tick difference.")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    raw = json.loads((a.bars / f"s1e-bars-{a.res}.json").read_text())["resolutions"][a.res]
    t0 = int(datetime.strptime(a.t_from, "%Y-%m-%d").replace(tzinfo=NY).timestamp())
    t1 = int((datetime.strptime(a.t_to, "%Y-%m-%d").replace(tzinfo=NY)
              + timedelta(days=1)).timestamp())
    pad = 86400 * 10
    series = {}
    for sym in [PRIMARY] + TRIAD_LEGS + [AURA_ASSET]:
        if sym in raw:
            series[sym] = [r for r in raw[sym]["rows"] if t0 - pad <= int(r[0]) <= t1 + pad]

    events = detect(series, a.res, a.forward_bars, a.noise_ticks)
    inwin = [e for e in events if t0 <= e.pivot_t <= t1]

    q = [e for e in inwin if e.smt_qualified]
    sw = [e for e in inwin if e.swept_on_all]
    both = [e for e in inwin if e.smt_qualified and e.swept_on_all]
    legcount: dict = {}
    for e in q:
        for d in e.diverging:
            legcount[d] = legcount.get(d, 0) + 1
    notvis: dict = {}
    for e in inwin:
        for l in e.legs:
            if l["verdict"] == "NOT-VISIBLE":
                notvis[l["symbol"]] = notvis.get(l["symbol"], 0) + 1

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "swing-smt.json").write_text(json.dumps({
        "object": "swing-point SMT — qualifies RANGE ANCHORS (aura-06/11, R3/R8)",
        "not_the_same_as": "cycle SMT (aura_qt_smt.py) which sets BIAS",
        "resolution": a.res,
        "span": {"from": a.t_from, "to": a.t_to},
        "forward_bars_declared": a.forward_bars,
        "noise_ticks_declared": a.noise_ticks,
        "aura_asset_join": ("session-date" if a.res in SESSION_JOIN_RES else "timestamp"),
        "r8_note": ("R8 is a rulebook CONTRADICTION and is NOT resolved: sentence 1 wants "
                    "SMT-qualified swings (which diverge), sentence 2 wants the extreme "
                    "swept on ALL legs (which does not). Both measured, neither chosen."),
        "totals": {
            "pivots": len(inwin),
            "smt_qualified": len(q),
            "swept_on_all": len(sw),
            "both_r8_conflict": len(both),
            "diverging_leg_counts": legcount,
            "not_visible_by_leg": notvis,
        },
        "events": [{**asdict(e),
                    "pivot_ny": datetime.fromtimestamp(e.pivot_t, NY).isoformat(),
                    "known_at_ny": datetime.fromtimestamp(e.known_at, NY).isoformat()}
                   for e in inwin],
    }, indent=1), encoding="utf-8")

    print(f"[swing] {a.res}  {a.t_from} -> {a.t_to}   forward={a.forward_bars} bars, "
          f"noise={a.noise_ticks} tick(s)")
    print(f"[swing] pivots                  : {len(inwin)}")
    print(f"[swing] SMT-QUALIFIED (R3)      : {len(q)}   diverging leg: {legcount}")
    print(f"[swing] swept on ALL legs (R8b) : {len(sw)}")
    print(f"[swing] both (R8 contradiction) : {len(both)}")
    print(f"[swing] NOT-VISIBLE by leg      : {notvis or '{}'}")
    print(f"[swing] -> {a.out / 'swing-smt.json'}")


if __name__ == "__main__":
    main()
