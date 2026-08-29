#!/usr/bin/env python
"""
External Range Liquidity (ERL) — previous day / week / month highs and lows.

    python api/scripts/aura_erl.py --bars api/docs/evidence/s1e/bars/packed \
        --res 5 --from 2025-05-26 --to 2025-05-30 --out api/docs/evidence/s1e/erl

⭐ WHY THIS EXISTS
Paul manages a trade as "half off at **nearest IRL**, rest to final TP, SL to breakeven"
(2026-08-15). IRL and ERL are a PAIR: the internal target versus the external one.
`aura_pd_arrays.py` now computes the internal side — the liquidity nested inside a gap,
which gaps.md calls "the precise target". This computes the external side, which was
missing entirely from every implementation (us and the QT[✦] indicators alike).

Objects, per `qt-pro.pine`'s PXH/L block:
    previous DAY high/low      (pD.H / pD.L)
    previous WEEK high/low     (pW.H / pW.L)
    previous MONTH high/low    (pM.H / pM.L)
    plus the EQUILIBRIUM of each period's range (pD.EQ / pW.EQ / pM.EQ)

A level is drawn from its own formation until it is **BROKEN**, verbatim from the
indicator:

    if lvl.is_high and high > lvl.price   -> broken, stop_time = time[1]
    else if not is_high and low < lvl.price -> broken

⛔ NO QUADRANTS. The indicator offers `mode = "Quadrants"` (0.25 / 0.75) on these levels.
**Aura uses discount / equilibrium / premium ONLY** — rule 5 and `ranges.md` name quadrants
an explicit divergence from the ICT order-flow model. EQ is emitted; 0.25/0.75 are not, and
must not be added without a source line.

⚠ PERIOD BOUNDARY: days/weeks/months are anchored on the **18:00 NY session open**, the same
anchor the segment model and NDOG detection use. TradingView's `request.security(sym,"D",…)`
also opens CME futures at 18:00 ET, so the two agree — but this is stated rather than assumed.

⛔ NOT YET INCLUDED: the current RANGE's extremes, which are also ERL. The range engine has
not been rebuilt on the segment model yet, so range-extreme ERL is NOT-IMPLEMENTED rather
than silently omitted.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
DAY_START_HOUR = 18


@dataclass
class Level:
    period: str            # D | W | M
    label: str             # pD.H | pD.L | pD.EQ | ...
    side: str              # high | low | eq
    price: float
    formed_t: int          # when the period that produced it CLOSED (knowable-at)
    source_period: str     # which period's extreme this is
    broken_t: int | None = None


def session_anchor(ts: int) -> datetime:
    dt = datetime.fromtimestamp(ts, NY)
    a = dt.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if dt < a:
        a -= timedelta(days=1)
    return a


def bucket(rows: list[list], period: str) -> dict:
    """Group bars into D / W / M buckets on the 18:00 NY session anchor."""
    out: dict = {}
    for r in rows:
        a = session_anchor(int(r[0]))
        if period == "D":
            key = a.date()
        elif period == "W":
            iso = a.isocalendar()
            key = (iso[0], iso[1])
        else:
            key = (a.year, a.month)
        out.setdefault(key, []).append(r)
    return out


# How many PAST periods of levels to keep, matching qt-pro.pine's defaults
# (cnt_d = 2, cnt_w = 1, cnt_m = 1). Without a cap every historical low in a rising
# market stays "unbroken" and the output lists April lows as live targets — true but
# useless. The cap is a DISPLAY/relevance choice, so it is declared, not hidden.
KEEP = {"D": 2, "W": 1, "M": 1}


def build_levels(rows: list[list], period: str) -> list[Level]:
    b = bucket(rows, period)
    keys = sorted(b)
    levels: list[Level] = []
    for prev, curr in zip(keys, keys[1:]):
        pr = b[prev]
        hi = max(float(r[2]) for r in pr)
        lo = min(float(r[3]) for r in pr)
        # knowable only once the producing period has closed
        formed = int(b[curr][0][0])
        tag = {"D": "pD", "W": "pW", "M": "pM"}[period]
        levels.append(Level(period, f"{tag}.H", "high", hi, formed, str(prev)))
        levels.append(Level(period, f"{tag}.L", "low", lo, formed, str(prev)))
        levels.append(Level(period, f"{tag}.EQ", "eq", (hi + lo) / 2, formed, str(prev)))
    keep = KEEP[period] * 3          # H + L + EQ per period
    return levels[-keep:] if keep else levels


def mark_broken(levels: list[Level], rows: list[list]) -> None:
    """Verbatim: a high is broken by `high > price`, a low by `low < price`."""
    for lv in levels:
        for r in rows:
            t = int(r[0])
            if t <= lv.formed_t:
                continue
            if lv.side == "high" and float(r[2]) > lv.price:
                lv.broken_t = t
                break
            if lv.side == "low" and float(r[3]) < lv.price:
                lv.broken_t = t
                break
            # EQ is a reference level, not liquidity — it is never "taken", so it has
            # no broken state. Left as None deliberately.


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--res", default="5")
    ap.add_argument("--symbol", default="NQ")
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    raw = json.loads((a.bars / f"s1e-bars-{a.res}.json").read_text())["resolutions"][a.res]
    rows_all = raw[a.symbol]["rows"]

    t0 = int(datetime.strptime(a.t_from, "%Y-%m-%d").replace(tzinfo=NY).timestamp())
    t1 = int((datetime.strptime(a.t_to, "%Y-%m-%d").replace(tzinfo=NY)
              + timedelta(days=1)).timestamp())
    # levels need history BEFORE the window to have a previous period at all
    lookback = t0 - 86400 * 120
    hist = [r for r in rows_all if lookback <= int(r[0]) <= t1]
    win = [r for r in rows_all if t0 <= int(r[0]) <= t1]

    levels: list[Level] = []
    for period in ("D", "W", "M"):
        levels += build_levels(hist, period)
    mark_broken(levels, hist)

    # only those live at some point inside the requested window
    live = [lv for lv in levels
            if lv.formed_t <= t1 and (lv.broken_t is None or lv.broken_t >= t0)]

    unbroken = [lv for lv in live if lv.broken_t is None and lv.side != "eq"]
    counts = {}
    for lv in live:
        counts[lv.label] = counts.get(lv.label, 0) + 1

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "erl.json").write_text(json.dumps({
        "symbol": a.symbol, "resolution": a.res,
        "span": {"from": a.t_from, "to": a.t_to},
        "anchor": "18:00 NY session open (matches the segment model and NDOG)",
        "quadrants": "NOT EMITTED — rule 5 / ranges.md: discount/EQ/premium only",
        "range_extreme_erl": "NOT-IMPLEMENTED — the range engine is not rebuilt yet",
        "periods_kept": KEEP,
        "counts_by_label": counts,
        "levels": [{**asdict(lv),
                    "formed_ny": datetime.fromtimestamp(lv.formed_t, NY).isoformat(),
                    "broken_ny": (datetime.fromtimestamp(lv.broken_t, NY).isoformat()
                                  if lv.broken_t else None)}
                   for lv in sorted(live, key=lambda x: (x.period, x.formed_t))],
    }, indent=1), encoding="utf-8")

    print(f"[erl] {a.symbol} {a.res}  {a.t_from} -> {a.t_to}")
    print(f"[erl] levels live in window : {len(live)}   {counts}")
    print(f"[erl] still UNBROKEN at end : {len(unbroken)}  "
          f"(these are the resting external targets)")
    for lv in sorted(unbroken, key=lambda x: x.price, reverse=True):
        print(f"    {lv.label:<6} {lv.price:>10,.2f}   from {lv.source_period}")
    print(f"[erl] -> {a.out / 'erl.json'}")


if __name__ == "__main__":
    main()
