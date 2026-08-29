#!/usr/bin/env python
"""
Aura PD arrays — the four gap types, and "what lies WITHIN" them (S1e-b, 2026-08-15).

    python api/scripts/aura_pd_arrays.py --bars api/docs/evidence/s1e/bars/packed \
        --res 5 --from 2025-05-26 --to 2025-05-30 --out api/docs/evidence/s1e/pd

⭐ WHY THIS EXISTS
`object-inventory.md` found that the single most valuable Aura object is implemented by
NOBODY — not our engine, not the QT[✦] indicators:

    B5  "what lies within" — the liquidity (a swing high/low) nested INSIDE a gap.
        gaps.md is unambiguous: "that internal level is the precise target, NOT the gap
        boundary." It is simultaneously rule 12's precise target, the core thesis of the
        gaps lesson, and Paul's TP1 ("half off at nearest IRL", 2026-08-15).

    B6  the fallbacks when no internal liquidity is visible: "If you can't find one,
        either LOOK LEFT or ZOOM IN." (aura-09)

    B7  confluence stacking, which dOoMeR treats as ADDITIVE.

⛔ EXACTLY FOUR GAP TYPES. FVG · iFVG · NWOG · NDOG.
"The only gaps I care about are... fair value gaps, inverse fair value gaps, or new week
opening gaps and new day opening gaps." (aura-09). No BPR, no volume imbalance — and this
script must never grow a fifth type without a source line to justify it.

DEFINITIONS TAKEN FROM SOURCE, NOT FROM MEMORY
- FVG, verbatim from `qt-pro.pine`:      bullish `low > high[2]` · bearish `high < low[2]`
- FVG mitigation, verbatim:              bullish `low <= bottom` · bearish `high >= top`
- iFVG: an FVG price has CLOSED THROUGH, inverting its polarity (rules.md R11).
  ⚠ The QT[✦] indicators do NOT define iFVG — 0 matches for "invers/ifvg" across all three
  scripts (the 8-9 hits elsewhere are the ASSET Inverse toggles). So the iFVG definition
  comes from the Aura corpus alone and CANNOT be cross-checked against the indicator.
- NDOG: previous day's close -> the 18:00 NY open.  NWOG: Friday close -> Monday open.

⛔ WHAT THIS SCRIPT DOES NOT DO
- It does not decide premium/discount. That needs a range, and the range engine is not
  rebuilt yet. Gaps are emitted with their prices so zone-tagging can be applied later.
- It does not pick an entry. Rule 30's entry is an iFVG *in the confirmed direction within
  the LTF range's discount/premium* — bias comes from the SMT layer, which is still
  awaiting Paul's TradingView validation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
DAY_START_HOUR = 18          # NDOG anchor, per qt-pro.pine's force1800

# S1d declared a 4-tick floor after finding a ONE-TICK gap treated as an entry candidate
# on equal footing with a six-tick one. Declared, counted, and reported — never silent.
MIN_GAP_TICKS = 4

RES_ORDER = ["1", "5", "15", "60", "240", "D", "W"]


@dataclass
class Pivot:
    t: int
    price: float
    side: str            # "high" | "low"
    swept_at: int | None = None


@dataclass
class Gap:
    kind: str            # FVG | iFVG | NWOG | NDOG
    direction: str       # bullish | bearish  (polarity AFTER any inversion)
    top: float
    bottom: float
    formed_t: int
    res: str
    size_ticks: float
    subtype: str | None = None         # NWOG/NDOG: VOID-BULL | OVERLAP-BULL | ...
    prior_session_open: float | None = None
    prior_session_close: float | None = None
    inverted_t: int | None = None      # iFVG only: when polarity flipped
    mitigated_t: int | None = None
    # B5 / B6 — "what lies within"
    internal_liquidity: float | None = None
    internal_liquidity_t: int | None = None
    liquidity_route: str = "NONE"      # INSIDE | LOOK-LEFT | ZOOM-IN | NOT-VISIBLE
    # B7 — confluence, additive
    overlaps: list = field(default_factory=list)
    liquidity_left: float | None = None

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2


def measure_tick(rows: list[list]) -> float:
    """Smallest non-zero price increment observed. Measured, never assumed."""
    seen = set()
    for r in rows[:4000]:
        for v in (r[1], r[2], r[3], r[4]):
            seen.add(round(float(v), 6))
    vals = sorted(seen)
    diffs = [round(b - a, 6) for a, b in zip(vals, vals[1:]) if b - a > 1e-9]
    return min(diffs) if diffs else 0.25


def find_pivots(rows: list[list]) -> list[Pivot]:
    """3-candle pivot; candle 2 is the swing point (swing-points.md, aura-06)."""
    out = []
    for i in range(1, len(rows) - 1):
        a, b, c = rows[i - 1], rows[i], rows[i + 1]
        if b[2] > a[2] and b[2] > c[2]:
            out.append(Pivot(t=int(b[0]), price=float(b[2]), side="high"))
        if b[3] < a[3] and b[3] < c[3]:
            out.append(Pivot(t=int(b[0]), price=float(b[3]), side="low"))
    return out


def mark_swept(pivots: list[Pivot], rows: list[list]) -> None:
    """A resting level is one NOT yet taken. Needed for the LOOK-LEFT fallback."""
    times = [int(r[0]) for r in rows]
    for p in pivots:
        for j in range(len(rows)):
            if times[j] <= p.t:
                continue
            if p.side == "high" and float(rows[j][2]) > p.price:
                p.swept_at = times[j]
                break
            if p.side == "low" and float(rows[j][3]) < p.price:
                p.swept_at = times[j]
                break


def find_fvgs(rows: list[list], res: str, tick: float) -> tuple[list[Gap], int]:
    """Verbatim: bullish `low > high[2]`, bearish `high < low[2]`."""
    gaps, below_floor = [], 0
    for i in range(2, len(rows)):
        c0, c2 = rows[i], rows[i - 2]
        lo0, hi0 = float(c0[3]), float(c0[2])
        lo2, hi2 = float(c2[3]), float(c2[2])
        if lo0 > hi2:
            size = (lo0 - hi2) / tick
            if size < MIN_GAP_TICKS:
                below_floor += 1
                continue
            gaps.append(Gap("FVG", "bullish", lo0, hi2, int(c0[0]), res, size))
        elif hi0 < lo2:
            size = (lo2 - hi0) / tick
            if size < MIN_GAP_TICKS:
                below_floor += 1
                continue
            gaps.append(Gap("FVG", "bearish", lo2, hi0, int(c0[0]), res, size))
    return gaps, below_floor


def lifecycle(gaps: list[Gap], rows: list[list]) -> None:
    """Mitigation (verbatim from qt-pro) and INVERSION (from the Aura corpus).

    mitigation : bullish `low <= bottom` · bearish `high >= top`
    inversion  : a CLOSE through the zone flips polarity -> the gap becomes an iFVG.
                 A wick through is not an inversion, mirroring R6's close-not-wick rule
                 for ranges.
    """
    for g in gaps:
        for r in rows:
            t = int(r[0])
            if t <= g.formed_t:
                continue
            hi, lo, cl = float(r[2]), float(r[3]), float(r[4])
            # MITIGATION FIRST. Filling the gap is the weaker, earlier condition; a close
            # THROUGH it is a further step. Checking inversion first (as the first draft
            # did) meant mitigation was never recorded at all, because both conditions
            # land on the same bar.
            if g.mitigated_t is None:
                if g.direction == "bullish" and lo <= g.bottom:
                    g.mitigated_t = t
                elif g.direction == "bearish" and hi >= g.top:
                    g.mitigated_t = t
            if g.inverted_t is None:
                if g.direction == "bullish" and cl < g.bottom:
                    g.inverted_t, g.direction = t, "bearish"
                    # ⚠ ONLY an FVG becomes an iFVG. The corpus names exactly four gap
                    # types and "inverse fair value gap" is specific to the FVG. The
                    # first draft overwrote `kind` unconditionally, which RELABELLED
                    # EVERY NDOG/NWOG AS AN iFVG and inflated the iFVG count to 208.
                    if g.kind == "FVG":
                        g.kind = "iFVG"
                elif g.direction == "bearish" and cl > g.top:
                    g.inverted_t, g.direction = t, "bullish"
                    if g.kind == "FVG":
                        g.kind = "iFVG"
            if g.mitigated_t is not None and g.inverted_t is not None:
                break


def attach_liquidity(gaps: list[Gap], pivots: list[Pivot],
                     finer: list[Pivot] | None, tick: float) -> None:
    """B5 + B6 — the precise target, with dOoMeR's two stated fallbacks.

    Route is ALWAYS recorded, because "found by zooming in" is a weaker claim than
    "visible inside the gap", and collapsing them would hide which is which.
    NOT-VISIBLE is a distinct verdict from absent.
    """
    look_left_tol = 2 * tick
    for g in gaps:
        inside = [p for p in pivots
                  if g.bottom <= p.price <= g.top and p.t <= g.formed_t]
        if inside:
            best = max(inside, key=lambda p: p.t)          # nearest in time
            g.internal_liquidity, g.internal_liquidity_t = best.price, best.t
            g.liquidity_route = "INSIDE"
            continue
        # LOOK LEFT — a resting (untaken) level at a similar price
        left = [p for p in pivots
                if p.t <= g.formed_t and p.swept_at is None
                and abs(p.price - g.mid) <= (g.top - g.bottom) / 2 + look_left_tol]
        if left:
            best = max(left, key=lambda p: p.t)
            g.internal_liquidity, g.internal_liquidity_t = best.price, best.t
            g.liquidity_route = "LOOK-LEFT"
            continue
        # ZOOM IN — a lower-timeframe swing inside the same gap
        if finer:
            fin = [p for p in finer
                   if g.bottom <= p.price <= g.top and p.t <= g.formed_t]
            if fin:
                best = max(fin, key=lambda p: p.t)
                g.internal_liquidity, g.internal_liquidity_t = best.price, best.t
                g.liquidity_route = "ZOOM-IN"
                continue
        g.liquidity_route = "NOT-VISIBLE"
        # liquidity to the LEFT of the gap, on top of liquidity inside it (B7)
    for g in gaps:
        near = [p for p in pivots
                if p.t < g.formed_t and p.swept_at is None
                and abs(p.price - g.mid) <= (g.top - g.bottom)]
        if near:
            g.liquidity_left = max(near, key=lambda p: p.t).price


def stack_confluence(gaps: list[Gap]) -> None:
    """B7 — overlapping gaps (e.g. NWOG x FVG). Additive, per aura-09."""
    for i, g in enumerate(gaps):
        for j, h in enumerate(gaps):
            if i == j:
                continue
            if g.bottom <= h.top and h.bottom <= g.top:
                g.overlaps.append({"kind": h.kind, "top": h.top, "bottom": h.bottom})


def session_gaps(rows: list[list], tick: float) -> list[Gap]:
    """NDOG (prev close -> 18:00 open) and NWOG (Friday close -> Monday open)."""
    by_session: dict = {}
    for r in rows:
        dt = datetime.fromtimestamp(int(r[0]), NY)
        anchor = dt.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
        if dt < anchor:
            anchor -= timedelta(days=1)
        by_session.setdefault(anchor.date(), []).append(r)
    days = sorted(by_session)
    out = []
    for prev, curr in zip(days, days[1:]):
        po = float(by_session[prev][0][1])         # previous session OPEN
        pc = float(by_session[prev][-1][4])        # previous session close
        co = float(by_session[curr][0][1])         # this session's open
        if abs(co - pc) < 1e-9:
            continue
        gap_days = (curr - prev).days
        kind = "NWOG" if gap_days >= 3 else "NDOG"
        g = Gap(kind, "bullish" if co > pc else "bearish",
                max(pc, co), min(pc, co),
                int(by_session[curr][0][0]), "session",
                abs(co - pc) / tick)
        # ── NWOG subtype, verbatim from qt-pro.pine `classifyGap()`:
        #      gapUp   -> friBullish ? VOID_BULL : OVERLAP_BULL
        #      gapDown -> friBearish ? VOID_BEAR : OVERLAP_BEAR
        # A VOID is a gap in the same direction the prior session closed (a true hole);
        # an OVERLAP gaps against it, so the gap sits back inside the prior range.
        # This is a REFINEMENT of an existing type, not a fifth gap type — the corpus
        # names exactly four and this adds none (gaps.md, R11, chart-markup §0b).
        prev_bullish = pc > po
        prev_bearish = pc < po
        if co > pc:
            g.subtype = "VOID-BULL" if prev_bullish else "OVERLAP-BULL"
        else:
            g.subtype = "VOID-BEAR" if prev_bearish else "OVERLAP-BEAR"
        g.prior_session_open = po
        g.prior_session_close = pc
        out.append(g)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--res", default="5")
    ap.add_argument("--symbol", default="NQ")
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    def load(res):
        p = a.bars / f"s1e-bars-{res}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())["resolutions"][res]
        return d.get(a.symbol, {}).get("rows")

    rows_all = load(a.res)
    if not rows_all:
        raise SystemExit(f"no rows for {a.symbol} at {a.res}")
    t0 = int(datetime.strptime(a.t_from, "%Y-%m-%d").replace(tzinfo=NY).timestamp())
    t1 = int((datetime.strptime(a.t_to, "%Y-%m-%d").replace(tzinfo=NY)
              + timedelta(days=1)).timestamp())
    rows = [r for r in rows_all if t0 <= int(r[0]) <= t1]

    tick = measure_tick(rows_all)
    fvgs, below = find_fvgs(rows, a.res, tick)
    sess = session_gaps(rows, tick)
    gaps = fvgs + sess
    lifecycle(gaps, rows)

    pivots = find_pivots(rows)
    mark_swept(pivots, rows)
    finer_res = RES_ORDER[max(RES_ORDER.index(a.res) - 1, 0)]
    finer_rows = load(finer_res) if finer_res != a.res else None
    finer_pivots = None
    if finer_rows:
        fr = [r for r in finer_rows if t0 <= int(r[0]) <= t1]
        finer_pivots = find_pivots(fr)

    attach_liquidity(gaps, pivots, finer_pivots, tick)
    stack_confluence(gaps)

    routes: dict = {}
    kinds: dict = {}
    subtypes: dict = {}
    for g in gaps:
        routes[g.liquidity_route] = routes.get(g.liquidity_route, 0) + 1
        kinds[g.kind] = kinds.get(g.kind, 0) + 1
        if g.subtype:
            subtypes[g.subtype] = subtypes.get(g.subtype, 0) + 1

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "pd-arrays.json").write_text(json.dumps({
        "symbol": a.symbol, "resolution": a.res,
        "span": {"from": a.t_from, "to": a.t_to},
        "tick_measured": tick,
        "min_gap_ticks_declared": MIN_GAP_TICKS,
        "fvgs_excluded_below_floor": below,
        "zoom_in_source": finer_res if finer_pivots else "NOT-AVAILABLE",
        "counts_by_kind": kinds,
        "session_gap_subtypes": subtypes,
        "liquidity_route_counts": routes,
        "gaps": [{**asdict(g),
                  "formed_ny": datetime.fromtimestamp(g.formed_t, NY).isoformat(),
                  "mid": g.mid} for g in sorted(gaps, key=lambda x: x.formed_t)],
    }, indent=1), encoding="utf-8")

    print(f"[pd] {a.symbol} {a.res}  {a.t_from} -> {a.t_to}")
    print(f"[pd] gaps by kind          : {kinds}")
    print(f"[pd] session-gap subtypes   : {subtypes}")
    print(f"[pd] FVGs below {MIN_GAP_TICKS}-tick floor: {below} (declared, excluded)")
    print(f"[pd] tick measured         : {tick}")
    print(f"[pd] zoom-in source        : {finer_res if finer_pivots else 'NOT-AVAILABLE'}")
    print(f"[pd] 'what lies within'    : {routes}")
    print(f"[pd] -> {a.out / 'pd-arrays.json'}")


if __name__ == "__main__":
    main()
