#!/usr/bin/env python
"""
Range framing — R4's expansive-move method, with R6 invalidation and D/EQ/P zones.

    python api/scripts/aura_range.py --bars api/docs/evidence/s1e/bars/packed \
        --res D --from 2025-01-02 --to 2025-05-30 --out api/docs/evidence/s1e/range

⭐ WHY THIS IS SAFE TO BUILD BEFORE PAUL'S TRADINGVIEW CHECK
Range ANCHORING uses **swing-point SMT** (aura-11: *"position the extremes of my ranges on
swing points, higher time frame swing points that have SMT within them"*) — the object built
by `aura_swing_smt.py`, which the pending cycle-SMT validation does not touch.
Only the new-range TRIGGER (R7: HTF *Sequential* SMT + expansive move) depends on the cycle
detector under validation, so that part is left as a declared hook, NOT guessed.

DEFINITIONS, FROM `ranges.md` (aura-08/11) AND `rules.md`

R4  "Find the largest expansive move between two swing points — this expansive move IS the
     range." Explicitly NOT time-based ranges.
R5  Reference zones are **discount / equilibrium / premium** only.
     ⛔ NO QUADRANTS — rule 5 names 0.25/0.75 an explicit ICT divergence.
R6  "A range is invalidated only by a candle CLOSE beyond its boundary — a wick through is
     not a break."
R3/R8  Anchor on SMT-QUALIFIED swing points; unqualified swings are provisional.
aura-08 step 4  "If we don't come into discount of this range, you just keep on marking
     higher, you continue to mark higher." -> the range EXTENDS rather than a new one being
     drawn, until price actually retraces into discount.
R9  Ambiguity is acceptable: "you can have two ranges if you prefer that". When the top two
     candidate moves are within a tolerance, BOTH are emitted rather than one being forced.

⛔ WHAT THIS DOES NOT DO
- It does not flip ranges on Sequential SMT (R7's trigger) — that needs the cycle detector.
- It does not pick entries.
- `zoom out until it becomes obvious` (aura-08's human fallback) is not automated; when the
  candidates are ambiguous the range is emitted as AMBIGUOUS instead of resolved.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# R9: when the top-2 candidate expansive moves are within this fraction of each other the
# engine REFUSES to pick and emits both. Declared, not tuned.
AMBIGUITY_TOLERANCE = 0.15


@dataclass
class Pivot:
    t: int
    price: float
    side: str
    smt_qualified: bool = False


@dataclass
class Range:
    high: float
    low: float
    high_t: int
    low_t: int
    direction: str                 # bullish (low->high) | bearish (high->low)
    framed_at: int                 # knowable-at: the later of the two anchors
    res: str
    anchors_smt_qualified: bool
    size: float
    extended_to: float | None = None      # aura-08 step 4
    extended_t: int | None = None
    invalidated_t: int | None = None      # R6: a CLOSE beyond a boundary
    invalidated_by: float | None = None
    invalidated_side: str | None = None
    runner_up: dict | None = None         # R9
    ambiguous: bool = False

    @property
    def eq(self) -> float:
        return (self.high + self.low) / 2

    def zone(self, price: float) -> str:
        if self.high == self.low:
            return "EQUILIBRIUM"
        p = (price - self.low) / (self.high - self.low)
        if abs(p - 0.5) < 1e-9:
            return "EQUILIBRIUM"
        return "DISCOUNT" if p < 0.5 else "PREMIUM"


def load_pivots(swing_json: Path | None, rows: list[list]) -> list[Pivot]:
    """Prefer the measured swing-SMT output; fall back to raw pivots if absent."""
    if swing_json and swing_json.exists():
        d = json.loads(swing_json.read_text())
        return [Pivot(t=e["pivot_t"], price=e["level"], side=e["side"],
                      smt_qualified=e["smt_qualified"]) for e in d["events"]]
    out = []
    for i in range(1, len(rows) - 1):
        a, b, c = rows[i - 1], rows[i], rows[i + 1]
        if b[2] > a[2] and b[2] > c[2]:
            out.append(Pivot(int(b[0]), float(b[2]), "high"))
        if b[3] < a[3] and b[3] < c[3]:
            out.append(Pivot(int(b[0]), float(b[3]), "low"))
    return out


def frame(pivots: list[Pivot], res: str, require_smt: bool) -> Range | None:
    """R4: the LARGEST expansive move between two swing points IS the range."""
    ps = [p for p in pivots if (p.smt_qualified or not require_smt)]
    ps.sort(key=lambda p: p.t)
    best = None
    second = None
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            if a.side == b.side:
                continue
            size = abs(b.price - a.price)
            lo, hi = (a, b) if a.price < b.price else (b, a)
            cand = Range(
                high=hi.price, low=lo.price, high_t=hi.t, low_t=lo.t,
                direction="bullish" if a.side == "low" else "bearish",
                framed_at=max(a.t, b.t), res=res,
                anchors_smt_qualified=(a.smt_qualified and b.smt_qualified),
                size=size)
            if best is None or size > best.size:
                second, best = best, cand
            elif second is None or size > second.size:
                second = cand
    if best is None:
        return None
    if second is not None:
        best.runner_up = {"high": second.high, "low": second.low, "size": second.size}
        # R9: refuse to pick when the top two are within tolerance
        if best.size > 0 and (best.size - second.size) / best.size < AMBIGUITY_TOLERANCE:
            best.ambiguous = True
    return best


def lifecycle(rng: Range, rows: list[list]) -> None:
    """R6 invalidation (CLOSE, not wick) and aura-08 step 4 extension.

    Step 4, verbatim: "if we don't come into discount of this range, you just keep on
    marking higher, you continue to mark higher." So while price has NOT retraced into the
    range's discount, a new high EXTENDS the range instead of creating a new one.
    """
    entered_discount = False
    for r in rows:
        t = int(r[0])
        if t <= rng.framed_at:
            continue
        hi, lo, cl = float(r[2]), float(r[3]), float(r[4])
        if not entered_discount and rng.zone(lo) == "DISCOUNT":
            entered_discount = True
        # extension only applies BEFORE the first discount retrace
        if not entered_discount and hi > (rng.extended_to or rng.high):
            rng.extended_to, rng.extended_t = hi, t
        if rng.invalidated_t is None:
            top = rng.extended_to or rng.high
            if cl > top:
                rng.invalidated_t, rng.invalidated_by, rng.invalidated_side = t, cl, "high"
                break
            if cl < rng.low:
                rng.invalidated_t, rng.invalidated_by, rng.invalidated_side = t, cl, "low"
                break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--res", default="D")
    ap.add_argument("--symbol", default="NQ")
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--swing-json", type=Path, default=None,
                    help="aura_swing_smt.py output; enables SMT-qualified anchoring (R3/aura-11)")
    ap.add_argument("--anchors", choices=["all", "smt-qualified"], default="smt-qualified")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    raw = json.loads((a.bars / f"s1e-bars-{a.res}.json").read_text())["resolutions"][a.res]
    rows_all = raw[a.symbol]["rows"]
    t0 = int(datetime.strptime(a.t_from, "%Y-%m-%d").replace(tzinfo=NY).timestamp())
    t1 = int((datetime.strptime(a.t_to, "%Y-%m-%d").replace(tzinfo=NY)
              + timedelta(days=1)).timestamp())
    rows = [r for r in rows_all if t0 <= int(r[0]) <= t1]

    pivots = load_pivots(a.swing_json, rows)
    pivots = [p for p in pivots if t0 <= p.t <= t1]
    require = a.anchors == "smt-qualified"
    rng = frame(pivots, a.res, require)
    if rng is None:
        raise SystemExit("no range could be framed — no opposing swing-point pair")
    lifecycle(rng, rows)

    top = rng.extended_to or rng.high
    out = {
        "symbol": a.symbol, "resolution": a.res,
        "span": {"from": a.t_from, "to": a.t_to},
        "anchor_mode": a.anchors,
        "anchor_source": (str(a.swing_json) if a.swing_json and a.swing_json.exists()
                          else "RAW PIVOTS (no swing-SMT file given — anchors NOT qualified)"),
        "quadrants": "NOT EMITTED — rule 5: discount/EQ/premium only",
        "r7_trigger": ("NOT IMPLEMENTED — a new range is triggered by HTF *Sequential* SMT "
                       "+ expansive move, which needs the cycle detector currently awaiting "
                       "Paul's TradingView validation. Declared hook, not guessed."),
        "ambiguity_tolerance": AMBIGUITY_TOLERANCE,
        "range": {
            **asdict(rng),
            "eq": rng.eq,
            "top_effective": top,
            "discount": [rng.low, rng.eq],
            "premium": [rng.eq, top],
            "framed_ny": datetime.fromtimestamp(rng.framed_at, NY).isoformat(),
            "invalidated_ny": (datetime.fromtimestamp(rng.invalidated_t, NY).isoformat()
                               if rng.invalidated_t else None),
        },
        "pivots_considered": len(pivots),
        "pivots_smt_qualified": sum(1 for p in pivots if p.smt_qualified),
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "range.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"[range] {a.symbol} {a.res}  {a.t_from} -> {a.t_to}   anchors={a.anchors}")
    print(f"[range] pivots considered   : {len(pivots)} "
          f"({out['pivots_smt_qualified']} SMT-qualified)")
    print(f"[range] RANGE               : {rng.low:,.2f} - {rng.high:,.2f}  "
          f"({rng.direction}, {rng.size:,.2f} pts)")
    print(f"[range]   equilibrium       : {rng.eq:,.2f}")
    print(f"[range]   discount         : {rng.low:,.2f} - {rng.eq:,.2f}")
    print(f"[range]   premium          : {rng.eq:,.2f} - {top:,.2f}")
    if rng.extended_to:
        print(f"[range] EXTENDED to         : {rng.extended_to:,.2f} "
              f"(aura-08 step 4 — no discount retrace yet)")
    print(f"[range] anchors SMT-qualified: {rng.anchors_smt_qualified}")
    print(f"[range] R9 ambiguous        : {rng.ambiguous}"
          + (f"  runner-up {rng.runner_up['low']:,.2f}-{rng.runner_up['high']:,.2f}"
             if rng.runner_up else ""))
    if rng.invalidated_t:
        print(f"[range] R6 INVALIDATED      : close {rng.invalidated_by:,.2f} beyond the "
              f"{rng.invalidated_side} at "
              f"{datetime.fromtimestamp(rng.invalidated_t, NY).strftime('%Y-%m-%d %H:%M')}")
    else:
        print("[range] R6                  : still live at span end")
    print(f"[range] -> {a.out / 'range.json'}")


if __name__ == "__main__":
    main()
